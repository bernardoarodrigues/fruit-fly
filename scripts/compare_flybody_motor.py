"""Fixed optional FlyBody motor comparison; no training or default changes.

Original model/weights/action wrappers from the successful isolated probe.
Only desired root preview is regenerated causally from the current command.
"""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

os.environ['TF_CPP_MIN_LOG_LEVEL']='2'
os.environ['CUDA_VISIBLE_DEVICES']='-1'
os.environ['OMP_NUM_THREADS']='1'
os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scripts.benchmark_freewalking import digest, native_kinematics, leg_cycles, stats, LEGS, LEG_SOURCE
from scripts.probe_flybody_inference import verify_sources

PLAN=Path('validation/flybody-motor-comparison-plan.json')
RESULT=Path('validation/flybody-motor-comparison.json')
BENCHMARK=Path('validation/freewalking-benchmark.json')
CPG=Path('validation/cpg-calibration-experiment.json')
REPO=Path('/tmp/fruit-fly-research-flybody')


def conditional_reference(benchmark, flies, target):
    animals=[]
    for fly in flies:
        rows=[r for r in benchmark['bouts'] if r['fly_id']==fly and abs(r['metrics']['model_root_speed_mm_s']['median']-target)<=2.5]
        if not rows:continue
        measures={}
        for leg in LEGS:
            measures[leg+'_frequency_hz']=stats([r['legs'][leg]['frequency_hz']['median'] for r in rows if r['legs'][leg]['frequency_hz']['median'] is not None])['median']
            measures[leg+'_tibia_rom_deg']=stats([r['legs'][leg]['joint_rom_deg']['tibia']['median'] for r in rows if r['legs'][leg]['joint_rom_deg']['tibia']['median'] is not None])['median']
        measures['absolute_yaw_deg_s']=stats([r['metrics']['absolute_turn_deg_s']['median'] for r in rows])['median']
        animals.append({'fly_id':fly,'bouts':len(rows),'metrics':measures})
    keys=animals[0]['metrics']
    return {'target_speed_mm_s':target,'halfwidth_mm_s':2.5,'animal_count':len(animals),'per_animal':animals,
            'metrics':{key:stats([a['metrics'][key] for a in animals if a['metrics'][key] is not None]) for key in keys}}


def make_plan():
    benchmark=json.loads(BENCHMARK.read_text())
    old_plan=json.loads(Path('validation/cpg-calibration-plan.json').read_text())
    cases=[{'name':'straight10','speed_mm_s':10,'yaw_rad_s':0},
           {'name':'straight20','speed_mm_s':20,'yaw_rad_s':0},
           {'name':'left20','speed_mm_s':20,'yaw_rad_s':2},
           {'name':'right20','speed_mm_s':20,'yaw_rad_s':-2},
           {'name':'zero','speed_mm_s':0,'yaw_rad_s':0},
           {'name':'withdraw20','speed_mm_s':20,'yaw_rad_s':0,'withdraw_at_s':.75}]
    return {'created_at':datetime.now(timezone.utc).isoformat(),'script_sha256':digest(__file__),
        'source_manifest_sha256':digest('validation/flybody-source-manifest.json'),
        'policy_receipt_sha256':digest('validation/flybody-walking-acquisition.json'),
        'benchmark_sha256':digest(BENCHMARK),'cpg_results_sha256':digest(CPG),
        'metrics_script_sha256':digest('scripts/benchmark_freewalking.py'),
        'requirements_lock_sha256':digest('validation/flybody-inference-requirements.lock'),
        'cases':cases,'seeds':[11,12],'duration_s':1.5,'startup_excluded_s':.3,
        'physics_dt_s':.0002,'control_sample_dt_s':.002,'heading_filter_sigma_s':.0075,
        'cycle_method':'Existing benchmark leg-tip speed Hilbert phase; Gaussian sigma7.5ms, 4sigma edge trim; native500Hz, compared with CPG200Hz and source800Hz',
        'command_preview':'At each policy step only current command is extrapolated over128ms. Preserve integrated target pose. Off command is not previewed before t=.75s. No physical reset or target recentering.',
        'source_reference':{str(v):conditional_reference(benchmark,old_plan['split']['evaluation_flies'],v) for v in (10,20)},
        'source_split':old_plan['split'],'source_caveat':'Same already-inspected mixed-sex pooled running benchmark; no per-fly sex. Exploratory, not blinded or independent animal validation.',
        'rules':{'physical':'Every trial finite, no MuJoCo warnings, upright_z>=.5, rootheight>=.5mm, <=1% samples without actual positive leg-floor contact force',
            'straight_speed':'At10/20mm/s mean absolute median-speed error <= frozen paired CPG baseline+2mm/s',
            'straight_yaw':'At both speeds median absolute yaw motion averaged over seeds reduced >=20% versus paired CPG baseline',
            'joint_rom':'Across both straight speeds/seeds, six-leg tibia ROM mean absolute reference error <= recomputed frozen CPG error+5deg; descriptive same-axis ROM, not complete pose equivalence',
            'turn':'At both signed2rad/s commands, signed median yaw within25% of command and median speed within20% of20mm/s',
            'zero':'After startup, median planar speed<=1mm/s and net planar displacement<=.5mm',
            'withdrawal':'In fixed1.0–1.5s window (250ms after withdrawal), median speed<=1mm/s and net displacement<=.5mm',
            'promotion':'All rules pass to support optional adapter discussion; no automatic integration or biological-fidelity claim'},
        'diagnostics':['actual support/weight','canonical clipping by adhesion/position','position-force limit availability and saturation where defined','tibia tracking versus filtered activation','supporting-claw marker speed (not exact contact slip)','cadence and ROM by leg','signed/absolute yaw'],
        'scope':'12 predeclared trials, no fitting or parameter changes, no neural or food input; preserve failures'}


