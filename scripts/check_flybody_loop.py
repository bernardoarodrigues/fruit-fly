"""Predeclared full-MaleCNS/FlyBody locomotor and on-food mechanism assays.

No gain fitting, forced walking outcome, natural behavior or male-body claim.
Every actual ordered drive and completed neural/physical tick is journaled;
partial source failures remain results. Run only after bridge/runner readiness.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import time
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'validation/flybody-loop'
PLAN = OUT / 'plan.json'
RESULT = OUT / 'results.json'
DT = .002
SENSORY_GROUPS = ('odor', 'sweet', 'club')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe(value):
    """Preserve invalid numeric evidence explicitly, never emit invalid JSON."""
    if isinstance(value, np.ndarray):
        return safe(value.tolist())
    if isinstance(value, np.generic):
        return safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return {'nonfinite': repr(value)}
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    return value


def write_json(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(safe(value), indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


class Journal:
    """Flush every event so failures cannot discard a condition's prior ticks."""
    def __init__(self, path):
        self.path = path
        self.stream = path.open('x', buffering=1)
        self.records = 0

    def append(self, event, **payload):
        self.stream.write(json.dumps(safe({'record': self.records, 'event': event, **payload}),
                                     allow_nan=False, separators=(',', ':')) + '\n')
        self.stream.flush()
        self.records += 1

    def close(self):
        self.stream.close()


def drive_record(drive, neuron_ids):
    indices = np.asarray(drive.indices)
    assert indices.ndim == 1 and np.issubdtype(indices.dtype, np.integer)
    n = len(indices)
    def values(value):
        if value is None:
            return None
        array = np.asarray(value, dtype=float)
        if array.ndim == 0:
            array = np.full(n, float(array))
        assert array.shape == (n,)
        return array.tolist()
    result = {'indices': indices.tolist(), 'neuron_ids': neuron_ids[indices].tolist(),
              'rates_hz': values(drive.rates_hz), 'current_mv': values(drive.current_mv),
              'poisson_weight_mv': values(drive.poisson_weight_mv),
              'disable_refractory': drive.disable_refractory}
    raw = json.dumps(result, sort_keys=True, allow_nan=False, separators=(',', ':')).encode()
    result['ordered_drive_sha256'] = hashlib.sha256(raw).hexdigest()
    return result


def spike_record(batch, keep=None):
    if keep is None:
        keep = np.ones(len(batch.indices), dtype=bool)
    ids = np.asarray(batch.neuron_ids[keep], dtype='<i8')
    times = np.asarray(batch.times_ms[keep], dtype='<f8')
    digest = hashlib.sha256(struct.pack('<Q', len(ids)) + ids.tobytes() + times.tobytes()).hexdigest()
    unique, counts = np.unique(ids, return_counts=True)
    return {'spikes': len(ids), 'event_sha256': digest,
            'neuron_ids': unique.tolist(), 'counts': counts.tolist()}


