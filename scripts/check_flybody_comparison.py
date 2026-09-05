"""Recompute fixed FlyBody comparison metrics from the generated physics traces."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.compare_flybody_motor import (
    PLAN, RESULT, BENCHMARK, CPG, LEGS, analyze_window, decide, digest,
    leg_cycles, stats,
)


def main():
    plan = json.loads(PLAN.read_text())
    report = json.loads(RESULT.read_text())
    assert report['complete']
    assert report['plan_sha256'] == digest(PLAN)
    assert report['script_sha256'] == plan['script_sha256'] == digest('scripts/compare_flybody_motor.py')
    for path, key in [(BENCHMARK, 'benchmark_sha256'), (CPG, 'cpg_results_sha256'),
                      ('scripts/benchmark_freewalking.py', 'metrics_script_sha256'),
                      ('validation/flybody-source-manifest.json', 'source_manifest_sha256'),
                      ('validation/flybody-walking-acquisition.json', 'policy_receipt_sha256'),
                      ('validation/flybody-inference-requirements.lock', 'requirements_lock_sha256')]:
        assert digest(path) == plan[key], path
    expected = {(c['name'], seed) for c in plan['cases'] for seed in plan['seeds']}
    assert {(r['case'], r['seed']) for r in report['trials']} == expected
    assert len(report['trials']) == len(expected) == 12
    spec = json.loads(Path('validation/flybody-inference-probe.json').read_text())['action_spec']
    lo, hi = np.asarray(spec['minimum'], np.float32), np.asarray(spec['maximum'], np.float32)
    diagnostics = []
    for row in report['trials']:
        assert 'failure' not in row, row
        assert digest(row['trace']) == row['trace_sha256']
        raw = dict(np.load(row['trace']))
        assert all(np.isfinite(a).all() for a in raw.values())
        assert raw['pose'].shape == (751, 7)
        assert raw['tips_mm'].shape == (751, 6, 3)
        assert raw['canonical_action'].shape == (750, 59)
        assert row['physical_trace_sha256'] == hashlib.sha256(b''.join(
            raw[k].tobytes() for k in ['pose', 'tibia_rad', 'tips_mm'])).hexdigest()
        scaled = lo + np.float32(.5) * (np.clip(raw['canonical_action'], -1, 1) + 1) * (hi - lo)
        np.testing.assert_array_equal(scaled, raw['native_action'])
        case = next(c for c in plan['cases'] if c['name'] == row['case'])
        command = np.broadcast_to([case['speed_mm_s'], case['yaw_rad_s']], (750, 2)).copy()
        if 'withdraw_at_s' in case:
            command[375:] = 0
            assert row['first_zero_command_s'] == .75
            np.testing.assert_array_equal(raw['target_pose'][375:], np.tile(raw['target_pose'][375], (375, 1)))
            assert row['before_withdrawal'] == analyze_window(raw, .3, .75)
            assert row['after_withdrawal'] == analyze_window(raw, 1., 1.5)
        np.testing.assert_array_equal(command, raw['command'])
        distance = np.linalg.norm(np.diff(raw['target_pose'][:, :2], axis=0), axis=1) * 10
        np.testing.assert_allclose(distance, command[:-1, 0] * .002, atol=1e-10, rtol=0)
        heading = np.unwrap(2*np.arctan2(raw['target_pose'][:, 6], raw['target_pose'][:, 3]))
        np.testing.assert_allclose(np.diff(heading), command[:-1, 1]*.002, atol=1e-10, rtol=0)
        for key, value in analyze_window(raw, .3, 1.5).items():
            assert row[key] == value, (row['case'], key)
        stop = .75 if 'withdraw_at_s' in case else 1.5
        window = slice(150, round(stop/.002)+1)
        for i, leg in enumerate(LEGS):
            cycles, _ = leg_cycles(raw['tips_mm'][window, i], 500) if case['speed_mm_s'] else ([], {})
            assert row['legs'][leg]['cycles'] == len(cycles)
            assert row['legs'][leg]['frequency_hz'] == stats([500/(b-a) for a,b in cycles])
            rom = stats([float(np.rad2deg(np.ptp(raw['tibia_rad'][window, i][a:b+1]))) for a,b in cycles])
            assert row['legs'][leg]['tibia_rom_deg'] == rom
        finite = all(np.isfinite(a).all() for a in raw.values())
        support = raw['support_dyne'][150:]
        physical = row['physical']
        assert physical['finite'] == finite
        assert physical['support_over_weight_mean'] == float(support.sum(axis=1).mean()/physical['body_weight_dyne'])
        assert physical['no_leg_support_fraction'] == float(np.mean(support.max(axis=1)<=1e-8))
        assert row['canonical_clipped_fraction'] == float(np.mean(abs(raw['canonical_action'][150:])>1))
        diagnostics.append({'case': row['case'], 'seed': row['seed'],
            'trace_sha256': row['trace_sha256'], 'metrics_reproduced': True})
    assert report['decisions'] == decide(plan, report['trials'])
    old = plan['reporting_amendment']
    assert digest(old['original_plan_path']) == old['original_plan_sha256']
    original = dict(np.load(old['first_failed_attempt']))
    assert digest(old['first_failed_attempt']) == old['first_attempt_trace_sha256']
    current = dict(np.load(report['trials'][0]['trace']))
    nonphysical = {'support_dyne', 'ground_contact_count'}
    same = {key: np.array_equal(original[key], current[key]) for key in original if key not in nonphysical}
    assert all(same.values()), same
    receipt = {'passed': True, 'plan_sha256': digest(PLAN), 'results_sha256': digest(RESULT),
        'checker_sha256': digest(__file__), 'trials': diagnostics,
        'diagnostic_fix_preserved_every_nondiagnostic_trace_array': same,
        'diagnostic_fix_caveat': 'Original contact-force array intentionally not reused: stale constraint-force cache.',
        'decisions_reproduced': True, 'full_neural_integration': False}
    path = Path('validation/flybody-motor-comparison-validation.json')
    path.write_text(json.dumps(receipt, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'passed': True, 'trials': len(diagnostics), 'receipt': str(path)}, indent=2))


if __name__ == '__main__':
    main()
