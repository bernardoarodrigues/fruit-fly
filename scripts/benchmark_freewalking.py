"""Aligned mixed-sex running summaries; no source trajectories are redistributed."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from importlib.metadata import version
import urllib.request
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import h5py
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import hilbert
from scipy.stats import spearmanr
from scipy.spatial.transform import Rotation

SOURCE = Path('data/raw/freewalking/free_running_raw_combined_v1.h5')
SHA256 = '369c57365b0155ea0e7d25b61ecfe09e08163ad44c896819c6f9dfb69f31f49e'
XML = Path('tmp/grooming-audit/freewalking-code/models/fruitfly_v1/fruitfly_v1_free.xml')
COMMIT = 'd346fcc50bc67e41ef57f98a44c0f53bebb2ab8f'
XML_SHA256 = '52dda79c9df22872fda0a37009f478515cc6398562a3988c79f11347e2c7f633'
XML_URL = f'https://raw.githubusercontent.com/elliottabe/3d_tracking_dataset/{COMMIT}/models/fruitfly_v1/fruitfly_v1_free.xml'
LEGS = ('LF','LM','LH','RF','RM','RH')
LEG_SOURCE = {leg:f'T{number}_{side}' for leg, number, side in
              [('LF',1,'left'),('LM',2,'left'),('LH',3,'left'),
               ('RF',1,'right'),('RM',2,'right'),('RH',3,'right')]}
TIP_NAMES = {leg:f'T{number}{side}_TaTip' for leg,number,side in
             [('LF',1,'L'),('LM',2,'L'),('LH',3,'L'),('RF',1,'R'),('RM',2,'R'),('RH',3,'R')]}


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(8*1024*1024):
            value.update(block)
    return value.hexdigest()


def stats(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return {'n':0,'mean':None,'p05':None,'p25':None,'median':None,'p75':None,'p95':None}
    return {'n':len(values),'mean':float(values.mean()), **dict(zip(
        ('p05','p25','median','p75','p95'),np.percentile(values,[5,25,50,75,95]).tolist()))}


def native_kinematics(qpos, sample_rate_hz, length_to_mm):
    """N-1 midpoint intervals; quaternion log, never four quaternion derivatives."""
    q = np.asarray(qpos,dtype=float)
    if q.ndim != 2 or q.shape[1] < 7 or len(q) < 2 or not np.isfinite(q).all():
        raise ValueError('Expected finite free-root qpos with at least two frames')
    if not np.isfinite(sample_rate_hz) or sample_rate_hz <= 0 or length_to_mm <= 0:
        raise ValueError('Invalid timing or length scale')
    norms = np.linalg.norm(q[:,3:7],axis=1)
    if np.max(np.abs(norms-1)) > 1e-3:
        raise ValueError('Quaternion normalization error exceeds 0.001')
    rotation = Rotation.from_quat(q[:,[4,5,6,3]])
    relative_body = (rotation[:-1].inv()*rotation[1:]).as_rotvec()
    rotation_mid = rotation[:-1]*Rotation.from_rotvec(relative_body/2)
    v_world = np.diff(q[:,:3],axis=0)*sample_rate_hz*length_to_mm
    omega_world = (rotation[1:]*rotation[:-1].inv()).as_rotvec()*sample_rate_hz
    forward = rotation.apply(np.broadcast_to([1.,0,0],(len(q),3)))
    projection = np.linalg.norm(forward[:,:2],axis=1)
    if np.min(projection) < .2:
        raise ValueError('Near-vertical heading has an ill-conditioned planar angle')
    heading = np.arctan2(forward[:,1],forward[:,0])
    yaw = np.angle(np.exp(1j*np.diff(heading)))*sample_rate_hz
    return {'velocity_world_mm_s':v_world,
            'speed_xy_mm_s':np.linalg.norm(v_world[:,:2],axis=1),
            'forward_mm_s':rotation_mid.inv().apply(v_world)[:,0],
            'turn_rad_s':yaw,'heading_rad':np.unwrap(heading),'angular_world_rad_s':omega_world,
            'angular_body_rad_s':relative_body*sample_rate_hz,
            'joint_velocity_rad_s':np.diff(q[:,7:],axis=0)*sample_rate_hz,
            'interval_midpoint_s':(np.arange(len(q)-1)+.5)/sample_rate_hz,
            'quaternion_max_norm_error':float(np.max(np.abs(norms-1))),
            'max_orientation_step_deg':float(np.rad2deg(np.linalg.norm(relative_body,axis=1)).max())}


def leg_cycles(positions_mm, sample_rate_hz, sigma_s=6/800):
    """Adapt the paper's speed/Hilbert phase on valid forward-difference intervals.

    Crossing -pi/2 defines swing onset. Discard 4-sigma edge regions and reject
    phase excursions that reverse >pi/4 during a candidate complete cycle.
    These extra edge/phase guards are engineering quality checks, not fitted data.
    """
    pos=np.asarray(positions_mm,dtype=float)
    speed=np.linalg.norm(np.diff(pos,axis=0)*sample_rate_hz,axis=1)
    sigma=sigma_s*sample_rate_hz
    edge=int(np.ceil(4*sigma))
    if len(speed) < 2*edge+4:
        return [], {'boundary_frames':edge,'candidate_cycles':0,'phase_reversal_rejected':0}
    smooth=gaussian_filter1d(speed,sigma=sigma,mode='reflect')
    phase=np.unwrap(np.angle(hilbert(smooth-smooth.mean())))
    boundaries=np.flatnonzero(np.diff(np.floor((phase+np.pi/2)/(2*np.pi)))>0)+1
    boundaries=boundaries[(boundaries>=edge)&(boundaries<len(speed)-edge)]
    accepted=[]
    rejected=0
    for a,b in zip(boundaries[:-1],boundaries[1:]):
        reversal=-np.minimum(np.diff(phase[a:b+1]),0).sum()
        if b-a < 2 or reversal > np.pi/4:
            rejected+=1
            continue
        accepted.append((int(a),int(b)))
    return accepted, {'boundary_frames':edge,'candidate_cycles':max(len(boundaries)-1,0),
                      'phase_reversal_rejected':rejected}


def source_analysis():
    if digest(SOURCE) != SHA256:
        raise ValueError('Source hash differs from acquired release')
    if not XML.exists():
        XML.parent.mkdir(parents=True,exist_ok=True)
        payload=urllib.request.urlopen(XML_URL,timeout=60).read()
        if hashlib.sha256(payload).hexdigest()!=XML_SHA256:
            raise ValueError('Downloaded model XML checksum differs from pinned audit')
        XML.write_bytes(payload)
    if digest(XML)!=XML_SHA256:
        raise ValueError('Local model XML checksum differs from pinned audit')
    xml=ET.parse(XML).getroot()
    xml_joints={x.attrib['name']:x.attrib for x in xml.findall('.//worldbody//joint')}
    animal=defaultdict(lambda:defaultdict(list))
    bouts=[]
    cycle_pairs=defaultdict(lambda:defaultdict(list))
    joint_fields=[f'{joint}_{LEG_SOURCE[leg]}' for leg in LEGS for joint in ('coxa','femur','tibia')]
    mapping={name:{'axis':xml_joints[name]['axis'],'class':xml_joints[name].get('class')} for name in joint_fields}
    with h5py.File(SOURCE) as source:
        info=source['info']
        names=[info['names_qpos'][str(i)][()].decode() for i in range(len(info['names_qpos']))]
        kpnames=[info['kp_names'][str(i)][()].decode() for i in range(len(info['kp_names']))]
        xml_qnames=[name for joint in xml.findall('.//worldbody//joint')
                    for name in [joint.attrib['name']]*(7 if joint.attrib.get('type')=='free' else 1)]
        if len(names)!=93 or names[:7] != ['free']*7 or names!=xml_qnames:
            raise ValueError('HDF5 qpos schema disagrees with named XML joints')
        for name in joint_fields:
            mapping[name]['qpos_column']=names.index(name)
        for index,bout in enumerate(sorted(k for k in source if k.startswith('bout_'))):
            fly=info['fly_ids'][str(index)][()].decode()
            q=source[bout+'/qpos'][:].astype(float)
            raw=source[bout+'/orig_keypoints'][:].astype(float)*.1
            k=native_kinematics(q,800,10)
            raw_speed=np.linalg.norm(np.diff(raw[:,kpnames.index('Scutellum'),:2],axis=0)*800,axis=1)
            measures={'model_root_speed_mm_s':k['speed_xy_mm_s'],
                      'model_root_forward_mm_s':k['forward_mm_s'],
                      'absolute_turn_unsmoothed_deg_s':np.rad2deg(np.abs(k['turn_rad_s'])),
                      'raw_scutellum_speed_mm_s':raw_speed}
            for sigma in (3,6,12):
                smoothed=gaussian_filter1d(q[:,:3],sigma=sigma,axis=0,mode='reflect')
                measures[f'model_root_speed_sigma{sigma}_mm_s']=np.linalg.norm(np.diff(smoothed[:,:2],axis=0)*8000,axis=1)
                heading_smoothed=gaussian_filter1d(k['heading_rad'],sigma=sigma,mode='reflect')
                measures[f'absolute_turn_sigma{sigma}_deg_s']=np.rad2deg(np.abs(np.diff(heading_smoothed)*800))
            measures['absolute_turn_deg_s']=measures['absolute_turn_sigma6_deg_s']
            net_rate=float(np.rad2deg(k['heading_rad'][-1]-k['heading_rad'][0])/((len(q)-1)/800))
            animal[fly]['absolute_net_heading_rate_per_bout_deg_s'].append(abs(net_rate))
            row={'bout':bout,'fly_id':fly,'net_heading_rate_deg_s':net_rate,'source_sex':'unknown individual; mixed-sex pooled dataset',
                 'frames':len(q),'duration_s':(len(q)-1)/800,
                 'quaternion_max_norm_error':k['quaternion_max_norm_error'],
                 'max_orientation_step_deg':k['max_orientation_step_deg'],
                 'max_scalar_joint_step_deg':float(np.rad2deg(np.abs(np.diff(q[:,7:],axis=0))).max()),
                 'metrics':{name:stats(value) for name,value in measures.items()},'legs':{}}
            for name,value in measures.items(): animal[fly][name].append(value)
            for leg in LEGS:
                cycles,quality=leg_cycles(raw[:,kpnames.index(TIP_NAMES[leg])],800)
                freq=[800/(b-a) for a,b in cycles]
                leg_stats={'cycles':len(cycles),'frequency_hz':stats(freq),'quality':quality,'joint_rom_deg':{},'joint_abs_velocity_rad_s':{}}
                animal[fly][leg+'_frequency_hz'].extend(freq)
                cycle_pairs[fly][leg].extend([(float(k['speed_xy_mm_s'][a:b].mean()),800/(b-a)) for a,b in cycles])
                for joint in ('coxa','femur','tibia'):
                    col=names.index(f'{joint}_{LEG_SOURCE[leg]}')
                    rom=[float(np.rad2deg(np.ptp(q[a:b+1,col]))) for a,b in cycles]
                    vel=np.abs(k['joint_velocity_rad_s'][:,col-7])
                    leg_stats['joint_rom_deg'][joint]=stats(rom)
                    leg_stats['joint_abs_velocity_rad_s'][joint]=stats(vel)
                    animal[fly][leg+'_'+joint+'_rom_deg'].extend(rom)
                    animal[fly][leg+'_'+joint+'_abs_velocity_rad_s'].append(vel)
                row['legs'][leg]=leg_stats
            bouts.append(row)
    per_animal=[]
    for fly,measures in sorted(animal.items()):
        rows=[r for r in bouts if r['fly_id']==fly]
        result={'fly_id':fly,'bouts':len(rows),'duration_s':sum(r['duration_s'] for r in rows),'metrics':{}}
        for name,values in measures.items():
            flattened=np.concatenate(values) if values and isinstance(values[0],np.ndarray) else values
            result['metrics'][name]=stats(flattened)
        result['frequency_speed_relationship']={}
        for leg,pairs in cycle_pairs[fly].items():
            pairs=np.asarray(pairs)
            correlation=float(spearmanr(pairs[:,0],pairs[:,1]).statistic) if len(pairs)>=6 and np.ptp(pairs[:,1])>0 else None
            bins=[]
            for low,high in zip((0,5,10,15,20,25,30,40),(5,10,15,20,25,30,40,100)):
                selected=pairs[(pairs[:,0]>=low)&(pairs[:,0]<high),1]
                bins.append({'speed_bin_mm_s':[low,high],'cycle_frequency_hz':stats(selected)})
            result['frequency_speed_relationship'][leg]={'cycles':len(pairs),'spearman_rho':correlation,'bins':bins}
        per_animal.append(result)
    keys=sorted(set(k for a in per_animal for k in a['metrics']))
    equal_weight={key:stats([a['metrics'][key]['median'] for a in per_animal if a['metrics'].get(key,{}).get('median') is not None]) for key in keys}
    # Select identifiers only, never export source arrays. Quality thresholds
    # are recorded and do not filter any of the pooled descriptive summaries.
    clean=[r for r in bouts if r['duration_s']>=.4 and r['max_scalar_joint_step_deg']<30
           and r['max_orientation_step_deg']<10 and all(r['legs'][leg]['cycles']>=2 for leg in LEGS)]
    clean.sort(key=lambda row:row['metrics']['model_root_speed_mm_s']['median'])
    selected=[]
    for fraction in (.1,.5,.9):
        if clean:
            candidate=clean[round(fraction*(len(clean)-1))]
            selected.append({'selection_quantile':fraction,'bout':candidate['bout'],'fly_id':candidate['fly_id'],
                             'duration_s':candidate['duration_s'],'median_model_speed_mm_s':candidate['metrics']['model_root_speed_mm_s']['median']})
    return {'source':str(SOURCE),'source_sha256':SHA256,'source_code_commit':COMMIT,
            'xml_sha256':digest(XML),'xml_url':XML_URL,'data_license':'not identified; no raw trajectory export',
            'source_doi':'10.64898/2026.05.03.722293','sample_rate_hz':800,
            'method':'N-1 native forward-difference intervals; quaternion log; scalar joint derivatives; raw tip Hilbert phase sigma=6 frames; four-sigma boundary trim',
            'length_conversions':{'qpos_model_to_mm':10,'raw_keypoints_to_mm':.1},
            'joint_mapping':mapping,'summary':{'bouts':len(bouts),'animals':len(per_animal),'duration_s':sum(r['duration_s'] for r in bouts),
            'total_leg_cycles':sum(r['legs'][leg]['cycles'] for r in bouts for leg in LEGS),'clean_selection_candidates':len(clean)},
            'between_animal_distribution_of_within_animal_medians':equal_weight,
            'between_animal_frequency_speed_spearman':{leg:stats([a['frequency_speed_relationship'][leg]['spearman_rho'] for a in per_animal if a['frequency_speed_relationship'][leg]['spearman_rho'] is not None]) for leg in LEGS},
            'selected_bout_identifiers_only':selected,'per_animal':per_animal,'bouts':bouts,
            'claim_ceiling':'Curated mixed-sex running bouts above source selection threshold; not male-specific, not unselected behavior or exact paper reproduction. Compound joint angles require retargeting before motor use.'}


def compare_simulation(seconds=1.5):
    from fruitfly.body import BodyRuntime
    from fruitfly.simulation import SimulationRunner
    output=[]
    for assay in ('controller_only','motor_probe'):
        for seed in (11,12):
            cfg={'assay':assay,'seed':seed,'probe_hz':40,'enable_taste':False,
                 'sensory_parameters':{'odor_baseline_hz':0,'odor_max_increment_hz':0},
                 'body':{'arena_half_size_mm':40,'initial_position_mm':(-12,0,.8),
                         'food_position_mm':(-25,25),'water_position_mm':(25,25)}}
            runner=None
            if assay=='motor_probe':
                runner=SimulationRunner(cfg)
                body=runner.body
            else:
                body=BodyRuntime(seed=seed,config=cfg['body'])
            try:
                qpos,tip,angles,drive,rate,behavior=[],[],[],[],[],[]
                def record():
                    qpos.append(np.r_[body.data.xpos[body._thorax_id],body.data.xquat[body._thorax_id]])
                    tip.append(body.data.xpos[body._tarsus5_ids].copy())
                    angles.append(np.column_stack([body.data.qpos[body._proprio_joint_qpos[name]] for name in ('coxa_pitch','femur_pitch','tibia_pitch')]))
                record()
                for _ in range(round(seconds/.005)):
                    if runner:
                        state=runner.advance(.005)
                        drive.append([state['motor']['left'],state['motor']['right']])
                        rate.append(state['neural']['output_rates']['forward'])
                        behavior.append(state['behavior'])
                    else:
                        body.advance(.005,behavior='walk',drive_left=1,drive_right=1)
                        drive.append([1.,1.]);behavior.append('walk')
                    record()
                # Exclude declared startup, not a data-driven steady-state fit.
                begin=round(.3/.005)
                qpos=np.asarray(qpos)[begin:];tip=np.asarray(tip)[begin:];angles=np.asarray(angles)[begin:]
                k=native_kinematics(qpos,200,1)
                row={'assay':assay,'seed':seed,'duration_s':seconds,'startup_excluded_s':.3,
                     'sample_rate_hz':200,'config':cfg,'run_dir':str(runner.run_dir) if runner else None,'walking_fraction':float(np.mean(np.asarray(behavior[begin:])=='walk')),
                     'model_root_speed_mm_s':stats(k['speed_xy_mm_s']),
                     'net_heading_rate_deg_s':float(np.rad2deg(k['heading_rad'][-1]-k['heading_rad'][0])/((len(qpos)-1)/200)),
                     'absolute_turn_deg_s':stats(np.rad2deg(np.abs(np.diff(gaussian_filter1d(k['heading_rad'],sigma=6*200/800,mode='reflect'))*200))),
                     'absolute_turn_unsmoothed_deg_s':stats(np.rad2deg(np.abs(k['turn_rad_s']))),
                     'drive':np.mean(drive[begin:],axis=0).tolist(),'DNg97_readout_hz':stats(rate[begin:]),
                     'legs':{},'cpg_frequencies_hz':body.controller.cpg_network.intrinsic_freqs.tolist()}
                for li,leg in enumerate(LEGS):
                    cycles,quality=leg_cycles(tip[:,li],200)
                    row['legs'][leg]={'cycles':len(cycles),'frequency_hz':stats([200/(b-a) for a,b in cycles]),
                        'quality':quality,'joint_rom_deg':{joint:stats([float(np.rad2deg(np.ptp(angles[a:b+1,li,ji]))) for a,b in cycles])
                        for ji,joint in enumerate(('coxa','femur','tibia'))}}
                output.append(row)
                print(assay,seed,row['model_root_speed_mm_s']['median'],flush=True)
            finally:
                if runner: runner.close()
                else: body.close()
    return output


def plot(report,output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(10,8),layout='constrained')
    keys=('model_root_speed_mm_s','absolute_turn_deg_s','LF_frequency_hz','LF_tibia_rom_deg')
    labels=('Root speed (model-normalized mm/s)','Absolute heading rate (degrees/s)',
            'Left foreleg cycle frequency (Hz)','Left tibia flexion ROM per cycle (degrees)')
    for axis,key,label in zip(axes.flat,keys,labels):
        values=[a['metrics'][key]['median'] for a in report['per_animal']]
        axis.scatter(np.ones(len(values)),values,s=22,alpha=.7,label='One median per source animal')
        axis.boxplot(values,positions=[1],widths=.25,showfliers=False)
        for i,s in enumerate(report.get('simulation_comparison',[])):
            if key in s: v=s[key]['median']
            elif key=='LF_frequency_hz': v=s['legs']['LF']['frequency_hz']['median']
            else: v=s['legs']['LF']['joint_rom_deg']['tibia']['median']
            axis.scatter(2 if s['assay']=='controller_only' else 3,v,marker='x',s=75,color='tab:orange' if s['assay']=='controller_only' else 'tab:red')
        axis.set_xticks([1,2,3],['Mixed-sex\nsource animals','CPG\nseeds 11/12','Direct DNg97\nseeds 11/12'])
        axis.set_ylabel(label);axis.grid(alpha=.15)
    fig.suptitle('Curated running benchmark — summaries, no male-specific calibration')
    fig.savefig(output,dpi=160)
    plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-simulation',action='store_true')
    parser.add_argument('--output',type=Path,default=Path('validation/freewalking-benchmark.json'))
    args=parser.parse_args()
    result=source_analysis()
    if args.include_simulation: result['simulation_comparison']=compare_simulation()
    result['script_sha256']=digest(Path(__file__))
    result['body_code_sha256']=digest(Path('fruitfly/body.py'))
    result['dependencies']={name:version(name) for name in ('numpy','scipy','h5py','mujoco','flygym')}
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    plot(result,args.output.with_suffix('.png'))
    print(json.dumps(result['summary'],indent=2))
    print(json.dumps({k:v for k,v in result['between_animal_distribution_of_within_animal_medians'].items() if k in
        ('model_root_speed_mm_s','raw_scutellum_speed_mm_s','absolute_turn_deg_s','LF_frequency_hz','LF_tibia_rom_deg')},indent=2))

if __name__=='__main__': main()