class Capture:
    """Passive wrappers: call each original method exactly once, no extra RNG."""
    def __init__(self, runner, journal):
        self.runner, self.journal = runner, journal
        self.tick = -1
        self.components = []
        self.neural = None
        self.restore = []
        self.sensory_indices = np.unique(np.concatenate([runner._input_group(g) for g in SENSORY_GROUPS]))
        self.monitor_groups = {g: runner._input_group(g) for g in SENSORY_GROUPS}
        self.monitor_groups.update({'motor_' + k: v for k, v in runner.motor.groups.items()})
        for name, encoder in [('odor', runner.sensors), ('sweet', runner.taste), ('club', runner.proprioceptor)]:
            if encoder is None:
                raise ValueError('The declared loop assay requires every named sensory encoder')
            original = encoder.encode
            def capture_encoder(observation, *args, _name=name, _original=original, **kwargs):
                before = {
                    't_s': observation['t_s'], 'antenna_odor': observation['antenna_odor'],
                    'hunger': observation['physiology'].get('hunger'),
                    'food_contact_by_leg': observation['food_contact_by_leg'],
                    'tibia_pitch_velocity_rad_s': observation['proprioception']['joint_velocities_rad_s']['tibia_pitch'],
                }
                drive = _original(observation, *args, **kwargs)
                record = drive_record(drive, runner.graph.neuron_ids)
                self.components.append(record)
                journal.append('encoder', tick=self.tick, encoder=_name,
                               actual_local_observation=before, actual_drive=record)
                return drive
            self.replace(encoder, 'encode', capture_encoder)
        original_advance = runner.brain.advance
        def capture_brain(duration_ms, **kwargs):
            drive = kwargs['drive']
            record = drive_record(drive, runner.graph.neuron_ids)
            rng_before = [int(x) for x in runner.brain._rng_state]
            journal.append('neural_start', tick=self.tick, brain_t_ms=runner.brain.time_ms,
                           duration_ms=duration_ms, actual_drive=record,
                           rng_state=rng_before)
            # This preserves real encoder order, including listed zero-rate ORNs.
            indices = np.concatenate([np.asarray(c['indices'], dtype=np.int64) for c in self.components])
            rates = np.concatenate([np.asarray(c['rates_hz'], dtype=float) for c in self.components])
            if runner.assay == 'motor_probe':
                indices = np.r_[indices, runner.probe_indices]
                rates = np.r_[rates, np.full(len(runner.probe_indices), 40.)]
            else:
                assert runner.assay == 'sensory'
            np.testing.assert_array_equal(record['indices'], indices)
            np.testing.assert_array_equal(record['rates_hz'], rates)
            assert record['current_mv'] is record['poisson_weight_mv'] is None
            assert record['disable_refractory'] is True
            assert duration_ms == 2.
            batch = original_advance(duration_ms, **kwargs)
            sensory_mask = np.isin(batch.indices, self.sensory_indices)
            full = spike_record(batch)
            # Full per-neuron counts stay in the journal; summary keeps only hash.
            monitored = {k: spike_record(batch, np.isin(batch.indices, v)) for k, v in self.monitor_groups.items()}
            downstream = spike_record(batch, ~sensory_mask)
            self.neural = {'tick': self.tick, 'start_ms': batch.start_ms, 'end_ms': batch.end_ms,
                'ordered_drive_sha256': record['ordered_drive_sha256'],
                'full_event_sha256': full['event_sha256'],
                'downstream_event_sha256': downstream['event_sha256'],
                'total_spikes': batch.total_spikes, 'traversed_edges': batch.traversed_edges,
                'monitored_counts': {k: v['spikes'] for k, v in monitored.items()},
                'finite_voltage': bool(np.isfinite(runner.brain.voltage_mv).all()),
                'finite_synaptic_state': bool(np.isfinite(runner.brain.synaptic_mv).all()),
                'voltage_mv': {'min': float(runner.brain.voltage_mv.min()),
                               'max': float(runner.brain.voltage_mv.max())},
                'rng_state_before': rng_before, 'rng_state_after': [int(x) for x in runner.brain._rng_state],
                'positive_input_cells_by_encoder': {name: int(np.count_nonzero(np.asarray(c['rates_hz']) > 0))
                                                    for name, c in zip(SENSORY_GROUPS, self.components, strict=True)},
                'max_input_event_rate_hz_by_encoder': {name: max(c['rates_hz'], default=0.)
                                                      for name, c in zip(SENSORY_GROUPS, self.components, strict=True)},
                'listed_input_refractory_zero': bool(not runner.brain.refractory_ticks[np.asarray(drive.indices)].any()),
                'sensory_outgoing_mask': bool(runner.brain.ablated[self.sensory_indices].all()),
                'blocked_neuron_count': int(runner.brain.ablated.sum())}
            assert batch.total_spikes == full['spikes']
            journal.append('neural_complete', **self.neural, all_neuron_counts=full,
                           sensory_and_motor_events=monitored)
            return batch
        self.replace(runner.brain, 'advance', capture_brain)

    def replace(self, obj, name, method):
        self.restore.append((obj, name, getattr(obj, name)))
        setattr(obj, name, method)

    def begin(self, tick):
        self.tick, self.components, self.neural = tick, [], None

    def close(self):
        for obj, name, method in reversed(self.restore):
            setattr(obj, name, method)


