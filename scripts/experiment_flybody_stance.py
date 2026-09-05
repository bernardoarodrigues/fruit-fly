"""Predeclared source-native posture holds; no learned weights/runtime changes."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
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
from scripts.benchmark_freewalking import digest, stats, leg_cycles, LEGS, LEG_SOURCE
from scripts.compare_flybody_motor import analyze_window
from scripts.probe_flybody_inference import verify_sources

PLAN=Path('validation/flybody-stance-plan.json')
RESULT=Path('validation/flybody-stance-experiment.json')
AUDIT=Path('validation/flybody-stance-actuator-audit.json')
REPO=Path('/tmp/fruit-fly-research-flybody')
VARIANTS=['policy_zero','last_target','measured_length','neutral_zero']
ASSAYS=['zero_start','walk_stop','walk_stop_resume']


def make_plan():
    audit=json.loads(AUDIT.read_text())
    assert audit['initialization_only_no_physics_rollout']
    assert len(audit['rows'])==59
    for r in audit['rows'][6:]:
        assert r['gain'][0]>0 and r['bias']==[0.,-r['gain'][0],0.]
        assert r['range'][0]<=0<=r['range'][1]
    previous=json.loads(Path('validation/flybody-motor-comparison.json').read_text())
    base=next(t for t in previous['trials'] if t['case']=='straight20' and t['seed']==11)
    return {'created_at':datetime.now(timezone.utc).isoformat(),'script_sha256':digest(__file__),
        'actuator_audit_sha256':digest(AUDIT),
        'comparison_script_sha256':digest('scripts/compare_flybody_motor.py'),
        'metrics_script_sha256':digest('scripts/benchmark_freewalking.py'),
        'baseline_results_sha256':digest('validation/flybody-motor-comparison.json'),
        'source_manifest_sha256':digest('validation/flybody-source-manifest.json'),
        'policy_receipt_sha256':digest('validation/flybody-walking-acquisition.json'),
        'requirements_lock_sha256':digest('validation/flybody-inference-requirements.lock'),
        'variants':VARIANTS,'assays':ASSAYS,'seed':11,'duration_s':2.,'physics_dt_s':.0002,'control_dt_s':.002,
        'seed_caveat':'Previous seeds11/12 yielded identical deterministic mean-policy physics; do not repeat as independent trials.',
        'gate_schedule':{'zero_start':'off throughout; intended on-speed20mm/s suppressed',
            'walk_stop':'on0-.6s then off.6-2s','walk_stop_resume':'on0-.6s, off.6-1.2s, on1.2-2s'},
        'windows':{'zero_start':{'stop':[.3,2.]},'walk_stop':{'stop':[.85,2.]},
                   'walk_stop_resume':{'stop':[.85,1.2],'resume':[1.5,2.]}},
        'hold_semantics':{'policy_zero':'Control: original policy continues selecting posture with zero-speed reference while gate off.',
            'last_target':'At off edge capture last applied native position targets. At zero-start these are reset native controls (zero).',
            'measured_length':'At off edge capture actual actuator transmission lengths in source action order, including tendon channels; original affine gain law verified.',
            'neutral_zero':'At off edge set all53 native position targets to zero, the source neutral geometry.',
            'adhesion':'All three engineering holds command native1 to each of six adhesion controls; original0.985gain/filter/friction retained. This is an engineering stance choice, not measured neural adhesion.',
            'bounds':'Clip latched position targets once to original ctrlrange; retain clipping diagnostic. No root pose or velocity clamps.',
            'mute':'Locomotor-policy output mute with posture actuation retained. Shadow policy is evaluated but contributes no actions during engineering hold.',
            'resume':'At rising gate release latch and immediately use unchanged mean-policy action; reference advances from preserved integrated target, no recenter/reset or entry blend.'},
        'reference':'1100frames; rebuild current-only65frame128ms preview each tick. No anticipation of gate edges, no food or environmental targets.',
        'rules':{'physical':'Every trial after.3s finite; warningszero; rootheight>=.5mm; upright_z>=.5; <=1%500Hzsamples withoutpositiveactualleg-floorforce.',
            'stop':'Every declared stopwindow median unsmoothed speed<=1mm/s and net displacement<=.5mm.',
            'resume':'In1.5-2s median speed16-24mm/s; medianabsolute yaw<=1.2*frozenstraight20+10deg/s; physicalgatealsoapplies.',
            'resume_absolute_yaw_ceiling_deg_s':1.2*base['absolute_yaw_deg_s']['median']+10,
            'mute':'Every gate-off native hold action equals captured/clipped53positiontargets plus adhesion1; shadow policy output ignored.',
            'decision':'Each engineering variant must pass everyassay/stop/physical/mute/resumecheck; no automaticpromotion. Baselinecontrolineligible.'},
        'scope':'12fixedtrials (4variantsx3assays), nofit/gainsearch/neuralintegration; preservefailures; female-derived body and engineering posture hold.'}


def enabled(assay,t):
    if assay=='zero_start':return False
    if assay=='walk_stop':return t<.6
    return t<.6 or t>=1.2


def capture_hold(variant,last_native,lengths,lo,hi):
    if variant=='last_target':unclipped=last_native.copy()
    elif variant=='measured_length':unclipped=lengths.copy()
    elif variant=='neutral_zero':unclipped=np.zeros(59)
    else:raise ValueError(variant)
    unclipped[:6]=1
    return np.clip(unclipped,lo,hi).astype(np.float32),unclipped


def run_trial(policy,tf,variant,assay,plan,folder):
    import mujoco
    from flybody.fly_envs import walk_imitation
    from flybody.tasks.synthetic_trajectories import constant_speed_trajectory
    env=walk_imitation(random_state=np.random.RandomState(plan['seed']))
    qref,vref=constant_speed_trajectory(1100,speed=2 if enabled(assay,0) else 0)
    env.task._traj_generator.set_next_trajectory(qref,vref);timestep=env.reset()
    m,d=env.physics.model,env.physics.data;spec=env.action_spec()
    lo,hi=spec.minimum.astype(np.float32),spec.maximum.astype(np.float32)
    names=spec.name.split();aids=np.array([m.name2id('walker/'+n,'actuator') for n in names])
    audit=json.loads(AUDIT.read_text())
    for i,r in enumerate(audit['rows']):
        assert names[i]==r['name'] and aids[i]==r['compiled_actuator_id']
        np.testing.assert_array_equal(m.actuator_gainprm[aids[i],:3],r['gain'])
        np.testing.assert_array_equal(m.actuator_biasprm[aids[i],:3],r['bias'])
        assert m.actuator_trntype[aids[i]]==r['trntype']
        if i>=6:
            assert m.actuator_gaintype[aids[i]]==mujoco.mjtGain.mjGAIN_FIXED
            assert m.actuator_biastype[aids[i]]==mujoco.mjtBias.mjBIAS_AFFINE
    sites=[env.task.walker.mjcf_model.find('site','claw_'+LEG_SOURCE[l]) for l in LEGS]
    qids=np.array([m.jnt_qposadr[m.name2id('walker/tibia_'+LEG_SOURCE[l],'joint')] for l in LEGS])
    floors={m.name2id(g.full_identifier,'geom') for g in env.task._arena.ground_geoms}
    geom_leg={i:li for i in range(m.ngeom) for li,l in enumerate(LEGS) if LEG_SOURCE[l] in (m.id2name(i,'geom') or '')}
    raw={key:[] for key in ['pose','qpos','qvel','up_z','tips_mm','tibia_rad','support_dyne','contacts_by_leg','actuator_length','actuator_activation','actuator_force']}
    actions=[];shadow=[];gate=[];target=[];captures=[];failure=None
    def record():
        pos,quat=env.task.walker.get_pose(env.physics)
        raw['pose'].append(np.r_[pos,quat]);raw['qpos'].append(d.qpos.copy());raw['qvel'].append(d.qvel.copy())
        raw['up_z'].append(float(env.physics.bind(env.task.walker.root_body).xmat.reshape(3,3)[2,2]))
        raw['tips_mm'].append(env.physics.bind(sites).xpos.copy()*10);raw['tibia_rad'].append(d.qpos[qids].copy())
        diagnostic=copy.copy(d.ptr);mujoco.mj_forward(m.ptr,diagnostic)
        force=np.zeros(6);count=np.zeros(6,int);cf=np.zeros(6)
        for ci,c in enumerate(diagnostic.contact):
            if c.geom1 in floors:li=geom_leg.get(c.geom2)
            elif c.geom2 in floors:li=geom_leg.get(c.geom1)
            else:continue
            if li is not None:
                mujoco.mj_contactForce(m.ptr,diagnostic,ci,cf)
                force[li]+=abs((cf[:3]@c.frame.reshape(3,3))[2]);count[li]+=1
        raw['support_dyne'].append(force);raw['contacts_by_leg'].append(count)
        raw['actuator_length'].append(d.actuator_length[aids].copy());raw['actuator_activation'].append(d.act[m.actuator_actadr[aids]].copy())
        raw['actuator_force'].append(d.actuator_force[aids].copy())
    batch=lambda obs:{k:tf.convert_to_tensor(np.asarray(v,np.float32)[None]) for k,v in obs.items()}
    policy(batch(timestep.observation)).mean().numpy()
    record();last_native=d.ctrl[aids].copy();held=None;target_pose=qref[0].copy();begin=time.perf_counter()
    try:
        for i in range(1000):
            on=enabled(assay,i*.002);speed=2. if on else 0.
            preview,pvel=constant_speed_trajectory(65,speed=speed,init_pos=target_pose[:3],init_heading=0)
            env.task._ref_qpos[i:i+65]=preview;env.task._ref_qvel[i:i+65]=pvel
            obs=dict(timestep.observation)
            for k in ['walker/ref_displacement','walker/ref_root_quat']:obs[k]=env.task.observables[k](env.physics)
            proposed=policy(batch(obs)).mean().numpy()[0]
            if not np.isfinite(proposed).all():raise ValueError('nonfinite policy action')
            if on or variant=='policy_zero':
                native=lo+np.float32(.5)*(np.clip(proposed,-1,1)+1)*(hi-lo);held=None
            else:
                if held is None:
                    lengths=d.actuator_length[aids].copy()
                    held,unclipped=capture_hold(variant,last_native,lengths,lo,hi)
                    captures.append({'time_s':i*.002,'native':held.tolist(),'unclipped':unclipped.tolist(),
                        'last_native':last_native.tolist(),'measured_length':lengths.tolist(),
                        'position_bounds_clipped_count':int(np.count_nonzero((unclipped[6:]<lo[6:])|(unclipped[6:]>hi[6:]))),
                        'max_position_clip_native':float(np.max(abs(held[6:].astype(float)-unclipped[6:]))),
                        'max_target_jump_native':float(np.max(abs(held[6:]-last_native[6:])))})
                native=held.copy()
            actions.append(native.copy());shadow.append(proposed.copy());gate.append(on);target.append(preview[0].copy())
            timestep=env.step(native);last_native=native.copy();target_pose=preview[1].copy();record()
            if not all(np.isfinite(a).all() for a in [d.qpos,d.qvel,d.act,d.actuator_force]):raise ValueError('nonfinite physics')
            if timestep.last():raise RuntimeError(f'early source termination at step{i+1}')
    except Exception as error:
        failure=type(error).__name__+': '+str(error)
    wall=time.perf_counter()-begin
    raw={k:np.asarray(v) for k,v in raw.items()};raw.update(native_action=np.asarray(actions),shadow_canonical=np.asarray(shadow),motor_enabled=np.asarray(gate),target_pose=np.asarray(target))
    trace=folder/(variant+'-'+assay+'.npz');np.savez_compressed(trace,**raw)
    base={'variant':variant,'assay':assay,'seed':plan['seed'],'wall_s':wall,'trace':str(trace),'trace_sha256':digest(trace),'captures':captures}
    if failure:return {**base,'failure':failure,'physical_pass':False}
    after=slice(150,None);support=raw['support_dyne'][after];warnings=[int(x.number) for x in d.warning]
    physical={'finite':all(np.isfinite(a).all() for a in raw.values()),'min_up_z':float(raw['up_z'][after].min()),
        'min_height_mm':float(raw['pose'][after,2].min()*10),'unsupported_fraction':float(np.mean(support.max(axis=1)<=1e-8)),
        'warnings':warnings,'support_over_weight_mean':float(np.mean(support.sum(axis=1))/env.task.walker.weight)}
    physical_pass=physical['finite'] and physical['min_up_z']>=.5 and physical['min_height_mm']>=.5 and physical['unsupported_fraction']<=.01 and not any(warnings)
    windows={}
    for name,(start,stop) in plan['windows'][assay].items():
        summary=analyze_window(raw,start,stop);sl=slice(round(start/.002),round(stop/.002)+1);legs={}
        for li,leg in enumerate(LEGS):
            contact=raw['support_dyne'][sl,li]>1e-8;changes=np.diff(contact.astype(int))
            cycles,_=leg_cycles(raw['tips_mm'][sl,li],500) if name=='resume' else ([],{})
            legs[leg]={'contact_fraction':float(contact.mean()),'contact_onsets':int(np.count_nonzero(changes==1)),
                'contact_offsets':int(np.count_nonzero(changes==-1)),
                'whole_window_tibia_rom_deg':float(np.rad2deg(np.ptp(raw['tibia_rad'][sl,li]))),
                'frequency_hz':stats([500/(b-a) for a,b in cycles]),
                'cycle_tibia_rom_deg':stats([float(np.rad2deg(np.ptp(raw['tibia_rad'][sl,li][a:b+1]))) for a,b in cycles])}
        if name=='stop':passed=summary['speed_mm_s']['median']<=1 and summary['net_displacement_mm']<=.5
        else:passed=16<=summary['speed_mm_s']['median']<=24 and summary['absolute_yaw_deg_s']['median']<=plan['rules']['resume_absolute_yaw_ceiling_deg_s']
        windows[name]={**summary,'legs':legs,'pass':bool(passed),'window_s':[start,stop]}
    off=~raw['motor_enabled'];native=raw['native_action'][off]
    if variant=='policy_zero':mute_pass=None
    else:mute_pass=bool(len(captures)==1 and np.array_equal(native,np.tile(np.asarray(captures[0]['native'],np.float32),(len(native),1))))
    return {**base,'physical':physical,'physical_pass':bool(physical_pass),'windows':windows,'locomotor_policy_mute_pass':mute_pass,
        'off_shadow_canonical_clipped_fraction':float(np.mean(abs(raw['shadow_canonical'][off])>1)),
        'off_native_action_range_max':float(np.ptp(native,axis=0).max()),'real_time_factor':2./wall}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan-only',action='store_true');parser.add_argument('--run',action='store_true');args=parser.parse_args()
    if args.plan_only:
        if PLAN.exists():raise FileExistsError('Existing frozen plan')
        PLAN.write_text(json.dumps(make_plan(),indent=2,allow_nan=False)+'\n');print('Plan saved',digest(PLAN));return
    if not args.run:parser.error('Choose --plan-only or --run')
    plan=json.loads(PLAN.read_text())
    paths=[(__file__,'script_sha256'),(AUDIT,'actuator_audit_sha256'),('scripts/compare_flybody_motor.py','comparison_script_sha256'),
        ('scripts/benchmark_freewalking.py','metrics_script_sha256'),('validation/flybody-motor-comparison.json','baseline_results_sha256'),
        ('validation/flybody-source-manifest.json','source_manifest_sha256'),('validation/flybody-walking-acquisition.json','policy_receipt_sha256'),
        ('validation/flybody-inference-requirements.lock','requirements_lock_sha256')]
    for p,key in paths:assert digest(p)==plan[key],p
    verify_sources(REPO);sys.path.insert(0,str(REPO))
    import tensorflow as tf,tensorflow_probability as tfp
    tf.config.set_visible_devices([],'GPU');tf.config.threading.set_intra_op_parallelism_threads(1);tf.config.threading.set_inter_op_parallelism_threads(1)
    tfp.experimental.auto_composite_tensor(tfp.distributions.Independent);_=tfp.distributions.Normal
    policy=tf.saved_model.load('data/raw/flybody/walking')
    folder=Path('runs')/('flybody-stance-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));folder.mkdir(parents=True)
    trials=[]
    for variant in plan['variants']:
        for assay in plan['assays']:
            row=run_trial(policy,tf,variant,assay,plan,folder);trials.append(row)
            RESULT.write_text(json.dumps({'complete':False,'plan_sha256':digest(PLAN),'trials':trials},indent=2,allow_nan=False)+'\n')
            print(variant,assay,'physical',row['physical_pass'],'stop',row.get('windows',{}).get('stop',{}).get('speed_mm_s',{}).get('median'),'resume',row.get('windows',{}).get('resume',{}).get('speed_mm_s',{}).get('median'),row.get('failure',''),flush=True)
    decisions=[]
    for variant in plan['variants']:
        rows=[r for r in trials if r['variant']==variant]
        passed=all('failure' not in r and r['physical_pass'] and all(w['pass'] for w in r['windows'].values()) and r['locomotor_policy_mute_pass'] is True for r in rows)
        decisions.append({'variant':variant,'all_declared_gates_pass':bool(passed),'baseline_control':variant=='policy_zero','runtime_promoted':False})
    report={'complete':True,'plan_sha256':digest(PLAN),'script_sha256':digest(__file__),'trials':trials,'decisions':decisions,'runtime_changed':False,'biological_stance_claim':False}
    RESULT.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps(decisions,indent=2))


if __name__=='__main__':main()
