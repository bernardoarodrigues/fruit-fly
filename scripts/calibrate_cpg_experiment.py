"""Fixed exploratory CPG grid; isolated instances, unchanged runtime defaults."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import mujoco
import numpy as np
from scipy.ndimage import gaussian_filter1d

from fruitfly.body import BodyRuntime
from flygym_demo.complex_terrain import HybridTurningController
from flygym_demo.complex_terrain.hybrid_controller import HybridController
from scripts.benchmark_freewalking import digest, native_kinematics, leg_cycles, stats, LEGS

BENCHMARK=Path('validation/freewalking-benchmark.json')
PLAN=Path('validation/cpg-calibration-plan.json')
RESULT=Path('validation/cpg-calibration-experiment.json')


def conditional_reference(benchmark, flies, target_speed):
    per_animal=[]
    for fly in flies:
        rows=[r for r in benchmark['bouts'] if r['fly_id']==fly and
              abs(r['metrics']['model_root_speed_mm_s']['median']-target_speed)<=2.5]
        if not rows: continue
        metrics={}
        for leg in LEGS:
            for key in ('frequency_hz','tibia_rom_deg'):
                values=[(r['legs'][leg]['frequency_hz']['median'] if key=='frequency_hz' else
                         r['legs'][leg]['joint_rom_deg']['tibia']['median']) for r in rows]
                metrics[leg+'_'+key]=stats([v for v in values if v is not None])['median']
        per_animal.append({'fly_id':fly,'bouts':len(rows),'metrics':metrics})
    return {'target_speed_mm_s':target_speed,'selection_halfwidth_mm_s':2.5,
            'animal_count':len(per_animal),'per_animal':per_animal,
            'metrics':{key:stats([a['metrics'][key] for a in per_animal if a['metrics'][key] is not None])
                       for key in (leg+'_'+kind for leg in LEGS for kind in ('frequency_hz','tibia_rom_deg'))}}


def make_plan():
    benchmark=json.loads(BENCHMARK.read_text())
    import hashlib
    flies=sorted((a['fly_id'] for a in benchmark['per_animal']),key=lambda x:hashlib.sha256(x.encode()).hexdigest())
    training, evaluation=flies[:14], flies[14:]
    points=[]
    for animal in benchmark['per_animal']:
        if animal['fly_id'] not in training: continue
        bins=[b for b in animal['frequency_speed_relationship']['LF']['bins'] if b['cycle_frequency_hz']['n']>=3 and np.ptp(b['speed_bin_mm_s'])<=10]
        for b in bins:
            points.append({'fly_id':animal['fly_id'],'speed_mm_s':float(np.mean(b['speed_bin_mm_s'])),
                           'frequency_hz':b['cycle_frequency_hz']['median'],'weight':1/len(bins)})
    x=np.asarray([p['speed_mm_s'] for p in points]);y=np.asarray([p['frequency_hz'] for p in points])
    w=np.sqrt([p['weight'] for p in points])
    coefficients=np.linalg.lstsq(np.c_[np.ones(len(x)),x]*w[:,None],y*w,rcond=None)[0]
    speed_ref=float(np.median([a['metrics']['model_root_speed_mm_s']['median'] for a in benchmark['per_animal'] if a['fly_id'] in training]))
    config={'arena_half_size_mm':40,'initial_position_mm':[-12,0,.8],
            'food_position_mm':[-25,25],'water_position_mm':[25,25]}
    variants=[{'name':'baseline','amplitude':'drive','cadence':'12hz','adhesion_gain':40,'role':'frozen baseline'},
              {'name':'full_excursion','amplitude':'one','cadence':'12hz','adhesion_gain':40,'role':'mechanistic control; not eligible'},
              {'name':'cadence','amplitude':'one','cadence':'source_fit','adhesion_gain':40,'role':'candidate'},
              {'name':'cadence_adhesion10','amplitude':'one','cadence':'source_fit','adhesion_gain':10,'role':'candidate'},
              {'name':'cadence_adhesion0','amplitude':'one','cadence':'source_fit','adhesion_gain':0,'role':'candidate'}]
    fit={'formula':'f_hz = intercept + slope * desired_speed_mm_s; clip to observed fit-point frequency range',
         'intercept_hz':float(coefficients[0]),'slope_hz_per_mm_s':float(coefficients[1]),
         'frequency_clip_hz':[float(y.min()),float(y.max())],
         'desired_speed_rule':'drive * training-animal-median root speed; engineering command mapping',
         'training_speed_reference_mm_s':speed_ref,'points':points,
         'fit_method':'Weighted least squares, bin midpoint and median LF frequency; equal total weight per contributing animal; bins require >=3 cycles and width<=10mm/s; exclude broad40-100bin rather than invent its typical speed'}
    references={str(drive):conditional_reference(benchmark,evaluation,drive*speed_ref) for drive in (.5,1.)}
    return {'created_at':datetime.now(timezone.utc).isoformat(),'benchmark_sha256':digest(BENCHMARK),
            'script_sha256':digest(Path(__file__)),'body_code_sha256':digest(Path('fruitfly/body.py')),
            'controller_code_sha256':digest(Path(inspect.getfile(HybridTurningController))),
            'split':{'training_flies':training,'evaluation_flies':evaluation,
                     'method':'Sort fly IDs by SHA256; first14 fit, remaining8 comparison; exploratory after pooled data inspection, not a blinded biological holdout'},
            'fit':fit,'variants':variants,'drives':[.5,1.],'seeds':[11,12],
            'duration_s':1.5,'startup_excluded_s':.3,'sample_period_s':.005,'body_config':config,
            'source_comparison':references,'source_reference_method':'For each evaluation animal, median of bout medians within desired speed +/-2.5mm/s; then equal-weight animal medians. Includes same-clock cycle ROM, not direct angle retargeting.',
            'decision_rule':{'primary':'Mean absolute tibia ROM error across six legs, two drives and seeds reduced >=20% versus paired baseline',
                'physical':'All trials finite, upright_z>=0.5, thorax_z>=0.5mm, no MuJoCo warnings, <=1% sampled frames with no supporting leg force',
                'guards':'At each drive: mean absolute desired-speed error <= baseline+2mm/s; mean absolute heading-motion median <=1.2*baseline+10deg/s; >=3 evaluation animals in reference band',
                'promotion':'Only candidate roles eligible; passing supports discussion of optional controller, never default change or validated biology'},
            'scope':'20 fixed forward-only trials. No neural model or runtime source edits. No extra grid search after observing outcomes. Adhesion gains10/0 are diagnostic quarter/zero controls, not measured adhesive physiology.'}


def desired_frequency(plan,drive):
    fit=plan['fit']; speed=drive*fit['training_speed_reference_mm_s']
    return float(np.clip(fit['intercept_hz']+fit['slope_hz_per_mm_s']*speed,*fit['frequency_clip_hz']))


def configure_instance(body,variant,frequency):
    ids=body._adhesion_actuator_ids
    if not np.allclose(body.model.actuator_gainprm[ids,0],40):
        raise RuntimeError('Baseline adhesion gain differs from predeclared controller')
    body.model.actuator_gainprm[ids,0]=variant['adhesion_gain']
    if variant['amplitude']=='one':
        controller=body.controller
        def full_excursion_step(descending_signal,observation):
            descending_signal=np.asarray(descending_signal)
            if descending_signal.shape!=(2,) or np.any(descending_signal<=0):
                raise ValueError('This isolated experiment only defines positive forward commands')
            controller.cpg_network.intrinsic_amps[:]=1
            controller.cpg_network.intrinsic_freqs[:]=frequency
            return HybridController.step(controller,observation)
        controller.step=full_excursion_step


def run_trial(plan,variant,drive,seed,folder):
    cadence=12. if variant['cadence']=='12hz' else desired_frequency(plan,drive)
    qpos,tips,tibia,force,up,heights,tracking,correction,actforce=[],[],[],[],[],[],[],[],[]
    warnings=None; failure=None
    with BodyRuntime(seed=seed,config=plan['body_config']) as body:
        configure_instance(body,variant,cadence)
        order=body.fly.get_actuated_jointdofs_order('position')
        tibia_act=[body._position_actuator_ids[next(i for i,d in enumerate(order) if d.child.name==leg.lower()+'_tibia' and d.axis.value=='pitch')] for leg in LEGS]
        def record():
            qpos.append(np.r_[body.data.xpos[body._thorax_id],body.data.xquat[body._thorax_id]])
            tips.append(body.data.xpos[body._tarsus5_ids].copy())
            angle=body.data.qpos[body._proprio_joint_qpos['tibia_pitch']].copy()
            tibia.append(angle)
            force.append(body._support_forces[:,2].copy())
            up.append(float(body.data.xmat[body._thorax_id].reshape(3,3)[2,2]))
            heights.append(float(body.data.xpos[body._thorax_id,2]))
            tracking.append(angle-body.data.ctrl[tibia_act])
            correction.append(body.controller.last_info.get('net_corrections',np.zeros(6)).copy())
            actforce.append(body.data.actuator_force[body._position_actuator_ids].copy())
        record()
        for _ in range(round(plan['duration_s']/plan['sample_period_s'])):
            try:
                body.advance(plan['sample_period_s'],drive,drive,behavior='walk')
            except RuntimeError as e:
                failure=str(e);break
            record()
        warnings=body.data.warning.number.copy().tolist()
        model_mass=float(body.model.body_mass.sum())
    raw={'qpos':np.asarray(qpos),'tips_mm':np.asarray(tips),'tibia_rad':np.asarray(tibia),
         'ground_vertical_force_native':np.asarray(force),'up_z':np.asarray(up),'height_mm':np.asarray(heights),
         'tibia_tracking_error_rad':np.asarray(tracking),'reflex_corrections':np.asarray(correction),
         'position_actuator_force_native':np.asarray(actforce)}
    name=f"{variant['name']}-drive{drive:g}-seed{seed}"
    trace=folder/(name+'.npz');np.savez_compressed(trace,**raw)
    begin=round(plan['startup_excluded_s']/plan['sample_period_s'])
    window={key:value[begin:] for key,value in raw.items()}
    k=native_kinematics(window['qpos'],200,1)
    heading=k['heading_rad']
    smoothed=gaussian_filter1d(heading,sigma=1.5,mode='reflect')
    yaw=np.rad2deg(np.abs(np.diff(smoothed)*200))
    ref=plan['source_comparison'][str(drive)]
    no_support=float(np.mean(np.max(window['ground_vertical_force_native'],axis=1)<=1e-6))
    physical={'finite':all(np.isfinite(v).all() for v in raw.values()),
              'upright_min_z':float(np.min(window['up_z'])),'thorax_min_mm':float(np.min(window['height_mm'])),
              'no_leg_support_fraction':no_support,'mujoco_warning_counts':warnings,
              'mean_sum_ground_vertical_force_native':float(np.sum(window['ground_vertical_force_native'],axis=1).mean()),
              'weight_native':model_mass*9810,'max_position_actuator_force_native':float(np.abs(window['position_actuator_force_native']).max()),
              'tibia_tracking_rms_deg':float(np.rad2deg(np.sqrt(np.mean(window['tibia_tracking_error_rad']**2)))),
              'max_reflex_correction':float(np.max(window['reflex_corrections'])),'failure':failure}
    stable=(physical['finite'] and physical['upright_min_z']>=.5 and physical['thorax_min_mm']>=.5 and
            no_support<=.01 and not any(warnings) and not failure)
    legs={}
    for li,leg in enumerate(LEGS):
        cycles,quality=leg_cycles(window['tips_mm'][:,li],200)
        rom=stats([float(np.rad2deg(np.ptp(window['tibia_rad'][a:b+1,li]))) for a,b in cycles])
        legs[leg]={'cycles':len(cycles),'frequency_hz':stats([200/(b-a) for a,b in cycles]),
                   'tibia_rom_deg':rom,'quality':quality,
                   'reference_tibia_rom_deg':ref['metrics'][leg+'_tibia_rom_deg']['median']}
    errors=[abs(legs[leg]['tibia_rom_deg']['median']-legs[leg]['reference_tibia_rom_deg']) for leg in LEGS
            if legs[leg]['tibia_rom_deg']['median'] is not None and legs[leg]['reference_tibia_rom_deg'] is not None]
    speed=stats(k['speed_xy_mm_s'])
    return {'variant':variant['name'],'drive':drive,'seed':seed,'cadence_command_hz':cadence,
            'source_fitted_cadence_hz':desired_frequency(plan,drive),'desired_speed_mm_s':ref['target_speed_mm_s'],
            'speed_mm_s':speed,'speed_absolute_error_mm_s':abs(speed['median']-ref['target_speed_mm_s']),
            'absolute_heading_rate_deg_s':stats(yaw),
            'net_heading_rate_deg_s':float(np.rad2deg(heading[-1]-heading[0])/((len(heading)-1)/200)),
            'tibia_rom_mae_deg':float(np.mean(errors)) if errors else None,'legs':legs,
            'physical':physical,'physical_pass':bool(stable),'trace':str(trace),'trace_sha256':digest(trace)}


def decisions(plan,trials):
    results=[]
    for variant in plan['variants']:
        rows=[r for r in trials if r['variant']==variant['name']]
        baseline=[r for r in trials if r['variant']=='baseline']
        improvement=1-np.mean([r['tibia_rom_mae_deg'] for r in rows])/np.mean([r['tibia_rom_mae_deg'] for r in baseline])
        guards=[]
        for drive in plan['drives']:
            current=[r for r in rows if r['drive']==drive];control=[r for r in baseline if r['drive']==drive]
            guards.append({'drive':drive,
                'speed_guard':bool(np.mean([r['speed_absolute_error_mm_s'] for r in current])<=np.mean([r['speed_absolute_error_mm_s'] for r in control])+2),
                'heading_guard':bool(np.mean([r['absolute_heading_rate_deg_s']['median'] for r in current])<=1.2*np.mean([r['absolute_heading_rate_deg_s']['median'] for r in control])+10),
                'source_coverage_guard':plan['source_comparison'][str(drive)]['animal_count']>=3})
        passes=(variant['role']=='candidate' and improvement>=.2 and all(r['physical_pass'] for r in rows)
                and all(all(v for k,v in g.items() if k!='drive') for g in guards))
        results.append({'variant':variant['name'],'role':variant['role'],'tibia_rom_error_reduction_fraction':float(improvement),
                        'all_physical_pass':all(r['physical_pass'] for r in rows),'guards':guards,'eligible_for_optional_discussion':bool(passes)})
    return results


def plot(plan,report):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
    for drive,style in zip(plan['drives'],('o-','s--')):
        rows=[[r for r in report['trials'] if r['variant']==v['name'] and r['drive']==drive] for v in plan['variants']]
        values=[['speed_mm_s','median'],['absolute_heading_rate_deg_s','median'],['tibia_rom_mae_deg'],['physical','no_leg_support_fraction']]
        for ax,path in zip(axes.flat,values):
            def get(row):
                value=row
                for key in path:value=value[key]
                return value
            means=[float(np.mean([get(r) for r in group])) for group in rows]
            ax.plot(range(len(rows)),means,style,label=f'drive {drive:g}, mean of seeds11/12')
            for i,group in enumerate(rows):ax.scatter([i]*len(group),[get(r) for r in group],s=15,alpha=.5)
    for ax,label in zip(axes.flat,('Median speed (mm/s)','Median absolute heading rate (degrees/s)',
                                  'Tibia ROM mean absolute reference error (degrees)','Fraction of samples with no leg support')):
        ax.set_ylabel(label);ax.set_xticks(range(5),['Baseline','Full\nexcursion','Fitted\ncadence','Cadence\nadhesion10','Cadence\nadhesion0']);ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=8)
    fig.suptitle('Exploratory CPG grid — frozen baseline, no runtime default changes')
    fig.savefig(RESULT.with_suffix('.png'),dpi=160);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan-only',action='store_true')
    parser.add_argument('--run',action='store_true')
    args=parser.parse_args()
    if args.plan_only:
        if PLAN.exists():raise FileExistsError('Predeclared plan already exists; do not silently overwrite it')
        plan=make_plan();PLAN.write_text(json.dumps(plan,indent=2,allow_nan=False)+'\n')
        print(json.dumps({'fit':plan['fit'],'coverage':{k:v['animal_count'] for k,v in plan['source_comparison'].items()},'plan':str(PLAN)},indent=2));return
    if not args.run:parser.error('Choose --plan-only or --run')
    plan=json.loads(PLAN.read_text())
    if digest(BENCHMARK)!=plan['benchmark_sha256'] or digest(Path('fruitfly/body.py'))!=plan['body_code_sha256']:
        raise ValueError('Benchmark or frozen body changed after predeclaration')
    if digest(Path(__file__))!=plan['script_sha256']:
        raise ValueError('Experiment implementation changed after predeclaration')
    folder=Path('runs')/('cpg-calibration-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    folder.mkdir(parents=True)
    trials=[]
    for variant in plan['variants']:
        for drive in plan['drives']:
            for seed in plan['seeds']:
                trial=run_trial(plan,variant,drive,seed,folder);trials.append(trial)
                print(trial['variant'],drive,seed,'speed',round(trial['speed_mm_s']['median'],3),'rom_error',round(trial['tibia_rom_mae_deg'],3),'physical',trial['physical_pass'],flush=True)
    report={'plan':str(PLAN),'plan_sha256':digest(PLAN),'script_sha256':digest(Path(__file__)),
            'source_benchmark_sha256':digest(BENCHMARK),'trials':trials,'decisions':decisions(plan,trials),
            'scope':'Exploratory split after pooled-data review; no valid claim of blinded biological generalization; source model-normalized mixed-sex running only'}
    RESULT.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');plot(plan,report)
    print(json.dumps(report['decisions'],indent=2))

if __name__=='__main__':main()