def analyze_window(raw, start_s, stop_s):
    dt=.002; begin=round(start_s/dt); end=round(stop_s/dt)+1
    q=raw['pose'][begin:end];k=native_kinematics(q,1/dt,10)
    heading=gaussian_filter1d(k['heading_rad'],sigma=.0075/dt,mode='reflect')
    yaw=np.rad2deg(np.diff(heading)/dt)
    return {'speed_mm_s':stats(k['speed_xy_mm_s']),'signed_yaw_deg_s':stats(yaw),
        'absolute_yaw_deg_s':stats(abs(yaw)),
        'net_heading_rate_deg_s':float(np.rad2deg(k['heading_rad'][-1]-k['heading_rad'][0])/(stop_s-start_s)),
        'net_displacement_mm':float(np.linalg.norm(q[-1,:2]-q[0,:2])*10)}


def run_trial(policy, tf, case, seed, plan, folder):
    import mujoco
    from flybody.fly_envs import walk_imitation
    from flybody.tasks.synthetic_trajectories import constant_speed_trajectory
    env=walk_imitation(random_state=np.random.RandomState(seed))
    qref,vref=constant_speed_trajectory(820,speed=case['speed_mm_s']/10,yaw_speed=case['yaw_rad_s'])
    vref[:,3:]=[0,0,case['yaw_rad_s']]
    env.task._traj_generator.set_next_trajectory(qref,vref)
    timestep=env.reset()
    spec=env.action_spec();lo=spec.minimum.astype(np.float32);hi=spec.maximum.astype(np.float32)
    model=env.physics.model;data=env.physics.data
    leg_joints=[env.task.walker.mjcf_model.find('joint','tibia_'+LEG_SOURCE[leg]) for leg in LEGS]
    joint_ids=np.array([model.name2id(j.full_identifier,'joint') for j in leg_joints])
    qids=model.jnt_qposadr[joint_ids]
    assert np.allclose(model.jnt_axis[joint_ids],np.tile([1,0,0],(6,1)))
    leg_sites=[env.task.walker.mjcf_model.find('site','claw_'+LEG_SOURCE[leg]) for leg in LEGS]
    tibia_aids=np.array([model.name2id('walker/tibia_'+LEG_SOURCE[leg],'actuator') for leg in LEGS])
    filtered_ids=model.actuator_actadr[tibia_aids]
    assert np.all(filtered_ids>=0)
    floors={model.name2id(g.full_identifier,'geom') for g in env.task._arena.ground_geoms}
    geom_leg={i:li for i in range(model.ngeom) for li,leg in enumerate(LEGS)
              if LEG_SOURCE[leg] in model.id2name(i,'geom')}
    force_bounds=model.actuator_forcerange.copy();force_limited=model.actuator_forcelimited.copy().astype(bool)
    weight=float(env.task.walker.weight)
    raw={key:[] for key in ['pose','tips_mm','tibia_rad','up_z','support_dyne','ground_contact_count','actuator_force','tibia_tracking_rad']}
    actions=[];native_actions=[];commands=[];target=[]
    def record():
        pos,quat=env.task.walker.get_pose(env.physics)
        raw['pose'].append(np.r_[pos,quat]);raw['tips_mm'].append(env.physics.bind(leg_sites).xpos.copy()*10)
        raw['tibia_rad'].append(data.qpos[qids].copy())
        raw['up_z'].append(float(env.physics.bind(env.task.walker.root_body).xmat.reshape(3,3)[2,2]))
        # dm-control ends its step with mj_step1: contacts are current but the
        # solved constraint force belongs to the previous configuration. Rebuild
        # both on a detached full MjData copy; never alter the policy's state.
        diagnostic_data=copy.copy(data.ptr)
        mujoco.mj_forward(model.ptr,diagnostic_data)
        force=np.zeros(6);contacts=np.zeros(6,dtype=int);contact_force=np.zeros(6)
        for ci,contact in enumerate(diagnostic_data.contact):
            if contact.geom1 in floors:leg=geom_leg.get(contact.geom2)
            elif contact.geom2 in floors:leg=geom_leg.get(contact.geom1)
            else:continue
            if leg is not None:
                mujoco.mj_contactForce(model.ptr,diagnostic_data,ci,contact_force)
                force[leg]+=abs((contact_force[:3]@contact.frame.reshape(3,3))[2])
                contacts[leg]+=1
        raw['support_dyne'].append(force);raw['ground_contact_count'].append(contacts)
        raw['actuator_force'].append(data.actuator_force.copy())
        raw['tibia_tracking_rad'].append(data.qpos[qids]-data.act[filtered_ids])
    # Warm the restored graph outside timed integration.
    policy({key:tf.convert_to_tensor(np.asarray(value,np.float32)[None]) for key,value in timestep.observation.items()}).mean().numpy()
    record();target_pose=qref[0].copy();failure=None;begin=time.perf_counter()
    for i in range(750):
        speed=case['speed_mm_s']/10;yaw=case['yaw_rad_s']
        if 'withdraw_at_s' in case and i*.002>=case['withdraw_at_s']:speed=yaw=0.
        heading=2*np.arctan2(target_pose[6],target_pose[3]) # target is exactly planar
        preview,pvel=constant_speed_trajectory(65,speed=speed,yaw_speed=yaw,
                            init_pos=target_pose[:3],init_heading=heading)
        pvel[:,3:]=[0,0,yaw] # correct source helper's per-step angular-velocity units
        env.task._ref_qpos[i:i+65]=preview;env.task._ref_qvel[i:i+65]=pvel
        # Composer cached these two before the new command arrived. Refresh only
        # the two command observations; all physical sensors remain untouched.
        observation=dict(timestep.observation)
        for key in ['walker/ref_displacement','walker/ref_root_quat']:
            observation[key]=env.task.observables[key](env.physics)
        batch={key:tf.convert_to_tensor(np.asarray(value,np.float32)[None]) for key,value in observation.items()}
        action=policy(batch).mean().numpy()[0]
        if not np.isfinite(action).all():failure='nonfinite action';break
        native=lo+np.float32(.5)*(np.clip(action,-1,1)+1)*(hi-lo)
        actions.append(action.copy());native_actions.append(native.copy());commands.append([speed*10,yaw]);target.append(preview[0].copy())
        timestep=env.step(native);target_pose=preview[1].copy();record()
        if not all(np.isfinite(v).all() for v in [data.qpos,data.qvel,data.actuator_force]):failure='nonfinite physical state';break
        if timestep.last():failure=f'early termination at{i+1}';break
    wall=time.perf_counter()-begin
    raw={k:np.asarray(v) for k,v in raw.items()};raw.update(canonical_action=np.asarray(actions),native_action=np.asarray(native_actions),command=np.asarray(commands),target_pose=np.asarray(target))
    name=f"{case['name']}-seed{seed}";trace=folder/(name+'.npz');np.savez_compressed(trace,**raw)
    warnings=[int(w.number) for w in data.warning]
    if failure:return {'case':case['name'],'seed':seed,'failure':failure,'physical_pass':False,'trace':str(trace),'trace_sha256':digest(trace)}
    window=slice(150,None);moving_stop=.75 if 'withdraw_at_s' in case else 1.5
    legwindow=slice(150,round(moving_stop/.002)+1)
    summary=analyze_window(raw,.3,1.5)
    support=raw['support_dyne'][window]
    physical={'finite':all(np.isfinite(v).all() for v in raw.values()),'up_z_min':float(raw['up_z'][window].min()),
              'height_mm_min':float(raw['pose'][window,2].min()*10),
              'no_leg_support_fraction':float(np.mean(np.max(support,axis=1)<=1e-8)),
              'support_over_weight_mean':float(np.mean(support.sum(axis=1))/weight),
              'body_weight_dyne':weight,'mujoco_warning_counts':warnings,
              'position_force_limited_count':int(force_limited.sum()),
              'max_absolute_actuator_force_native':float(np.max(np.abs(raw['actuator_force'][window]))),
              'tibia_filtered_tracking_rms_deg':float(np.rad2deg(np.sqrt(np.mean(raw['tibia_tracking_rad'][window]**2))))}
    if force_limited.any():
        force=raw['actuator_force'][window][:,force_limited];bounds=force_bounds[force_limited]
        physical['force_at_limit_fraction']=float(np.mean((force<=bounds[:,0]+.01*np.ptp(bounds,axis=1))|(force>=bounds[:,1]-.01*np.ptp(bounds,axis=1))))
    else:physical['force_at_limit_fraction']=None
    physical_pass=(physical['finite'] and physical['up_z_min']>=.5 and physical['height_mm_min']>=.5 and physical['no_leg_support_fraction']<=.01 and not any(warnings))
    legs={}
    for li,leg in enumerate(LEGS):
        cycles,quality=leg_cycles(raw['tips_mm'][legwindow,li],500) if case['speed_mm_s'] else ([],{'not_applicable':'zero command, settling motion not assigned gait cycles'})
        rom=stats([float(np.rad2deg(np.ptp(raw['tibia_rad'][legwindow,li][a:b+1]))) for a,b in cycles])
        marker_speed=np.linalg.norm(np.diff(raw['tips_mm'][window,li],axis=0),axis=1)*500
        contact=(support[:-1,li]>1e-8)&(support[1:,li]>1e-8)
        legs[leg]={'cycles':len(cycles),'frequency_hz':stats([500/(b-a) for a,b in cycles]),'tibia_rom_deg':rom,'quality':quality,
                   'supporting_claw_marker_speed_mm_s':stats(marker_speed[contact])}
    if case['speed_mm_s']:
        reference=plan['source_reference'][str(case['speed_mm_s'])]
        errors=[abs(legs[leg]['tibia_rom_deg']['median']-reference['metrics'][leg+'_tibia_rom_deg']['median']) for leg in LEGS if legs[leg]['tibia_rom_deg']['median'] is not None]
        summary['tibia_rom_mae_deg']=float(np.mean(errors)) if errors else None
    else:summary['tibia_rom_mae_deg']=None
    a=raw['canonical_action'][150:]
    result={'case':case['name'],'seed':seed,**summary,'legs':legs,'physical':physical,'physical_pass':bool(physical_pass),
        'canonical_clipped_fraction':float(np.mean(abs(a)>1)),'adhesion_clipped_fraction':float(np.mean(abs(a[:,:6])>1)),
        'position_clipped_fraction':float(np.mean(abs(a[:,6:])>1)),'max_abs_canonical_action':float(abs(a).max()),
        'wall_s':wall,'real_time_factor':1.5/wall,'trace':str(trace),'trace_sha256':digest(trace),
        'physical_trace_sha256':hashlib.sha256(b''.join(raw[k].tobytes() for k in ['pose','tibia_rad','tips_mm'])).hexdigest(),
        'tibia_axis_compiled':model.jnt_axis[joint_ids].tolist(),'tibia_names':[j.full_identifier for j in leg_joints]}
    if 'withdraw_at_s' in case:
        result['before_withdrawal']=analyze_window(raw,.3,.75)
        result['after_withdrawal']=analyze_window(raw,1.,1.5)
        result['first_zero_command_s']=float(np.flatnonzero(raw['command'][:,0]==0)[0]*.002)
    return result


