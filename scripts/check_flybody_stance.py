"""Verify frozen stance traces, exact motor mute, and baseline prefix identity."""
import json
from pathlib import Path
import numpy as np
from scripts.experiment_flybody_stance import PLAN, RESULT, AUDIT, capture_hold, enabled
from scripts.compare_flybody_motor import analyze_window
from scripts.benchmark_freewalking import digest


def main():
    plan=json.loads(PLAN.read_text());report=json.loads(RESULT.read_text())
    assert report['complete'] and report['plan_sha256']==digest(PLAN)
    assert report['script_sha256']==plan['script_sha256']==digest('scripts/experiment_flybody_stance.py')
    paths=[(AUDIT,'actuator_audit_sha256'),('scripts/compare_flybody_motor.py','comparison_script_sha256'),
        ('scripts/benchmark_freewalking.py','metrics_script_sha256'),('validation/flybody-motor-comparison.json','baseline_results_sha256'),
        ('validation/flybody-source-manifest.json','source_manifest_sha256'),('validation/flybody-walking-acquisition.json','policy_receipt_sha256'),
        ('validation/flybody-inference-requirements.lock','requirements_lock_sha256')]
    for p,key in paths:assert digest(p)==plan[key],p
    assert len(report['trials'])==12
    assert {(r['variant'],r['assay']) for r in report['trials']}=={(v,a) for v in plan['variants'] for a in plan['assays']}
    spec=json.loads(Path('validation/flybody-inference-probe.json').read_text())['action_spec']
    lo,hi=np.asarray(spec['minimum'],np.float32),np.asarray(spec['maximum'],np.float32)
    raw_by_key={};checks=[]
    for row in report['trials']:
        assert digest(row['trace'])==row['trace_sha256']
        raw=dict(np.load(row['trace']));raw_by_key[(row['variant'],row['assay'])]=raw
        if 'failure' in row:
            checks.append({'variant':row['variant'],'assay':row['assay'],'preserved_failure':row['failure']})
            continue
        assert raw['pose'].shape==(1001,7) and raw['native_action'].shape==(1000,59)
        assert all(np.isfinite(a).all() for a in raw.values())
        expected_gate=np.asarray([enabled(row['assay'],i*.002) for i in range(1000)])
        np.testing.assert_array_equal(expected_gate,raw['motor_enabled'])
        np.testing.assert_allclose(np.diff(raw['target_pose'][:,:3],axis=0)[:,0]*10,expected_gate[:-1]*20*.002,atol=1e-10,rtol=0)
        np.testing.assert_allclose(np.diff(raw['target_pose'][:,1:3],axis=0),0,atol=1e-15)
        policy_native=lo+np.float32(.5)*(np.clip(raw['shadow_canonical'],-1,1)+1)*(hi-lo)
        used=expected_gate if row['variant']!='policy_zero' else np.ones(1000,bool)
        np.testing.assert_array_equal(raw['native_action'][used],policy_native[used])
        if row['variant']!='policy_zero':
            capture=row['captures'][0];idx=round(capture['time_s']/.002)
            assert idx==(0 if row['assay']=='zero_start' else 300)
            last=raw['native_action'][idx-1] if idx else np.zeros(59)
            lengths=raw['actuator_length'][idx]
            np.testing.assert_array_equal(last,capture['last_native'])
            np.testing.assert_array_equal(lengths,capture['measured_length'])
            held,unclipped=capture_hold(row['variant'],last,lengths,lo,hi)
            np.testing.assert_array_equal(held,np.asarray(capture['native'],np.float32))
            np.testing.assert_array_equal(unclipped,capture['unclipped'])
            np.testing.assert_array_equal(raw['native_action'][~expected_gate],np.tile(held,(np.count_nonzero(~expected_gate),1)))
            assert row['locomotor_policy_mute_pass']
            assert np.array_equal(held[:6],np.ones(6))
            assert row['off_native_action_range_max']==0
        for name,(a,b) in plan['windows'][row['assay']].items():
            for key,value in analyze_window(raw,a,b).items():assert row['windows'][name][key]==value
            window=row['windows'][name]
            if name=='stop':passed=window['speed_mm_s']['median']<=1 and window['net_displacement_mm']<=.5
            else:passed=16<=window['speed_mm_s']['median']<=24 and window['absolute_yaw_deg_s']['median']<=plan['rules']['resume_absolute_yaw_ceiling_deg_s']
            assert window['pass']==passed
        p=row['physical'];support=raw['support_dyne'][150:]
        assert p['min_up_z']==raw['up_z'][150:].min()
        assert p['min_height_mm']==raw['pose'][150:,2].min()*10
        assert p['unsupported_fraction']==np.mean(support.max(axis=1)<=1e-8)
        passed=p['finite'] and p['min_up_z']>=.5 and p['min_height_mm']>=.5 and p['unsupported_fraction']<=.01 and not any(p['warnings'])
        assert row['physical_pass']==passed
        checks.append({'variant':row['variant'],'assay':row['assay'],'metrics_and_motor_gate_verified':True,'trace_sha256':row['trace_sha256']})
    original=json.loads(Path('validation/flybody-motor-comparison.json').read_text())
    baseline_identity={}
    for assay,source in [('zero_start','zero'),('walk_stop','straight20'),('walk_stop_resume','straight20')]:
        old=dict(np.load(next(r for r in original['trials'] if r['case']==source and r['seed']==11)['trace']))
        n=751 if assay=='zero_start' else 301
        current=raw_by_key[('policy_zero',assay)]
        baseline_identity[assay]=all(np.array_equal(old[k][:n],current[k][:n]) for k in ['pose','tips_mm','tibia_rad'])
        assert baseline_identity[assay]
    prefix_identity={}
    for variant in plan['variants']:
        a=raw_by_key[(variant,'walk_stop')];b=raw_by_key[(variant,'walk_stop_resume')]
        prefix_identity[variant]=np.array_equal(a['pose'][:601],b['pose'][:601])
        assert prefix_identity[variant],variant
        if variant!='policy_zero':
            for assay in ['walk_stop','walk_stop_resume']:
                np.testing.assert_array_equal(raw_by_key[(variant,assay)]['pose'][:301],raw_by_key[('policy_zero',assay)]['pose'][:301])
    for decision in report['decisions']:
        rows=[r for r in report['trials'] if r['variant']==decision['variant']]
        passed=all('failure' not in r and r['physical_pass'] and all(w['pass'] for w in r['windows'].values()) and r['locomotor_policy_mute_pass'] is True for r in rows)
        assert decision['all_declared_gates_pass']==passed and not decision['runtime_promoted']
    result={'passed':True,'plan_sha256':digest(PLAN),'results_sha256':digest(RESULT),'checker_sha256':digest(__file__),
        'trials':checks,'original_baseline_physics_prefixes_bitwise_identical':baseline_identity,
        'stop_and_resume_assays_identical_until_resume_edge':prefix_identity,
        'all_hold_actions_exact':True,'runtime_changed':False}
    out=Path('validation/flybody-stance-validation.json');out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'passed':True,'trials':len(checks),'receipt':str(out)},indent=2))


if __name__=='__main__':main()
