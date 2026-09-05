"""Check a completed fixed-grid receipt, including frozen-baseline reproduction."""
import inspect
import json
from pathlib import Path

import numpy as np
from flygym_demo.complex_terrain import HybridTurningController
from scripts.benchmark_freewalking import digest, LEGS


def main():
    plan_path=Path('validation/cpg-calibration-plan.json')
    result_path=Path('validation/cpg-calibration-experiment.json')
    plan=json.loads(plan_path.read_text());result=json.loads(result_path.read_text())
    benchmark=json.loads(Path('validation/freewalking-benchmark.json').read_text())
    assert result['plan_sha256']==digest(plan_path)
    assert plan['benchmark_sha256']==digest(Path('validation/freewalking-benchmark.json'))
    assert plan['body_code_sha256']==digest(Path('fruitfly/body.py'))
    assert plan['controller_code_sha256']==digest(Path(inspect.getfile(HybridTurningController)))
    assert plan['script_sha256']==digest(Path('scripts/calibrate_cpg_experiment.py'))
    expected={(v['name'],d,s) for v in plan['variants'] for d in plan['drives'] for s in plan['seeds']}
    actual={(r['variant'],r['drive'],r['seed']) for r in result['trials']}
    assert expected==actual and len(result['trials'])==20
    frame_counts=[]
    for trial in result['trials']:
        assert digest(Path(trial['trace']))==trial['trace_sha256']
        with np.load(trial['trace'],allow_pickle=False) as trace:
            assert all(np.isfinite(trace[key]).all() for key in trace.files)
            assert len(trace['qpos'])==301
            frame_counts.append(len(trace['qpos']))
        assert all(trial['legs'][leg]['cycles']>0 for leg in LEGS)
    baseline_checks=[]
    for seed in plan['seeds']:
        prior=next(r for r in benchmark['simulation_comparison'] if r['assay']=='controller_only' and r['seed']==seed)
        current=next(r for r in result['trials'] if r['variant']=='baseline' and r['drive']==1 and r['seed']==seed)
        error=abs(prior['model_root_speed_mm_s']['median']-current['speed_mm_s']['median'])
        np.testing.assert_allclose(prior['model_root_speed_mm_s']['median'],current['speed_mm_s']['median'],rtol=0,atol=1e-10)
        for leg in LEGS:
            np.testing.assert_allclose(prior['legs'][leg]['joint_rom_deg']['tibia']['median'],current['legs'][leg]['tibia_rom_deg']['median'],rtol=0,atol=1e-10)
        baseline_checks.append({'seed':seed,'speed_difference_mm_s':error,'all_six_tibia_rom_match_atol':1e-10})
    report={'status':'passed','plan_sha256':digest(plan_path),'experiment_sha256':digest(result_path),
            'complete_unique_trials':len(actual),'frame_count_per_simulated_trace':sorted(set(frame_counts)),
            'all_trace_hashes_and_finite_arrays_checked':True,'baseline_reproduction':baseline_checks,
            'runtime_body_and_installed_controller_hashes_unchanged':True,
            'initial_unrun_draft':{'path':'validation/cpg-calibration-plan-v0-unrun.json',
                                 'status':'superseded before any physics execution; broad-bin midpoint corrected'},
            'source_arrays_redistributed':False}
    Path('validation/cpg-calibration-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
