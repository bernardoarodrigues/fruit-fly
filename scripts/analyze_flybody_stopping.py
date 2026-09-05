"""Post hoc read-only stopping diagnostics; never changes the frozen decision."""
import json
from pathlib import Path
import numpy as np
from scripts.benchmark_freewalking import digest, stats, leg_cycles, LEGS
from scripts.compare_flybody_motor import analyze_window


def summarize(row, start, stop):
    raw=dict(np.load(row['trace']))
    assert digest(row['trace'])==row['trace_sha256']
    sl=slice(round(start/.002),round(stop/.002)+1)
    pose=raw['pose'][sl];support=raw['support_dyne'][sl]
    motion=analyze_window(raw,start,stop)
    motion['planar_path_length_mm']=float(np.linalg.norm(np.diff(pose[:,:2],axis=0),axis=1).sum()*10)
    motion['xy_extent_mm']=(np.ptp(pose[:,:2],axis=0)*10).tolist()
    legs={}
    for li,leg in enumerate(LEGS):
        contact=support[:,li]>1e-8
        change=np.diff(contact.astype(int));onsets=np.flatnonzero(change==1)+1;off=np.flatnonzero(change==-1)+1
        padded=np.r_[False,contact,False].astype(int)
        run_lengths=np.flatnonzero(np.diff(padded)==-1)-np.flatnonzero(np.diff(padded)==1)
        tips=raw['tips_mm'][sl,li]
        candidates,quality=leg_cycles(tips,500)
        legs[leg]={'actual_positive_floor_contact_fraction':float(contact.mean()),
            'contact_onsets':int(len(onsets)),'contact_offsets':int(len(off)),
            'contact_onsets_per_s':float(len(onsets)/(stop-start)),
            'positive_contact_run_lengths_samples':stats(run_lengths),
            'inter_contact_onset_frequency_hz':stats(500/np.diff(onsets)) if len(onsets)>1 else stats([]),
            'tip_xyz_extent_mm':np.ptp(tips,axis=0).tolist(),
            'tip_speed_mm_s':stats(np.linalg.norm(np.diff(tips,axis=0),axis=1)*500),
            'tibia_whole_window_rom_deg':float(np.rad2deg(np.ptp(raw['tibia_rad'][sl,li]))),
            'hilbert_candidates_not_validated_steps':len(candidates),
            'hilbert_candidate_frequency_hz':stats([500/(b-a) for a,b in candidates]),
            'hilbert_quality':quality}
    return {'case':row['case'],'seed':row['seed'],'window_s':[start,stop],
            'trace_sha256':row['trace_sha256'],'motion':motion,'legs':legs,
            'supporting_legs_count':stats((support>1e-8).sum(axis=1))}


def main():
    path=Path('validation/flybody-motor-comparison.json');report=json.loads(path.read_text())
    windows=[('zero',.3,1.5),('withdraw20',.3,.75),('withdraw20',1.,1.5)]
    out={'analysis_kind':'Post hoc diagnostics of existing frozen traces; no new physics, fit, thresholds or promotion decision.',
        'script_sha256':digest(__file__),'comparison_sha256':digest(path),
        'contact_threshold_dyne':1e-8,'contact_definition':'Actual positive leg-floor vertical force on any named leg geom, from detached-state mj_forward; sampled500Hz.',
        'cadence_caveat':'Contact onset rate is a contact-state diagnostic, not a validated step frequency. Hilbert candidate cycles on low-amplitude nonwalking motion must not be counted as biological steps.',
        'windows':[summarize(next(t for t in report['trials'] if t['case']==name and t['seed']==11),a,b) for name,a,b in windows],
        'seed_12_duplicate_physics':report['seed_pairs_identical_physics'],
        'unchanged_decisions':report['decisions']}
    target=Path('validation/flybody-stopping-diagnostics.json');target.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    for row in out['windows']:
        print(row['case'],row['window_s'], 'speed median/p95',row['motion']['speed_mm_s']['median'],row['motion']['speed_mm_s']['p95'])
        print('legs',[(leg,d['contact_onsets'],d['contact_offsets'],round(d['actual_positive_floor_contact_fraction'],3),round(d['tibia_whole_window_rom_deg'],3),d['hilbert_candidates_not_validated_steps']) for leg,d in row['legs'].items()])


if __name__=='__main__':main()
