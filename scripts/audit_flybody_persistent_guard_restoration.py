"""Initialization-only audit of the frozen experiment's guard-probe side effects."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np
from scripts.experiment_flybody_persistent import CONFIG, worker_class, guard_probe, digest


def arrays(owner):
    result = {}
    for name in dir(owner):
        if name.startswith('_'):
            continue
        try:
            value = getattr(owner, name)
        except Exception:
            continue
        if isinstance(value, np.ndarray) and value.dtype.kind in 'biuf':
            result[name] = (list(value.shape), str(value.dtype), hashlib.sha256(value.tobytes()).hexdigest())
    return result


def main():
    rows = []
    for rolling in (False, True):
        worker = worker_class(rolling)(CONFIG, 11)
        task = worker.env.task
        state = worker.collect()
        before = dict(data=arrays(worker.d), model=arrays(worker.m),
            observation={k: np.asarray(v).copy() for k, v in worker.step_result.observation.items()},
            qpos=task._ref_qpos.copy(), qvel=task._ref_qvel.copy(),
            time=float(worker.d.time), counter=task._step_counter,
            should_terminate=task._should_terminate,
            reached_traj_end_present=hasattr(task, '_reached_traj_end'),
            reached_traj_end=getattr(task, '_reached_traj_end', None))
        answers = guard_probe(worker)
        after = dict(data=arrays(worker.d), model=arrays(worker.m),
            time=float(worker.d.time), counter=task._step_counter,
            should_terminate=task._should_terminate,
            reached_traj_end_present=hasattr(task, '_reached_traj_end'),
            reached_traj_end=getattr(task, '_reached_traj_end', None))
        differences = {key: [before[key], after[key]] for key in after
                       if key not in ('data', 'model') and before[key] != after[key]}
        row = dict(rolling=rolling, guards=answers,
            numeric_data_arrays_checked=len(before['data']),
            numeric_model_arrays_checked=len(before['model']),
            data_arrays_identical=before['data'] == after['data'],
            model_arrays_identical=before['model'] == after['model'],
            reference_arrays_identical=np.array_equal(before['qpos'], task._ref_qpos) and np.array_equal(before['qvel'], task._ref_qvel),
            cached_observations_identical=all(np.array_equal(v, worker.step_result.observation[k]) for k, v in before['observation'].items()),
            full_worker_state_identical=state == worker.collect(),
            task_scalar_differences=differences, physics_steps=0)
        rows.append(row)
        worker.close()
    report = dict(script_sha256=digest(__file__),
        experiment_sha256=digest('scripts/experiment_flybody_persistent.py'),
        worker_sha256=digest('fruitfly/flybody_worker.py'),
        task_sha256=digest('scripts/flybody_persistent_task.py'),
        rows=rows, strict_boundary_equivalence_tested=False,
        scope='Initialization-only numerical side-effect audit. No physics step, fitting, new trajectory, or threshold change.')
    path = Path('validation/flybody-persistent-guard-restoration.json')
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