def decide(plan,trials):
    cpg=[x for x in json.loads(CPG.read_text())['trials'] if x['variant']=='baseline']
    straight=[];baseline_rom=[];policy_rom=[]
    for speed,drive in [(10,.5),(20,1.)]:
        current=[r for r in trials if r['case']==f'straight{speed}'];base=[r for r in cpg if r['drive']==drive]
        ref=plan['source_reference'][str(speed)]
        for r in base:
            baseline_rom.append(float(np.mean([abs(r['legs'][leg]['tibia_rom_deg']['median']-ref['metrics'][leg+'_tibia_rom_deg']['median']) for leg in LEGS])))
        policy_rom.extend(r['tibia_rom_mae_deg'] for r in current)
        current_yaw=float(np.mean([r['absolute_yaw_deg_s']['median'] for r in current]));base_yaw=float(np.mean([r['absolute_heading_rate_deg_s']['median'] for r in base]))
        error=float(np.mean([abs(r['speed_mm_s']['median']-speed) for r in current]));base_error=float(np.mean([abs(r['speed_mm_s']['median']-speed) for r in base]))
        straight.append({'speed_mm_s':speed,'flybody_abs_yaw_deg_s':current_yaw,'cpg_abs_yaw_deg_s':base_yaw,
            'yaw_reduction_fraction':1-current_yaw/base_yaw,'yaw_pass':current_yaw<=.8*base_yaw,
            'flybody_speed_error_mm_s':error,'cpg_speed_error_mm_s':base_error,'speed_pass':error<=base_error+2})
    turns=[]
    for case,command in [('left20',2),('right20',-2)]:
        rows=[r for r in trials if r['case']==case]
        turns.append({'case':case,'command_deg_s':float(np.rad2deg(command)),
            'yaw_pass':all(abs(r['signed_yaw_deg_s']['median']-np.rad2deg(command))<=.25*abs(np.rad2deg(command)) for r in rows),
            'speed_pass':all(abs(r['speed_mm_s']['median']-20)<=4 for r in rows)})
    rest=all(r['speed_mm_s']['median']<=1 and r['net_displacement_mm']<=.5 for r in trials if r['case']=='zero')
    withdrawal=all(r['after_withdrawal']['speed_mm_s']['median']<=1 and r['after_withdrawal']['net_displacement_mm']<=.5 for r in trials if r['case']=='withdraw20')
    rom={'flybody_mean_mae_deg':float(np.mean(policy_rom)),'cpg_mean_mae_deg':float(np.mean(baseline_rom)),
         'pass':float(np.mean(policy_rom))<=float(np.mean(baseline_rom))+5}
    physical=all(r['physical_pass'] for r in trials)
    pass_all=(physical and rom['pass'] and rest and withdrawal and all(x['speed_pass'] and x['yaw_pass'] for x in straight+turns))
    return {'physical_pass_all':physical,'straight':straight,'turns':turns,'joint_rom':rom,'zero_pass':rest,
            'withdrawal_pass':withdrawal,'eligible_for_optional_adapter_discussion':bool(pass_all),
            'defaults_changed':False,'biological_validation_claim':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan-only',action='store_true');parser.add_argument('--run',action='store_true');args=parser.parse_args()
    if args.plan_only:
        if PLAN.exists():raise FileExistsError('Predeclared plan exists')
        PLAN.write_text(json.dumps(make_plan(),indent=2,allow_nan=False)+'\n');print('Plan saved',digest(PLAN));return
    if not args.run:parser.error('choose --plan-only or --run')
    plan=json.loads(PLAN.read_text())
    for path,key in [(Path(__file__),'script_sha256'),(BENCHMARK,'benchmark_sha256'),(CPG,'cpg_results_sha256'),(Path('scripts/benchmark_freewalking.py'),'metrics_script_sha256')]:
        if digest(path)!=plan[key]:raise ValueError(f'Changed since plan: {path}')
    verify_sources(REPO);sys.path.insert(0,str(REPO.resolve()))
    import tensorflow as tf
    import tensorflow_probability as tfp
    tf.config.set_visible_devices([], 'GPU');tf.config.threading.set_intra_op_parallelism_threads(1);tf.config.threading.set_inter_op_parallelism_threads(1)
    tfp.experimental.auto_composite_tensor(tfp.distributions.Independent);_=tfp.distributions.Normal
    policy=tf.saved_model.load('data/raw/flybody/walking')
    folder=Path('runs')/('flybody-comparison-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));folder.mkdir(parents=True)
    trials=[]
    for case in plan['cases']:
        for seed in plan['seeds']:
            trial=run_trial(policy,tf,case,seed,plan,folder);trials.append(trial)
            RESULT.write_text(json.dumps({'plan_sha256':digest(PLAN),'complete':False,'trials':trials},indent=2,allow_nan=False)+'\n')
            print(case['name'],seed,'physical',trial['physical_pass'],'speed',trial.get('speed_mm_s',{}).get('median'),'yaw',trial.get('absolute_yaw_deg_s',{}).get('median'),flush=True)
    report={'plan_sha256':digest(PLAN),'script_sha256':digest(__file__),'complete':True,'trials':trials}
    report['decisions']=decide(plan,trials) if all('failure' not in r for r in trials) else {'eligible_for_optional_adapter_discussion':False,'failure':'One or more trials failed; preserve partial traces'}
    report['seed_pairs_identical_physics']={case['name']:len({r.get('physical_trace_sha256') for r in trials if r['case']==case['name']})==1 for case in plan['cases']}
    RESULT.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps(report['decisions'],indent=2))


if __name__=='__main__':main()
