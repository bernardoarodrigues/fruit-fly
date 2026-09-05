#!/usr/bin/env python3
"""Independent selected-spike recount and post-hoc exact MBON-train comparison.

Reads saved extracted timestamps, not the producer's binning function. This does
not repeat its complete raw-chunk integrity audit or execute a neural model.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'validation/navigation-ladder-timing-independent-review.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if OUT.exists():
        raise FileExistsError('Preserve the first independent timing review')
    names = ['scripts/review_navigation_ladder_timing.py',
             'validation/navigation-ladder-timing-plan.json',
             'validation/navigation-ladder-timing-results.json',
             'validation/navigation-ladder-timing-arrays.npz']
    hashes = {n: sha(ROOT/n) for n in names}
    plan = json.loads((ROOT/names[1]).read_text())
    result = json.loads((ROOT/names[2]).read_text())
    checks = []

    def check(name, ok):
        checks.append({'name': name, 'passed': bool(ok)})
        if not ok:
            raise AssertionError(name)

    try:
        check('passed complete producer reduction', result['passed'] and len(result['trials']) == 6)
        check('plan pin', result['plan']['sha256'] == hashes[names[1]])
        with np.load(ROOT/names[3], allow_pickle=False) as archive:
            idx = archive['graph_indices']; lookup = {int(v): i for i, v in enumerate(idx)}
            times_by_trial = {}
            for i, trial in enumerate(result['trials']):
                spec = trial['spec']; name = spec['name']
                events = archive[f"trial_{spec['ordinal']}_spikes"]
                count = np.zeros((120, len(idx)), dtype=np.int64)
                for tick, cell in events:
                    count[int(tick)//250, lookup[int(cell)]] += 1
                check(name+' all selected 25ms counts', np.array_equal(count, archive['counts25'][i]))
                times_by_trial[spec['seed'], spec['condition']] = events.copy()
                for group, definition in plan['cohorts'].items():
                    columns = [lookup[v] for v in definition['indices']]
                    c = count[:, columns].sum(axis=1)
                    observation = trial['cohorts'][group]
                    check(name+' '+group+' counts/rates',
                          c.tolist() == observation['counts25'] and
                          np.array_equal(c/(.025*len(columns)), observation['rates25_hz']) and
                          int(c[20:24].sum()) == observation['early_pulse_count'] and
                          int(c[36:40].sum()) == observation['late_pulse_count'])
                    chosen = events[np.isin(events['index'], definition['indices'])]['tick']
                    check(name+' '+group+' first/last', len(chosen) == observation['whole']['count'] and
                          (int(chosen[0]) if len(chosen) else None) == observation['whole']['first_tick'] and
                          (int(chosen[-1]) if len(chosen) else None) == observation['whole']['last_tick'])
            exact = []
            for seed in [11, 12, 13]:
                ea = times_by_trial[seed, 'ethyl_acetate']; base = times_by_trial[seed, 'constant_baseline']
                for group in ['MBON12', 'MBON13', 'MBON14']:
                    ids = plan['cohorts'][group]['indices']
                    a = ea[np.isin(ea['index'], ids)]; b = base[np.isin(base['index'], ids)]
                    exact.append({'seed': seed, 'cohort': group, 'EA_spikes': len(a), 'constant_spikes': len(b),
                                  'identical_full_recorded_spike_sequence': np.array_equal(a, b),
                                  'EA_packed_sha256': hashlib.sha256(a.tobytes()).hexdigest(),
                                  'constant_packed_sha256': hashlib.sha256(b.tobytes()).hexdigest()})
            check('source inputs unchanged', hashes == {n: sha(ROOT/n) for n in names})
        receipt = {'passed': True, 'checks': checks, 'input_sha256': hashes,
                   'selected_25ms_count_values_recounted': 6*120*len(idx),
                   'posthoc_exact_MBON_comparisons': exact,
                   'scope': 'Recount extracted exact spike records with a scalar loop; check every selected 25ms count and cohort rate/early/late/first/last. Compare whole MBON12/13/14 emitted sequences between matched H1 EA and constant trials. No model or producer import; complete original raw-chunk audit is not repeated here.',
                   'interpretation': 'Identical output sequences imply no recorded spike-output contrast for these cells, this paired stimulus and these three seeds. They do not establish the responsible mechanism, generalize to other stimuli or physiological cells, or exclude unsaved subthreshold changes.'}
    except Exception as e:
        receipt = {'passed': False, 'checks': checks, 'input_sha256': hashes, 'error': repr(e)}
        raise
    finally:
        receipt['completed_utc'] = datetime.now(timezone.utc).isoformat()
        OUT.write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({'passed': True, 'checks': len(checks), 'sha256': sha(OUT),
                      'all_nine_MBON_sequences_identical': all(r['identical_full_recorded_spike_sequence'] for r in exact)}))


if __name__ == '__main__':
    main()
