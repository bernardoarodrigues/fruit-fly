"""Predeclared rolling-reference parity and >10 s source-native experiments."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

for key, value in {'TF_CPP_MIN_LOG_LEVEL': '2', 'CUDA_VISIBLE_DEVICES': '-1',
                   'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'}.items():
    os.environ[key] = value
import numpy as np

PLAN = Path('validation/flybody-persistent-plan.json')
RESULT = Path('validation/flybody-persistent-experiment.json')
SOURCE = Path('data/raw/flybody/source').resolve()
FILES = ['scripts/flybody_persistent_task.py', 'scripts/experiment_flybody_persistent.py',
         'fruitfly/flybody_worker.py', 'validation/flybody-source-manifest.json',
         'validation/flybody-walking-acquisition.json', 'validation/flybody-stance-actuator-audit.json',
         'validation/flybody-inference-requirements.lock']
CASES = ['bounded_parity', 'rolling_parity', 'rolling_rest12', 'rolling_switch12']
CONFIG = dict(source_path=str(SOURCE), width=800, height=560,
              food_position_mm=[6., 0.], food_radius_mm=3.,
              water_position_mm=[5., 7.], water_radius_mm=2.)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_plan():
    return dict(created_at=datetime.now(timezone.utc).isoformat(),
        files={path: digest(path) for path in FILES}, config=CONFIG, seed=11,
        cases=CASES, control_dt_s=.002, physics_dt_s=.0002,
        parity={'duration_s': 2., 'schedule': 'walk 0-.6 s, rest .6-1.2 s, walk 1.2-2 s; on-speed 20 mm/s, yaw 0',
                'gate': 'Bitwise equality of all actual float32 actor inputs, mean/native actions, qpos/qvel/qacc/act/ctrl, target and native clock against untouched bounded worker.',
                'cached_reference': 'Compare separately: first 64 post-step rows must match. Last cached row may differ because rolling fills it causally; next actor refresh must replace it before inference.'},
        long_schedules={'rolling_rest12': 'rest for 12 s',
            'rolling_switch12': 'walk [0,.6),[1.2,3),[3.6,6),[6.6,9),[10.6,12); rest otherwise. On-speed 20 mm/s, yaw 0.'},
        guards={'linear_cm_s': 50., 'angular_rad_s': 200., 'reference_error_cm': .3, 'qacc_norm_mixed_units': 1e14,
                'check': 'Original source guard equations and strict > thresholds. At reset compare isolated above-threshold diagnostic injections on source and rolling tasks, restoring each array. No injected state enters rollout.'},
        long_gates={'completion': '6000 uninterrupted control ticks / 60000 native physics steps. No LAST, reset, target recenter, pose/velocity clamp, physical-guard relaxation or finite-reference cutoff.',
             'physical': 'All sampled native qpos/qvel/qacc/act/ctrl/forces finite and warnings zero; native time and task counter agree within 1e-10 s.',
             'storage': 'Reference qpos(66,7), qvel(66,6) throughout; every actual actor still gets 65 reference rows / 741 total values.',
             'stop': 'Every stop window [.85,1.2],[3.25,3.6],[6.25,6.6],[9.25,10.6] s median raw root speed <=1 mm/s and net displacement <=.5 mm.',
             'resume': 'Each resumed walking window [1.5,3],[3.9,6],[6.9,9],[10.9,12] s median raw root speed 16-24 mm/s.',
             'stance': 'Every off action has original native adhesion 1 and all 53 position targets 0; unchanged learned weights, body, filters, gains, clocks.'},
        limitations=['Two chosen deterministic 12 s schedules, one seed, flat source floor; no reliability population, biological stance, turning or full-brain claim.',
                      'Task initialization still creates original finite static trajectory-site visualization. Those sites are not policy inputs and are not an updated persistent path display.',
                      'Finite/warnings diagnostics are sampled each 2 ms, not recorded each .2 ms substep; preserve any native exception and its true partial state.'],
        scope='Standalone prototype only; no runtime promotion or edits to bounded worker/bridge.')


def command(case, tick):
    if case == 'rolling_rest12':
        on = False
    elif case.endswith('parity'):
        on = tick < 300 or tick >= 600
    else:
        on = any(a <= tick < b for a, b in [(0, 300), (600, 1500), (1800, 3000), (3300, 4500), (5300, 6000)])
    return (20., 0., 'walk') if on else (0., 0., 'rest')


def worker_class(rolling):
    from fruitfly.flybody_worker import Worker
    class ObservedWorker(Worker):
        def _policy(self, observation):
            self.actor_keys = list(observation)
            self.actor_shapes = {k: list(np.asarray(v).shape) for k, v in observation.items()}
            self.actor_values = np.concatenate([np.asarray(v, np.float32).ravel() for v in observation.values()])
            return super()._policy(observation)
    if not rolling:
        return ObservedWorker
    sys.path.insert(0, str(SOURCE))
    from scripts.flybody_persistent_task import rolling_walk_imitation
    from unittest.mock import patch
    class RollingWorker(ObservedWorker):
        def reset(self, seed):
            # Local experiment-only factory injection; the saved worker file and
            # installed source are untouched, and the patch ends after reset.
            with patch('flybody.fly_envs.walk_imitation', rolling_walk_imitation):
                return super().reset(seed)

        def advance(self, speed_mm_s, yaw_rad_s, behavior):
            if self.failed:
                raise RuntimeError('Source task failed; reset explicitly before advancing')
            if behavior not in ('walk', 'rest', 'feed'):
                raise ValueError('Unsupported behavior')
            if not math.isfinite(speed_mm_s) or not 0 <= speed_mm_s <= 20 or not math.isfinite(yaw_rad_s) or abs(yaw_rad_s) > 2:
                raise ValueError('Invalid bounded motor command')
            on = behavior == 'walk'
            if not on:
                speed_mm_s = yaw_rad_s = 0.
            self.command = dict(speed_mm_s=speed_mm_s, yaw_rad_s=yaw_rad_s, policy_enabled=on, behavior=behavior)
            from flybody.tasks.synthetic_trajectories import constant_speed_trajectory
            heading = 2 * np.arctan2(self.target[6], self.target[3])
            preview, velocity = constant_speed_trajectory(66, speed=speed_mm_s / 10,
                yaw_speed=yaw_rad_s, init_pos=self.target[:3], init_heading=heading)
            velocity[:, 3:] = [0, 0, yaw_rad_s]
            self.env.task.install_preview(preview, velocity, self.tick)
            observation = dict(self.step_result.observation)
            for key in ('walker/ref_displacement', 'walker/ref_root_quat'):
                observation[key] = self.env.task.observables[key](self.env.physics)
            self.canonical = self._policy(observation)
            if on:
                self.native = self.lo + np.float32(.5) * (np.clip(self.canonical, -1, 1) + 1) * (self.hi - self.lo)
            else:
                self.native = np.zeros(59, np.float32)
                self.native[:6] = 1
            self.target = preview[1].copy()
            try:
                self.step_result = self.env.step(self.native.copy())
            except BaseException:
                self.failed = True
                self.tick = int(round(float(self.d.time) / .002))
                self.state = self.collect()
                raise
            self.tick += 1
            self.state = self.collect()
            if not self.state['finite'] or self.state['source_terminated']:
                self.failed = True
                raise RuntimeError('Source physical failure at tick ' + str(self.tick))
            return self.state
    return RollingWorker


def guard_probe(worker):
    task, physics = worker.env.task, worker.env.physics
    qacc = worker.d.qacc.copy()
    sensors = worker.d.sensordata.copy()
    reference = task._ref_qpos.copy()
    reached = getattr(task, '_reached_traj_end', None)
    answers = {}
    try:
        answers['baseline'] = bool(task.check_termination(physics))
        for name, threshold in [('qacc', 1e14), ('velocimeter', 50.), ('gyro', 200.), ('reference', .3)]:
            worker.d.qacc[:] = qacc
            worker.d.sensordata[:] = sensors
            task._ref_qpos[:] = reference
            if name == 'qacc':
                worker.d.qacc[:] = 0
                worker.d.qacc[0] = threshold * 1.01
            elif name == 'reference':
                task._ref_qpos[0, 0] += threshold * 1.01
            else:
                physics.named.data.sensordata['walker/' + name] = [threshold * 1.01, 0, 0]
            answers[name + '_above'] = bool(task.check_termination(physics))
    finally:
        worker.d.qacc[:] = qacc
        worker.d.sensordata[:] = sensors
        task._ref_qpos[:] = reference
        if reached is not None:
            task._reached_traj_end = reached
    return answers


def model_arrays(worker):
    arrays = {}
    for name in dir(worker.m):
        if name.startswith('_'):
            continue
        try:
            value = getattr(worker.m, name)
        except Exception:
            continue
        if isinstance(value, np.ndarray) and value.dtype.kind in 'biuf':
            arrays[name] = dict(shape=list(value.shape), dtype=str(value.dtype),
                sha256=hashlib.sha256(value.tobytes()).hexdigest())
    return arrays


def trial(case, folder):
    plan = json.loads(PLAN.read_text())
    for path, expected in plan['files'].items():
        if digest(path) != expected:
            raise ValueError('Changed after frozen plan: ' + path)
    rolling = case.startswith('rolling')
    count = 1000 if case.endswith('parity') else 6000
    cls = worker_class(rolling)
    worker = cls(CONFIG, 11)
    fields = ['native_time_s', 'tick', 'qpos', 'qvel', 'qacc', 'act', 'ctrl',
              'native_action', 'canonical_action', 'target_pose_cm_quat', 'pose_cm_quat',
              'velocity_world_mm_s', 'angular_velocity_world_rad_s', 'up_z', 'warnings',
              'finite', 'source_terminated']
    raw = {key: [] for key in fields}
    raw.update(actor=[], cached_displacement=[], cached_quaternion=[],
               reference_error_cm=[], source_linvel_cm_s=[], source_angvel_rad_s=[],
               task_counter=[], ref_shape=[], command_on=[])
    failure = None
    guards = guard_probe(worker)
    model = model_arrays(worker)
    def record():
        for key in fields:
            raw[key].append(worker.state[key])
        raw['actor'].append(worker.actor_values.copy())
        obs = worker.step_result.observation
        raw['cached_displacement'].append(obs['walker/ref_displacement'].copy())
        raw['cached_quaternion'].append(obs['walker/ref_root_quat'].copy())
        task = worker.env.task
        raw['reference_error_cm'].append(float(np.linalg.norm(task.observables['walker/ref_displacement'](worker.env.physics)[0])))
        raw['source_linvel_cm_s'].append(float(np.linalg.norm(task.walker.observables.velocimeter(worker.env.physics))))
        raw['source_angvel_rad_s'].append(float(np.linalg.norm(task.walker.observables.gyro(worker.env.physics))))
        raw['task_counter'].append(task._step_counter)
        raw['ref_shape'].append(task._ref_qpos.shape)
        raw['command_on'].append(worker.command['policy_enabled'])
    record()
    start = time.perf_counter()
    try:
        for tick in range(count):
            worker.advance(*command(case, tick))
            record()
            if (tick + 1) % 1000 == 0:
                print(case, tick + 1, 'native_time', worker.d.time, 'ref_error_cm', raw['reference_error_cm'][-1], flush=True)
    except Exception as error:
        failure = type(error).__name__ + ': ' + str(error)
        (folder / (case + '-failure.txt')).write_text(traceback.format_exc())
        if len(raw['tick']) == 1 or raw['native_time_s'][-1] != worker.state['native_time_s']:
            record()
    wall = time.perf_counter() - start
    raw = {key: np.asarray(value) for key, value in raw.items()}
    trace = folder / (case + '.npz')
    np.savez_compressed(trace, **raw)
    report = dict(case=case, failure=failure, samples=len(raw['tick']),
        trace=str(trace), trace_sha256=digest(trace), actor_keys=worker.actor_keys,
        actor_shapes=worker.actor_shapes, guards=guards, compiled_numeric_arrays=model,
        wall_s=wall, native_time_s=float(worker.d.time), source=worker.provenance,
        composer_time_limit='infinite' if rolling else worker.env._time_limit,
        task_construction_time_limit=worker.env.task._time_limit,
        task_episode_steps=worker.env.task._episode_steps,
        finite=bool(raw['finite'].all()), warnings_max=raw['warnings'].max(axis=0).tolist(),
        max_reference_error_cm=float(raw['reference_error_cm'].max()),
        max_qacc_norm=float(np.linalg.norm(raw['qacc'], axis=1).max()),
        max_source_linvel_cm_s=float(raw['source_linvel_cm_s'].max()),
        max_source_angvel_rad_s=float(raw['source_angvel_rad_s'].max()),
        native_clock_max_error_s=float(np.max(abs(raw['native_time_s'] - raw['task_counter'] * .002))))
    (folder / (case + '.json')).write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    worker.close()
    print(case, 'complete', failure, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan-only', action='store_true')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--trial', choices=CASES)
    parser.add_argument('--folder', type=Path)
    args = parser.parse_args()
    if args.plan_only:
        if PLAN.exists():
            raise FileExistsError('Existing frozen plan')
        PLAN.write_text(json.dumps(make_plan(), indent=2) + '\n')
        print('Saved plan', digest(PLAN))
    elif args.trial:
        trial(args.trial, args.folder)
    elif args.run:
        folder = Path('runs') / ('flybody-persistent-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        folder.mkdir(parents=True)
        reports = []
        for case in CASES:
            with (folder / (case + '.log')).open('w') as log:
                process = subprocess.run([sys.executable, '-m', 'scripts.experiment_flybody_persistent',
                    '--trial', case, '--folder', str(folder)], stdout=log, stderr=subprocess.STDOUT)
            if process.returncode:
                reports.append(dict(case=case, failure='Trial process exit ' + str(process.returncode), log=str(folder / (case + '.log'))))
            else:
                reports.append(json.loads((folder / (case + '.json')).read_text()))
            RESULT.write_text(json.dumps(dict(complete=False, plan_sha256=digest(PLAN), trials=reports), indent=2) + '\n')
            print(case, reports[-1].get('failure'), flush=True)
        RESULT.write_text(json.dumps(dict(complete=True, plan_sha256=digest(PLAN), trials=reports), indent=2) + '\n')
    else:
        parser.error('Choose --plan-only, --run or internal --trial')


if __name__ == '__main__':
    main()