def paired_mechanisms(conditions):
    """Do not assume afferents remain matched after closed-loop divergence."""
    if len(conditions) != 2:
        return {'comparison_available': False}
    left, right = conditions
    a, b = left.get('neural_intervals', []), right.get('neural_intervals', [])
    matched_input_prefix = True
    first_input_difference = first_downstream_difference = None
    first_downstream_with_matched_inputs = None
    for x, y in zip(a, b):
        if x['ordered_drive_sha256'] != y['ordered_drive_sha256']:
            matched_input_prefix = False
            if first_input_difference is None:
                first_input_difference = x['tick']
        if matched_input_prefix:
            assert x['rng_state_before'] == y['rng_state_before']
            assert x['rng_state_after'] == y['rng_state_after']
        if x['downstream_event_sha256'] != y['downstream_event_sha256']:
            if first_downstream_difference is None:
                first_downstream_difference = x['tick']
            if matched_input_prefix and first_downstream_with_matched_inputs is None:
                first_downstream_with_matched_inputs = x['tick']
    return {'comparison_available': True, 'paired_neural_intervals': min(len(a), len(b)),
            'first_ordered_input_difference_tick': first_input_difference,
            'first_non_sensory_spike_event_difference_tick': first_downstream_difference,
            'first_downstream_difference_with_identical_input_history_tick': first_downstream_with_matched_inputs,
            'physical_feedback_reaches_downstream_under_paired_input_history': first_downstream_with_matched_inputs is not None,
            'entire_closed_loop_input_equality_required': False,
            'interpretation': 'Afferent-output block can change physical feedback and later input/RNG assignment. A matched-prefix downstream difference supports graph transmission, not natural navigation.'}


def inspect_physical(runner):
    """Read cached completed native state; no IPC, rendering or physics step."""
    d = runner.body.diagnostics()
    required = ('native_time_s', 'tick', 'finite', 'warnings', 'qpos', 'qvel', 'qacc', 'act', 'ctrl',
                'native_action', 'canonical_action', 'actuator_ids', 'action_names', 'pose_cm_quat',
                'up_z', 'support_dyne_by_leg', 'contacts', 'antenna_positions_mm',
                'tibia_velocity_rad_s', 'command', 'target_pose_cm_quat', 'source_terminated')
    missing = [k for k in required if k not in d]
    if missing:
        raise ValueError(f'Frozen physical diagnostic contract incomplete: {missing}')
    return copy.deepcopy(d)


def native_state_hash(d):
    fields = {k: d[k] for k in ('native_time_s', 'tick', 'qpos', 'qvel', 'qacc', 'act', 'ctrl',
                               'native_action', 'pose_cm_quat', 'target_pose_cm_quat')}
    return hashlib.sha256(json.dumps(safe(fields), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def physical_summary(runner, d, state, expected_tick):
    arrays = [np.asarray(d[k], dtype=float) for k in ('qpos', 'qvel', 'qacc', 'act', 'ctrl',
              'native_action', 'pose_cm_quat', 'antenna_positions_mm', 'tibia_velocity_rad_s')]
    finite = bool(all(np.isfinite(v).all() for v in arrays))
    warning_counts = d['warnings']
    if isinstance(warning_counts, dict):
        warning_counts = list(warning_counts.values())
    assert all(isinstance(x, (int, np.integer)) for x in warning_counts)
    clock_error = max(abs(state['t_s'] - expected_tick*DT),
                      abs(state['brain_t_s'] - expected_tick*DT),
                      abs(float(d['native_time_s']) - expected_tick*DT))
    obs = runner.body.observe()
    np.testing.assert_array_equal(obs['proprioception']['joint_velocities_rad_s']['tibia_pitch'],
                                  d['tibia_velocity_rad_s'])
    # Independently test native-to-public contact gating using the retained
    # actual source contact points and declared material regions of the floor.
    world = runner.body.snapshot()
    cfg = world['config']
    contact_checks = {}
    for resource in ('food', 'water'):
        expected = {leg: False for leg in ('LF', 'LM', 'LH', 'RF', 'RM', 'RH')}
        for contact in d['contacts']:
            if contact['active'] and contact['is_tarsal'] and contact['dist_cm'] <= 0:
                point = np.asarray(contact['position_mm'], dtype=float)[:2]
                inside = np.linalg.norm(point-np.asarray(cfg[resource+'_position_mm'])) <= cfg[resource+'_radius_mm']
                if inside and world['resources'][resource]['remaining'] > 0:
                    expected[contact['leg']] = True
        actual = obs[resource+'_contact_by_leg']
        contact_checks[resource] = expected == actual
        assert contact_checks[resource], (resource, expected, actual)
    # PuffField.sample is a pure read of existing physical puffs. This extra
    # evaluator query does not advance field time, create puffs or touch RNG.
    antenna_m = np.asarray(d['antenna_positions_mm'], dtype=float)*.001
    odor = runner.body.field.sample(antenna_m, state['t_s'])
    np.testing.assert_array_equal(odor, obs['antenna_odor'])
    native = np.asarray(d['native_action'])
    commanded = d['command']
    assert d['action_names'] == world['backend']['action_names']
    np.testing.assert_array_equal(np.asarray(d['ctrl'])[d['actuator_ids']], native)
    hold_required = not commanded['policy_enabled']
    hold_exact = bool(np.array_equal(native, np.r_[np.ones(6), np.zeros(53)])) if hold_required else None
    policy_exact = None
    if not hold_required:
        lo = np.asarray(world['backend']['action_minimum'], dtype=np.float32)
        hi = np.asarray(world['backend']['action_maximum'], dtype=np.float32)
        canonical = np.asarray(d['canonical_action'], dtype=np.float32)
        expected_native = lo + np.float32(.5)*(np.clip(canonical, -1, 1)+1)*(hi-lo)
        policy_exact = bool(np.array_equal(expected_native, native))
        assert policy_exact
    drives = np.clip([state['motor']['left'], state['motor']['right']], -1.2, 1.2)
    expected_speed = 20*float(np.clip(drives.mean(), 0, 1)) if not hold_required else 0.
    expected_yaw = 2*float(np.clip((drives[1]-drives[0])/1.2, -1, 1)) if not hold_required else 0.
    assert abs(commanded['speed_mm_s']-expected_speed) < 1e-12
    assert abs(commanded['yaw_rad_s']-expected_yaw) < 1e-12
    residual = max(abs(float(v)) for v in state['resource_balance'].values())
    return {'tick': expected_tick, 't_s': state['t_s'], 'brain_t_s': state['brain_t_s'],
            'native_time_s': d['native_time_s'], 'clock_max_error_s': clock_error,
            'native_tick': d['tick'], 'finite_native_arrays': finite,
            'producer_finite_flag': d['finite'], 'warnings': warning_counts,
            'qacc_abs_max_native': max(abs(float(x)) for x in d['qacc']),
            'up_z': d['up_z'], 'position_mm': (np.asarray(d['pose_cm_quat'])[:3]*10).tolist(),
            'source_terminated': d['source_terminated'], 'motor': state['motor'],
            'native_command': commanded, 'neutral_hold_required': hold_required,
            'neutral_hold_exact': hold_exact, 'native_policy_action_exact': policy_exact,
            'motor_command_map_exact': True, 'native_control_order_exact': True,
            'resource_residual_max': residual,
            'taste_contact_mapping_exact': contact_checks, 'odor_at_actual_antenna_positions_exact': True,
            'tibia_feedback_matches_native': True, 'actual_contact_count': len(d['contacts']),
            'blocked_synaptic_outputs': state['neural']['blocked_synaptic_outputs']}


def create_plan(config_path):
    if PLAN.exists():
        raise FileExistsError('Existing declared plan is immutable')
    config = json.loads(config_path.read_text())
    required = {'body_backend': 'flybody', 'seed': 11, 'coupling_s': .002,
                'neural_model': 'shiu', 'assay': 'motor_probe', 'probe_hz': 40,
                'enable_taste': True}
    for key, value in required.items():
        if config.get(key) != value:
            raise ValueError(f'Declared config must have {key}={value!r}')
    assert config['proprioception'] == {'max_rate_hz': 30, 'half_speed_rad_s': 5}
    assert config.get('neural_parameters', {}) == {}
    assert config.get('connectome', 'data/processed/malecns_v1') == 'data/processed/malecns_v1'
    graph_manifest_path = ROOT/'data/processed/malecns_v1/manifest.json'
    graph_manifest = json.loads(graph_manifest_path.read_text())
    assert (graph_manifest['neurons'], graph_manifest['edges']) == (166700, 25582938)
    parity = json.loads((ROOT/'validation/flybody-bridge-validation.json').read_text())
    assert parity['complete'] and parity['passed']
    sources = [str(p.relative_to(ROOT)) for p in sorted((ROOT/'fruitfly').glob('*.py'))]
    sources += ['scripts/check_flybody_loop.py', str(config_path.relative_to(ROOT)),
                'validation/flybody-source-manifest.json', 'validation/flybody-walking-acquisition.json',
                'validation/flybody-inference-requirements.lock', 'validation/flybody-stance-plan.json',
                'validation/flybody-stance-experiment.json', 'docs/flybody-integration-plan.md',
                'validation/flybody-bridge-validation.json',
                str(graph_manifest_path.relative_to(ROOT))]
    # These source locations are declared before observing any full-loop result.
    config['body']['food_position_mm'] = [6., 10.]
    config['body']['food_radius_mm'] = 3.
    conditions = [
        {'name': 'locomotor_feedback', 'duration_s': 2., 'assay': 'motor_probe',
         'motor_mute': True, 'outgoing_blocks': [], 'food_position_mm': [6., 10.]},
        {'name': 'locomotor_sensory_block', 'duration_s': 2., 'assay': 'motor_probe',
         'motor_mute': True, 'outgoing_blocks': list(SENSORY_GROUPS), 'food_position_mm': [6., 10.]},
        {'name': 'on_food_feedback', 'duration_s': .5, 'assay': 'sensory',
         'motor_mute': False, 'outgoing_blocks': [], 'food_position_mm': [0., 0.]},
        {'name': 'on_food_sweet_block', 'duration_s': .5, 'assay': 'sensory',
         'motor_mute': False, 'outgoing_blocks': ['sweet'], 'food_position_mm': [0., 0.]},
    ]
    plan = {'scope': __doc__, 'config': config, 'coupling_s': DT,
            'seed': 11, 'physics_dt_s': .0002, 'neural_dt_ms': .1,
            'expected_neurons': 166700, 'expected_edges': 25582938,
            'conditions': conditions,
            'sensory_outgoing_groups': list(SENSORY_GROUPS),
            'interventions_locomotor_pair': [{'before_tick': 300, 't_s': .6, 'motor_readout_muted': True},
                                            {'before_tick': 600, 't_s': 1.2, 'motor_readout_muted': False}],
            'sensory_block_schedule': 'Block declared source groups before tick0 in each paired condition. Preserve actual odor/sweet/club inputs throughout. Direct40Hz DNg97 probe exists only in locomotor pair.',
            'source_sha256': {p: sha(ROOT/p) for p in sources},
            'hash_conventions': {'spike_events': 'SHA256:little-endian uint64 event count,then ordered int64 neuron IDs,then ordered float64 absolute milliseconds; all events recorded.',
                                 'drives': 'SHA256 of compact sorted-key JSON containing ordered indices/IDs/rates/current/weight/refractory declaration; no sorting of input arrays.'},
            'gates': {'completion': 'Locomotor trials each complete1000 intervals; on-food trials each250. Preserve and fail incomplete/source-terminated conditions.',
                      'clocks': 'At each tick brain/body/native time agrees with tick*.002 within1e-9; native tick agrees.',
                      'finite': 'Every retained qpos/qvel/qacc/act/ctrl and brain voltage/synaptic array finite; zero native warning counters.',
                      'mechanism': 'Exact ordered encoder composition and source IDs; actual physical antenna/tarsal/tibia mappings; exact original neutral53-zero/six-adhesion1 command whenever not walking.',
                      'mute': 'Ticks300–599 request rest with zero left/right while full-graph spikes continue; no requirement for forced postmute walking.',
                      'sensory_block': 'Only declared sensory-source outgoing mask changes; native inputs still delivered; report downstream differences within identical-input-history prefix.',
                      'transmission_evidence': 'Require a non-sensory spike-event difference in the locomotor pair while all prior/current ordered inputs and RNG states match. Absence fails this evidence criterion,not necessarily interface plumbing.',
                      'resources': 'Finite normalized ledger residuals below1e-8.',
                      'lifecycle': 'Before trial, same-seed reset reproduces initial native state; advance0 and initial render preserve native/neural clocks and state.'},
            'not_gates': ['No forced trajectory, minimum walking distance, regained walking, natural navigation, feeding or biological stance claim.',
                          'No requirement of positive food intake or differential MN9 recruitment; report those endpoints separately from input/control plumbing.',
                          'No requirement that closed-loop afferent drives or afferent spikes stay identical after the output block alters feedback.'],
            'failure_retention': 'Flush ordered encoder/neural-start/neural-complete/physical events each tick to condition JSONL; save any failed completed-step native cache and latest neural time before cleanup; retain partial condition results.',
            'claim_limits': ['Fullgraph Shiu current-based pathology remains, including potentially implausible hyperpolarization.',
                             'Female-derived FlyBody morphology; pretrained motor policy and engineering neutral hold.',
                             '2ms physical sensory/physiology sampling, not all0.2ms substeps; contact between snapshots may be missed.',
                             'Two selected2s locomotor and two0.5s on-food trials,one seed,one floor; no persistent-viewer or robustness claim.',
                             'On-food assays retain odor and club input: not taste-only activation. Zero taste in off-path-food locomotor trials is reported explicitly if observed.',
                             'No training,gain tuning,new sensory calibration,world-to-motor shortcut or prerecorded physical replay.']}
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(PLAN, plan)
    print('Predeclared plan saved', sha(PLAN), flush=True)


def run_condition(condition, plan):
    from fruitfly.simulation import SimulationRunner
    from PIL import Image
    name = condition['name']
    folder = OUT/name
    folder.mkdir(exist_ok=False)
    journal = Journal(folder/'events.jsonl')
    record = {'condition': name, 'design': condition, 'complete': False, 'completed_ticks': 0,
              'physical_intervals': [], 'neural_intervals': [], 'failures': []}
    config = copy.deepcopy(plan['config'])
    config['run_dir'] = str(folder/'runner')
    config['assay'] = condition['assay']
    config['body']['food_position_mm'] = condition['food_position_mm']
    total_ticks = round(condition['duration_s']/DT)
    runner = capture = process = None
    try:
        journal.append('condition_start', condition=condition, config=config, plan_sha256=sha(PLAN))
        runner = SimulationRunner(config)
        assert runner.brain.n_neurons == plan['expected_neurons']
        assert runner.brain.n_edges == plan['expected_edges']
        process = runner.body._proc
        record['worker_pid'] = process.pid
        initial_d = inspect_physical(runner)
        initial_native_hash = native_state_hash(initial_d)
        runner.control({'type': 'reset'})
        assert native_state_hash(inspect_physical(runner)) == initial_native_hash
        before = runner.brain.state_dict()
        runner.advance(0)
        Image.fromarray(runner.render('overview')).save(folder/'initial.png')
        after = runner.brain.state_dict()
        for k, value in before.items():
            if isinstance(value, np.ndarray):
                np.testing.assert_array_equal(value, after[k])
            else:
                assert value == after[k]
        assert native_state_hash(inspect_physical(runner)) == initial_native_hash
        assert initial_d['native_time_s'] == 0 and initial_d['tick'] == 0
        record['lifecycle_initial_pass'] = True
        record['graph_sha256'] = runner.brain.graph_sha256
        record['neural_parameters'] = asdict(runner.brain.parameters)
        record['initial'] = runner.snapshot()
        record['initial_diagnostics'] = inspect_physical(runner)
        for group in condition['outgoing_blocks']:
            runner.control({'type': 'synaptic_output', 'group': group, 'blocked': True})
        capture = Capture(runner, journal)
        expected_mask = np.zeros(runner.brain.n_neurons, dtype=bool)
        for group in condition['outgoing_blocks']:
            expected_mask[runner._input_group(group)] = True
        record['groups'] = {k: {'indices': v.tolist(), 'neuron_ids': runner.graph.neuron_ids[v].tolist(),
                                'types': runner.graph.neurons.iloc[v].type.tolist()}
                            for k, v in capture.monitor_groups.items()}
        record['probe_ids'] = runner.graph.neuron_ids[runner.probe_indices].tolist()
        journal.append('initial', state=record['initial'], diagnostics=record['initial_diagnostics'],
                       groups=record['groups'], probe_ids=record['probe_ids'])
        start = time.perf_counter()
        for tick in range(total_ticks):
            capture.begin(tick)
            if condition['motor_mute'] and tick in (300, 600):
                command = {'type': 'ablation', 'enabled': tick == 300}
                journal.append('intervention_start', tick=tick, command=command)
                runner.control(command)
                journal.append('intervention_complete', tick=tick, state=runner.snapshot())
            np.testing.assert_array_equal(runner.brain.ablated, expected_mask)
            journal.append('coupling_start', tick=tick, physical_t_s=runner.body.time_s,
                           brain_t_ms=runner.brain.time_ms, physical_observation=runner.body.observe())
            state = runner.advance(DT)
            d = inspect_physical(runner)
            summary = physical_summary(runner, d, state, tick+1)
            journal.append('physical_complete', tick=tick, diagnostics=d, state=state, checks=summary)
            assert capture.neural is not None
            record['neural_intervals'].append(copy.deepcopy(capture.neural))
            record['physical_intervals'].append(summary)
            record['completed_ticks'] = tick+1
            # Check after journaling so a failed assertion preserves its evidence.
            assert summary['clock_max_error_s'] < 1e-9 and d['tick'] == tick+1
            assert summary['finite_native_arrays'] and d['finite'] and not any(summary['warnings'])
            assert summary['resource_residual_max'] < 1e-8
            assert not d['source_terminated']
            assert capture.neural['finite_voltage'] and capture.neural['finite_synaptic_state']
            assert capture.neural['listed_input_refractory_zero']
            if summary['neutral_hold_required']:
                assert summary['neutral_hold_exact'] and not d['command']['policy_enabled']
            if condition['motor_mute'] and 300 <= tick < 600:
                assert state['motor'] == {'behavior': 'rest', 'left': 0., 'right': 0.}
            if (tick+1) % 100 == 0:
                write_json(folder/'progress.json', {'completed_ticks': tick+1, 't_s': state['t_s'],
                                                   'graph_sha256': record['graph_sha256']})
                print(name, 'completed', tick+1, 'ticks', 'behavior', state['behavior'], flush=True)
        record['wall_s'] = time.perf_counter()-start
        record['final'] = runner.snapshot()
        final_hash = native_state_hash(inspect_physical(runner))
        Image.fromarray(runner.render('overview')).save(folder/'final.png')
        assert native_state_hash(inspect_physical(runner)) == final_hash
        record['complete'] = True
    except BaseException as error:
        failure = {'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc()}
        if runner is not None:
            failure['brain_t_ms'] = runner.brain.time_ms
            try:
                failure['last_native_diagnostics'] = inspect_physical(runner)
                failure['last_cached_state'] = runner.snapshot()
            except BaseException as diagnostic_error:
                failure['diagnostic_error'] = repr(diagnostic_error)
        if capture is not None and capture.neural is not None:
            failure['last_completed_neural_interval'] = copy.deepcopy(capture.neural)
        record['failures'].append(failure)
        journal.append('condition_failure', failure=failure)
    finally:
        if capture is not None:
            capture.close()
        if runner is not None:
            try:
                runner.close()
            except BaseException as error:
                record['failures'].append({'cleanup_error': repr(error)})
                journal.append('cleanup_failure', error=repr(error))
            record['worker_exit_code_after_close'] = process.poll() if process is not None else None
        journal.append('condition_end', complete=record['complete'], completed_ticks=record['completed_ticks'])
        journal.close()
        record['journal'] = {'path': str(journal.path.relative_to(ROOT)), 'sha256': sha(journal.path), 'records': journal.records}
        if (folder/'runner/manifest.json').exists():
            record['manifest_sha256'] = sha(folder/'runner/manifest.json')
        record['frames'] = {p.name: sha(p) for p in folder.glob('*.png')}
        muted = [x for x in record['neural_intervals'] if 300 <= x['tick'] < 600]
        record['muted_neural_spikes'] = sum(x['total_spikes'] for x in muted)
        record['checks'] = {'completed_declared_duration': record['complete'] and record['completed_ticks'] == total_ticks,
                            'no_retained_failures': not record['failures'],
                            'neural_spikes_continue_during_mute': not condition['motor_mute'] or record['muted_neural_spikes'] > 0,
                            'lifecycle_initial': record.get('lifecycle_initial_pass', False),
                            'worker_reaped': process is not None and process.poll() is not None}
        intervals = record['neural_intervals']
        record['observed_endpoints'] = {
            'sweet_input_ever_positive': any(x['positive_input_cells_by_encoder']['sweet'] > 0 for x in intervals),
            'source_spikes_by_group': {g: sum(x['monitored_counts'][g] for x in intervals) for g in SENSORY_GROUPS},
            'feeding_motor_spikes': sum(x['monitored_counts']['motor_feeding'] for x in intervals),
            'food_ingested': record.get('final', {}).get('physiology', {}).get('food_ingested'),
            'requested_behavior_counts': {behavior: sum(x['motor']['behavior'] == behavior for x in record['physical_intervals'])
                                          for behavior in ('rest', 'walk', 'feed')},
            'positive_intake_required_for_success': False,
        }
        record['all_declared_condition_gates_pass'] = all(record['checks'].values())
        write_json(folder/'condition.json', record)
    return record


def run():
    plan = json.loads(PLAN.read_text())
    for p, value in plan['source_sha256'].items():
        if sha(ROOT/p) != value:
            raise ValueError(f'Declared source changed before rollout: {p}')
    if RESULT.exists():
        raise FileExistsError('Existing results must be preserved')
    report = {'complete': False, 'plan_sha256': sha(PLAN), 'conditions': [],
              'biological_behavior_validated': False, 'gain_tuning': None}
    write_json(RESULT, report)
    for condition in plan['conditions']:
        record = run_condition(condition, plan)
        report['conditions'].append(record)
        write_json(RESULT, report)
    report['paired_mechanisms'] = {'locomotor': paired_mechanisms(report['conditions'][:2]),
                                   'on_food': paired_mechanisms(report['conditions'][2:])}
    report['complete'] = True  # All declared attempts concluded; not success.
    report['all_condition_plumbing_gates_pass'] = all(x['all_declared_condition_gates_pass'] for x in report['conditions'])
    report['all_declared_gates_pass'] = (report['all_condition_plumbing_gates_pass']
        and report['paired_mechanisms']['locomotor'].get('physical_feedback_reaches_downstream_under_paired_input_history', False))
    report['source_hashes_unchanged_after'] = {p: sha(ROOT/p) == h for p, h in plan['source_sha256'].items()}
    write_json(RESULT, report)
    print(json.dumps({'complete': True, 'all_declared_gates_pass': report['all_declared_gates_pass'],
                      'paired_mechanisms': report['paired_mechanisms']}, indent=2), flush=True)
    if not report['all_declared_gates_pass']:
        raise SystemExit('Declared mechanism or engineering gate failed; all partial evidence retained.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan', action='store_true')
    mode.add_argument('--run', action='store_true')
    parser.add_argument('--config', type=Path, default=ROOT/'configs/male-flybody-probe.json')
    args = parser.parse_args()
    create_plan(args.config.resolve()) if args.plan else run()
