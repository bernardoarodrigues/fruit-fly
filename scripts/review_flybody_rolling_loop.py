#!/usr/bin/env python3
"""Independent streaming review of CLOSED rolling-loop journals and spike files.

Never imports or executes the producer, neural model, learned actor or physics.
--available reviews only attempts with completed producer condition receipts.
An incomplete gzip is an error, never an inferred successful end of a trial.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'validation/flybody-rolling-loop'
DT = .002
LEGS = ('LF','LM','LH','RF','RM','RH')
SENSORY = ('odor','sweet','club')
BLOCK = struct.Struct('<QQdd')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while data := stream.read(8*1024*1024):
            h.update(data)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',',':'), allow_nan=False).encode()


def same(a, b, tolerance=0.):
    a,b = np.asarray(a),np.asarray(b)
    assert a.shape == b.shape, (a.shape,b.shape)
    assert np.isfinite(a).all() and np.isfinite(b).all()
    error = float(np.max(a != b)) if a.dtype.kind == b.dtype.kind == 'b' else (float(np.max(abs(a-b))) if a.size else 0.)
    assert error <= tolerance, error
    return error


def drive_check(drive, ids):
    assert drive['ordered_drive_sha256'] == hashlib.sha256(canonical(
        {k:v for k,v in drive.items() if k != 'ordered_drive_sha256'})).hexdigest()
    indices = np.asarray(drive['indices'],dtype=int)
    assert len(np.unique(indices)) == len(indices)
    same(ids[indices],drive['neuron_ids'])
    assert drive['current_mv'] is drive['poisson_weight_mv'] is None
    assert drive['disable_refractory'] is True
    rates = np.asarray(drive['rates_hz'])
    assert rates.shape == indices.shape and np.isfinite(rates).all() and (rates >= 0).all()


class GzipReader:
    def __init__(self,path):
        self.path = Path(path)
        self.stream = gzip.open(path,'rb')
        self.digest = hashlib.sha256()
        self.bytes = 0

    def read(self,n=-1):
        data = self.stream.read(n)
        self.digest.update(data);self.bytes += len(data)
        return data

    def lines(self):
        while line := self.stream.readline():
            self.digest.update(line);self.bytes += len(line)
            assert line.endswith(b'\n'), 'Incomplete JSON journal line'
            yield json.loads(line)

    def finish(self,receipt):
        assert self.read(1) == b'', 'Unread/trailing compressed content'
        self.stream.close()  # read above also validates the gzip EOF/trailer.
        assert self.bytes == receipt['uncompressed_bytes']
        assert self.digest.hexdigest() == receipt['uncompressed_sha256']
        assert sha(self.path) == receipt['sha256']
        assert self.path.stat().st_size == receipt['compressed_bytes']


class Spikes:
    def __init__(self,path,plan_hash,graph_hash):
        self.reader = GzipReader(path)
        assert self.reader.read(8) == b'FFSPK001'
        raw = self.reader.read(4)
        assert len(raw) == 4
        n, = struct.unpack('<I',raw)
        assert 0 < n <= 65536
        raw = self.reader.read(n)
        assert len(raw) == n
        header = json.loads(raw)
        assert header['format'] == 'FFSPK001' and header['endian'] == 'little'
        assert header['plan_sha256'] == plan_hash and header['graph_sha256'] == graph_hash
        assert header['block_header_bytes'] == 32 and header['bytes_per_event'] == 16
        self.blocks = self.events = 0
        self.last = None

    def next(self,packet):
        offset = self.reader.bytes
        raw = self.reader.read(32)
        assert len(raw) == 32, 'Truncated spike block header'
        tick,n,start,end = BLOCK.unpack(raw)
        assert tick == self.blocks and 0 <= n <= 166700*20
        raw_ids,raw_times = self.reader.read(n*8),self.reader.read(n*8)
        assert len(raw_ids) == len(raw_times) == n*8, 'Truncated spike payload'
        digest = hashlib.sha256(struct.pack('<Q',n)+raw_ids+raw_times).hexdigest()
        expected = dict(tick=tick,uncompressed_offset=offset,uncompressed_block_bytes=32+n*16,
                        events=n,start_ms=start,end_ms=end,event_sha256=digest)
        for key,value in expected.items():
            assert packet[key] == value, (key,packet[key],value)
        self.blocks += 1;self.events += n;self.last = expected
        return np.frombuffer(raw_ids,dtype='<i8'),np.frombuffer(raw_times,dtype='<f8')

    def finish(self,receipt):
        self.reader.finish(receipt)
        assert self.blocks == receipt['blocks'] and self.events == receipt['events']
        assert self.last == receipt['last_complete_block']


def rng_step(state):
    state ^= state >> 12
    state ^= (state << 25) & ((1 << 64)-1)
    return state ^ (state >> 27)


def apply_linear(columns,state):
    out = 0
    while state:
        lowest = state & -state
        out ^= columns[lowest.bit_length()-1]
        state ^= lowest
    return out


RNG_POWERS = [[rng_step(1 << bit) for bit in range(64)]]


def rng_after(state,draws):
    """Exact GF(2) jump of xorshift state; no neural or Poisson model replay."""
    power = 0
    while draws:
        if power == len(RNG_POWERS):
            prior = RNG_POWERS[-1]
            RNG_POWERS.append([apply_linear(prior,col) for col in prior])
        if draws & 1:
            state = apply_linear(RNG_POWERS[power],state)
        power += 1;draws >>= 1
    return state


def source_groups(neurons):
    side = neurons.rootSide.fillna(neurons.somaSide)
    def select(types,lateral=None,nerve=None):
        mask = neurons.type.isin(types)
        if lateral is not None: mask &= side.eq(lateral)
        if nerve is not None: mask &= neurons.entryNerve.eq(nerve)
        return np.flatnonzero(mask.values)
    odor = [select(['ORN_DM1','ORN_DM4'],s) for s in ('L','R')]
    taste,club = [],[]
    for leg in LEGS:
        nerve = {'F':'ProLN','M':'MesoLN','H':'MetaLN'}[leg[1]]
        taste.append(select(['LgAG2','LgLG4'],leg[0],nerve))
        club.append(select(['SNpp40','SNpp47','SNpp56','SNpp57','SNpp60'],leg[0],nerve))
    groups = dict(odor=np.concatenate(odor),sweet=np.unique(np.concatenate(taste)),club=np.unique(np.concatenate(club)),
        motor_forward=select(['DNg97']),motor_turn_left=select(['DNa01','DNa02'],'L'),
        motor_turn_right=select(['DNa01','DNa02'],'R'),motor_feeding=select(['MN9']),motor_escape=select(['DNp01']))
    return groups,odor,taste,club


def event_hash(ids,times):
    return hashlib.sha256(struct.pack('<Q',len(ids)) + np.asarray(ids,dtype='<i8').tobytes()
                          + np.asarray(times,dtype='<f8').tobytes()).hexdigest()


class Prefix:
    def __init__(self,reference,plan):
        assert sha(ROOT/reference['journal_gzip_path']) == reference['journal_gzip_sha256']
        self.reader = GzipReader(ROOT/reference['journal_gzip_path'])
        self.events = self.reader.lines()
        self.reference,self.plan = reference,plan
        self.count = 0;self.digest = hashlib.sha256();self.differences = []
        self.initial = next(e for e in self.events if e['event'] == 'initial')

    def equal_fields(self,old,new,fields,tick,kind):
        for field in fields:
            if canonical(old[field]) != canonical(new[field]):
                self.differences.append(dict(tick=tick,kind=kind,field=field))

    def initial_check(self,initial):
        self.equal_fields(self.initial['diagnostics'],initial,self.plan['prefix_native_fields'],-1,'native_initial')

    def compare(self,bundle):
        tick = bundle['coupling_start']['tick']
        if tick >= self.plan['initial_prefix_ticks']: return
        old = dict(encoders=[])
        for event in self.events:
            kind = event['event']
            if kind.startswith('intervention_'): continue
            if kind == 'encoder': old['encoders'].append(event)
            else: old[kind] = event
            if kind == 'physical_complete': break
        assert old['physical_complete']['tick'] == tick
        assert len(old['encoders']) == len(bundle['encoders']) == 3
        before = len(self.differences)
        for left,right in zip(old['encoders'],bundle['encoders'],strict=True):
            self.equal_fields(left,right,('encoder','actual_local_observation','actual_drive'),tick,'encoder')
        self.equal_fields(old['neural_start'],bundle['neural_start'],
                          ('brain_t_ms','duration_ms','actual_drive','rng_state'),tick,'neural_start')
        self.equal_fields(old['neural_complete'],bundle['neural_complete'],self.plan['prefix_neural_fields'],tick,'neural_complete')
        native = bundle['physical_returned']['diagnostics']
        self.equal_fields(old['physical_complete']['diagnostics'],native,self.plan['prefix_native_fields'],tick,'native')
        assert bundle['ordered_spikes']['event_sha256'] == bundle['neural_complete']['full_event_sha256']
        if len(self.differences) == before:
            self.count += 1
            self.digest.update(struct.pack('<Q',tick))
            self.digest.update(canonical({k:native[k] for k in self.plan['prefix_native_fields']}))
            self.digest.update(canonical({k:bundle['neural_complete'][k] for k in self.plan['prefix_neural_fields']}))

    def finish(self):
        for _ in self.events: pass
        r = self.reference
        self.reader.finish(dict(uncompressed_bytes=r['original_uncompressed_bytes'],
            uncompressed_sha256=r['original_uncompressed_sha256'],sha256=r['journal_gzip_sha256'],
            compressed_bytes=(ROOT/r['journal_gzip_path']).stat().st_size))


def check_physical(bundle,previous,initial_phys,previous_phys,metadata,rate_state,groups,plan,design,maxima):
    tick = bundle['coupling_start']['tick']
    obs = bundle['coupling_start']['physical_observation']
    returned = bundle['physical_returned']
    d,state = returned['diagnostics'],returned['state']
    for key in ('qpos','qvel','qacc','act','ctrl','native_action','canonical_action','pose_cm_quat',
                'antenna_positions_mm','tibia_velocity_rad_s','actuator_force_preceding_stage'):
        assert np.isfinite(d[key]).all(), key
    assert d['tick'] == tick+1 and d['source_control_tick'] == tick+1
    assert d['reference_buffer_origin'] == tick
    assert d['reference_qpos_shape'] == [66,7] and d['reference_qvel_shape'] == [66,6]
    assert len(d['actor_input_sha256']) == 64
    same(d['pose_cm_quat'],np.asarray(d['qpos'])[:7])
    quaternion = np.asarray(d['pose_cm_quat'][3:])
    assert abs(np.linalg.norm(quaternion)-1) < 1e-10
    w,x,y,z = quaternion
    same(d['up_z'],1-2*(x*x+y*y),1e-12)
    maxima['clock_error_s'] = max(maxima['clock_error_s'],same(
        [state['t_s'],state['brain_t_s'],d['native_time_s']],[(tick+1)*DT]*3,1e-9))
    command = state['motor']
    muted = design['motor_mute'] and any(a <= tick < b for a,b in plan['mute_intervals_ticks'])
    if muted:
        expected = dict(behavior='rest',left=0.,right=0.)
    elif rate_state['motor_feeding'] > 5 and (obs['taste_food'] or obs['taste_water']):
        expected = dict(behavior='feed',left=0.,right=0.)
    else:
        forward = np.clip(rate_state['motor_forward']/40,0,1)
        turn = np.clip((rate_state['motor_turn_left']-rate_state['motor_turn_right'])/50,-.6,.6)
        expected = (dict(behavior='rest',left=0.,right=0.) if forward < .05 and abs(turn) < .05 else
            dict(behavior='walk',left=float(np.clip(forward-turn,-1.2,1.2)),right=float(np.clip(forward+turn,-1.2,1.2))))
    assert command['behavior'] == expected['behavior']
    same([command['left'],command['right']],[expected['left'],expected['right']],1e-12)
    for group,value in rate_state.items():
        same(value,state['neural']['output_rates'][group.removeprefix('motor_')],1e-10)
    on = expected['behavior'] == 'walk'
    assert d['command']['policy_enabled'] == on and d['command']['behavior'] == expected['behavior']
    if on:
        lo,hi = [np.asarray(metadata[k],dtype=np.float32) for k in ('action_minimum','action_maximum')]
        action = np.asarray(d['canonical_action'],dtype=np.float32)
        expected_action = lo + np.float32(.5)*(np.clip(action,-1,1)+1)*(hi-lo)
    else: expected_action = np.r_[np.ones(6),np.zeros(53)]
    same(d['native_action'],expected_action)
    same(np.asarray(d['ctrl'])[d['actuator_ids']],expected_action)
    assert d['action_names'] == metadata['action_names']
    drives = np.clip([command['left'],command['right']],-1.2,1.2)
    speed = 20*float(np.clip(drives.mean(),0,1)) if on else 0.
    yaw = 2*float(np.clip((drives[1]-drives[0])/1.2,-1,1)) if on else 0.
    same([d['command']['speed_mm_s'],d['command']['yaw_rad_s']],[speed,yaw],1e-12)
    prior_target = np.asarray(previous['target_pose_cm_quat'])
    heading = 2*np.arctan2(prior_target[6],prior_target[3]); angle = yaw*DT
    rotate = np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    delta = rotate @ (speed/10*np.array([np.cos(heading),np.sin(heading)]))*DT
    target = prior_target.copy();target[:2] += delta
    target[3:] = [np.cos(angle/2)*np.cos(heading/2)-np.sin(angle/2)*np.sin(heading/2),0,0,
                  np.cos(angle/2)*np.sin(heading/2)+np.sin(angle/2)*np.cos(heading/2)]
    maxima['integrated_target_error_cm_quat'] = max(maxima['integrated_target_error_cm_quat'],
        same(d['target_pose_cm_quat'],target,1e-12))
    support = np.zeros(6);ground = np.zeros((6,3))
    for contact in d['contacts']:
        index = LEGS.index(contact['leg']);force = np.asarray(contact['force_world_dyne'])
        support[index] += abs(force[2]);ground[index] += force
    same(d['support_dyne_by_leg'],support,1e-10)
    same(d['ground_force_g_mm_s2'],ground*10,1e-9)
    p,resources = state['physiology'],state['resources']
    nutrient = resources['food']['remaining']+p['crop']+p['energy']+p['energy_spent']-resources['food']['initial']-initial_phys['energy']
    water = resources['water']['remaining']+p['hydration']+p['water_lost']-resources['water']['initial']-initial_phys['hydration']
    residual = max(abs(nutrient),abs(water))
    same([nutrient,water],[state['resource_balance']['nutrient'],state['resource_balance']['water']])
    maxima['resource_residual'] = max(maxima['resource_residual'],residual)
    assert residual < 1e-8
    assert all(0 <= p[k] <= p['capacities'][k] for k in ('energy','crop','hydration'))
    same(resources['food']['initial']-resources['food']['remaining'],p['food_ingested'],1e-12)
    delta_food = p['food_ingested']-previous_phys['food_ingested']
    assert 0 <= delta_food <= .08*DT+1e-12
    if delta_food > 0:
        assert command['behavior'] == 'feed' and np.linalg.norm(np.asarray(d['velocity_world_mm_s'])[:2]) <= 1.
        assert any(c['active'] and c['is_tarsal'] and c['dist_cm'] <= 0 and
            np.linalg.norm(np.asarray(c['position_mm'][:2])-plan['config']['body']['food_position_mm']) <= 3.
            for c in d['contacts'])
    healthy = d['finite'] and not d['source_terminated'] and not any(d['warnings'])
    return d,state,p,muted,healthy


def review_condition(condition,plan,ids,degree,neurons,group_info):
    name,design = condition['condition'],condition['design']
    groups,odor_groups,taste_groups,club_groups = group_info
    for group,indices in groups.items():
        saved = condition['groups'][group]
        same(np.sort(saved['indices']),np.sort(indices))
        same(ids[np.asarray(saved['indices'])],saved['neuron_ids'])
        assert neurons.iloc[saved['indices']].type.tolist() == saved['types']
    assert condition['graph_sha256'] == plan['graph_sha256'] and condition['neural_parameters'] == plan['neural_parameters']
    # The runner retains the available probe IDs even in sensory-only mode;
    # absence of their imposed drive is checked in every neural_start below.
    same(condition['probe_ids'],ids[groups['motor_forward']])
    folder = ROOT/condition['run_dir']
    assert (folder/'condition-summary.json').exists(), 'Attempt is still active'
    closed = read(folder/'condition-summary.json')
    assert closed == condition
    for receipt in condition['files'].values():
        assert sha(ROOT/receipt['path']) == receipt['sha256']
    journal = GzipReader(ROOT/condition['journal']['path'])
    spikes = Spikes(ROOT/condition['lossless_spikes']['path'],sha(OUT/'plan.json'),plan['graph_sha256'])
    sensory_mask = np.zeros(len(ids),bool)
    sensory_mask[np.concatenate([groups[g] for g in SENSORY])] = True
    blocked = np.zeros(len(ids),bool)
    for group in design['outgoing_blocks']: blocked[groups[group]] = True
    group_masks = {}
    for group,indices in groups.items():
        group_masks[group] = np.zeros(len(ids),bool);group_masks[group][indices] = True
    prefix = Prefix(plan['references'][name],plan) if name in plan['references'] else None
    maxima = defaultdict(float);totals = Counter();event_counts = Counter();behavior = Counter()
    adaptation = np.zeros(2);rate_state = {k:0. for k in groups if k.startswith('motor_')}
    edge_schedule = np.zeros(plan['ticks']+2,dtype=np.int64)
    last_spike = np.full(len(ids),-(2**60),dtype=np.int64)
    pending_tail = []
    first_rng = int(np.random.SeedSequence(plan['seed']).generate_state(1,dtype=np.uint64)[0])
    rng = first_rng
    bundle = None;initial = previous = previous_phys = None
    records = [];interventions = [];failure_events = [];unhealthy = []
    positions = [];neural_meta = [];voltage_min = float('inf');voltage_max = -float('inf')
    physical_count = complete_count = 0
    muted_windows = [dict(first_tick=a,end_tick=b,completed_ticks=0,neural_spikes=0) for a,b in plan['mute_intervals_ticks']] if design['motor_mute'] else []
    prior_kinds = []
    def contact_expected(d,resource,resources):
        position = plan['config']['body'].get(resource+'_position_mm',[5.,7.])
        radius = plan['config']['body'].get(resource+'_radius_mm',2.)
        found = {leg:False for leg in LEGS}
        for c in d['contacts']:
            if c['active'] and c['is_tarsal'] and c['dist_cm'] <= 0 and resources[resource]['remaining'] > 0:
                if np.linalg.norm(np.asarray(c['position_mm'][:2])-position) <= radius: found[c['leg']] = True
        return found

    for number,event in enumerate(journal.lines()):
        assert event['record'] == number
        kind = event['event'];event_counts[kind] += 1
        if kind == 'condition_start':
            assert number == 0 and event['condition'] == design and event['plan_sha256'] == sha(OUT/'plan.json')
        elif kind == 'initial':
            initial = event;previous = event['diagnostics'];previous_phys = event['state']['physiology']
            assert event['groups'] == condition['groups'] and event['probe_ids'] == condition['probe_ids']
            metadata = event['state']['body_metadata']
            assert metadata == condition['body_metadata']
            assert (metadata['reference_mode'],metadata['horizon_s'],metadata['reference_frames'],metadata['preview_frames']) == ('rolling',None,66,65)
            assert (metadata['physics_timestep_s'],metadata['control_timestep_s']) == (.0002,.002)
            assert previous['native_time_s'] == 0 and previous['tick'] == 0
            if prefix: prefix.initial_check(previous)
            positions.append(np.asarray(previous['pose_cm_quat'][:2])*10)
        elif kind.startswith('intervention_'):
            interventions.append((kind,event['tick']))
            if kind == 'intervention_start':
                assert event['command'] == dict(type='ablation',enabled=any(event['tick'] == a for a,_ in plan['mute_intervals_ticks']))
        elif kind == 'coupling_start':
            if bundle is not None:
                assert prior_kinds == ['coupling_start','encoder','encoder','encoder','neural_start','ordered_spikes','neural_complete','physical_returned','physical_complete']
            tick = event['tick'];assert tick == complete_count
            bundle = {'coupling_start':event,'encoders':[]};prior_kinds = [kind]
            obs = event['physical_observation']
            same([event['physical_t_s'],event['brain_t_ms']/1000,obs['t_s']],[tick*DT]*3,1e-9)
            same(obs['pose']['position_mm'],np.asarray(previous['pose_cm_quat'][:3])*10)
            same(obs['proprioception']['joint_velocities_rad_s']['tibia_pitch'],previous['tibia_velocity_rad_s'])
            same(obs['proprioception']['speed_mm_s'],np.linalg.norm(np.asarray(previous['velocity_world_mm_s'])[:2]))
            previous_resources = initial['state']['resources'] if physical_count == 0 else bundle_previous_state['resources']
            for resource in ('food','water'):
                expected = contact_expected(previous,resource,previous_resources)
                assert obs[resource+'_contact_by_leg'] == expected and obs['taste_'+resource] == any(expected.values())
        elif kind == 'encoder':
            bundle['encoders'].append(event);prior_kinds.append(kind)
            assert event['tick'] == tick
            obs = bundle['coupling_start']['physical_observation']
            assert event['actual_local_observation'] == dict(t_s=obs['t_s'],antenna_odor=obs['antenna_odor'],hunger=obs['physiology']['hunger'],
                food_contact_by_leg=obs['food_contact_by_leg'],tibia_pitch_velocity_rad_s=obs['proprioception']['joint_velocities_rad_s']['tibia_pitch'])
            drive_check(event['actual_drive'],ids)
        elif kind == 'neural_start':
            bundle[kind] = event;prior_kinds.append(kind)
            assert [e['encoder'] for e in bundle['encoders']] == list(SENSORY)
            obs = bundle['coupling_start']['physical_observation']
            concentration = np.asarray(obs['antenna_odor']);occupancy = concentration/(1e8+concentration)
            odor_rates = 5+145*occupancy*(1+.5*np.clip(obs['physiology']['hunger'],0,1))/(1+adaptation)
            adaptation += (occupancy-adaptation)*(1-np.exp(-DT/.3))
            expected_indices = [np.concatenate(odor_groups)]
            expected_rates = [np.repeat(odor_rates,[len(g) for g in odor_groups])]
            for index,members in enumerate((taste_groups,club_groups)):
                rates = (np.array([100. if obs['food_contact_by_leg'][leg] else 0. for leg in LEGS]) if index == 0 else
                    30*np.abs(previous['tibia_velocity_rad_s'])/(5+np.abs(previous['tibia_velocity_rad_s'])))
                active = [(g,r) for g,r in zip(members,rates,strict=True) if r > 0]
                expected_indices.append(np.concatenate([g for g,_ in active]) if active else np.array([],dtype=int))
                expected_rates.append(np.concatenate([np.full(len(g),r) for g,r in active]) if active else np.array([]))
            for encoder,index_array,rates in zip(bundle['encoders'],expected_indices,expected_rates,strict=True):
                same(encoder['actual_drive']['indices'],index_array)
                maxima['encoder_rate_error_hz'] = max(maxima['encoder_rate_error_hz'],same(encoder['actual_drive']['rates_hz'],rates,1e-12))
            if design['assay'] == 'motor_probe':
                expected_indices.append(groups['motor_forward']);expected_rates.append(np.full(len(groups['motor_forward']),40.))
            drive_check(event['actual_drive'],ids)
            same(event['actual_drive']['indices'],np.concatenate(expected_indices))
            same(event['actual_drive']['rates_hz'],np.concatenate(expected_rates),1e-12)
            assert event['rng_state'] == [rng] and event['duration_ms'] == 2.
            same(event['brain_t_ms'],tick*2.,1e-9)
        elif kind == 'ordered_spikes':
            bundle[kind] = event;prior_kinds.append(kind)
            event_ids,times = spikes.next(event)
            indices = np.searchsorted(ids,event_ids)
            assert (indices < len(ids)).all()
            same(ids[indices],event_ids)
            same([event['start_ms'],event['end_ms']],[tick*2.,(tick+1)*2.],1e-9)
            assert np.isfinite(times).all() and (times >= event['start_ms']).all() and (times < event['end_ms']).all()
            nticks = np.rint(times/.1).astype(np.int64)
            same(times,nticks*.1)
            assert (np.diff(nticks) >= 0).all()
            if len(indices) > 1: assert np.all((np.diff(nticks) > 0) | (np.diff(indices) > 0))
            listed = np.zeros(len(ids),bool)
            listed[np.asarray(bundle['neural_start']['actual_drive']['indices'],dtype=int)] = True
            ordinary = ~listed[indices]
            assert np.all(nticks[ordinary]-last_spike[indices[ordinary]] >= 22)
            # A 20-tick batch is shorter than ordinary refractory duration.
            assert len(np.unique(indices[ordinary])) == int(ordinary.sum())
            np.maximum.at(last_spike,indices,nticks)
            delivered_at = (nticks+18)//20
            unblocked = ~blocked[indices]
            np.add.at(edge_schedule,delivered_at[unblocked],degree[indices[unblocked]])
            pending_tail = [(int(t),int(i)) for t,i in zip(nticks,indices,strict=True) if t+18 >= (tick+1)*20]
            totals['lossless_spikes'] += len(indices)
            bundle['spike_arrays'] = (event_ids,times,indices)
        elif kind == 'neural_complete':
            bundle[kind] = event;prior_kinds.append(kind)
            event_ids,times,indices = bundle['spike_arrays']
            assert event['tick'] == tick and event['total_spikes'] == len(indices)
            assert event['full_event_sha256'] == event_hash(event_ids,times) == bundle['ordered_spikes']['event_sha256']
            assert event['downstream_event_sha256'] == event_hash(event_ids[~sensory_mask[indices]],times[~sensory_mask[indices]])
            assert event['traversed_edges'] == int(edge_schedule[tick])
            allids,counts = np.unique(event_ids,return_counts=True)
            expected = dict(spikes=len(indices),event_sha256=event_hash(event_ids,times),neuron_ids=allids.tolist(),counts=counts.tolist())
            assert event['all_neuron_counts'] == expected
            for group,mask in group_masks.items():
                keep = mask[indices];unique,count = np.unique(event_ids[keep],return_counts=True)
                assert event['sensory_and_motor_events'][group] == dict(spikes=int(keep.sum()),event_sha256=event_hash(event_ids[keep],times[keep]),neuron_ids=unique.tolist(),counts=count.tolist())
                assert event['monitored_counts'][group] == int(keep.sum())
                if group.startswith('motor_'):
                    instantaneous = int(keep.sum())/len(groups[group])/DT
                    rate_state[group] += (1-np.exp(-DT/.05))*(instantaneous-rate_state[group])
            assert event['blocked_neuron_count'] == int(blocked.sum())
            assert event['sensory_outgoing_mask'] == bool(blocked[sensory_mask].all())
            assert event['ordered_drive_sha256'] == bundle['neural_start']['actual_drive']['ordered_drive_sha256']
            assert event['rng_state_before'] == [rng]
            draws = 20*len(bundle['neural_start']['actual_drive']['indices'])
            rng = rng_after(rng,draws)
            assert event['rng_state_after'] == [rng]
            totals['RNG_draws_checked'] += draws
            for encoder in bundle['encoders']:
                rates = encoder['actual_drive']['rates_hz'];group = encoder['encoder']
                assert event['positive_input_cells_by_encoder'][group] == np.count_nonzero(np.asarray(rates)>0)
                assert event['max_input_event_rate_hz_by_encoder'][group] == max(rates,default=0.)
                maxima['input_rate_'+group] = max(maxima['input_rate_'+group],max(rates,default=0.))
            assert event['listed_input_refractory_zero']
            if not event['finite_voltage'] or not event['finite_synaptic_state']: unhealthy.append(dict(tick=tick,kind='neural_nonfinite'))
            voltage_min = min(voltage_min,event['voltage_mv']['min']);voltage_max = max(voltage_max,event['voltage_mv']['max'])
            neural_meta.append({k:event[k] for k in ('tick','ordered_drive_sha256','downstream_event_sha256','rng_state_before','rng_state_after')})
        elif kind == 'physical_returned':
            bundle[kind] = event;prior_kinds.append(kind)
            d,state,phys,muted,healthy = check_physical(bundle,previous,initial['state']['physiology'],previous_phys,metadata,rate_state,groups,plan,design,maxima)
            physical_count += 1
            if not healthy: unhealthy.append(dict(tick=tick,kind='native_flags',finite=d['finite'],source_terminated=d['source_terminated'],warnings=d['warnings']))
            if prefix: prefix.compare(bundle)
            positions.append(np.asarray(d['pose_cm_quat'][:2])*10)
            bundle_previous_state = state
        elif kind == 'physical_complete':
            bundle[kind] = event;prior_kinds.append(kind)
            assert event['tick'] == tick and event['checks']['tick'] == tick+1
            complete_count += 1
            neural = bundle['neural_complete'];d = bundle['physical_returned']['diagnostics'];state = bundle['physical_returned']['state']
            summary = event['checks']
            same(summary['clock_max_error_s'],max(abs(state['t_s']-(tick+1)*DT),abs(state['brain_t_s']-(tick+1)*DT),abs(d['native_time_s']-(tick+1)*DT)))
            same(summary['resource_residual_max'],max(abs(v) for v in state['resource_balance'].values()))
            assert summary['finite_native_arrays'] and summary['native_tick'] == d['tick']
            assert summary['producer_finite_flag'] == d['finite'] and summary['source_terminated'] == d['source_terminated']
            assert summary['warnings'] == d['warnings'] and summary['motor'] == state['motor']
            assert summary['neutral_hold_required'] == (not d['command']['policy_enabled'])
            if summary['neutral_hold_required']: assert summary['neutral_hold_exact']
            else: assert summary['native_policy_action_exact']
            assert state['neural']['blocked_synaptic_outputs'] == sorted(design['outgoing_blocks'])
            totals['completed_spikes'] += neural['total_spikes'];totals['completed_edge_visits'] += neural['traversed_edges']
            for g,c in neural['monitored_counts'].items(): totals[g] += c
            behavior[state['motor']['behavior']] += 1
            assert state['neural']['total_spikes'] == totals['completed_spikes'] and state['neural']['spikes'] == neural['total_spikes']
            for window in muted_windows:
                if window['first_tick'] <= tick < window['end_tick']:
                    window['completed_ticks'] += 1;window['neural_spikes'] += neural['total_spikes']
            maxima['qacc_abs_native'] = max(maxima['qacc_abs_native'],max(abs(v) for v in d['qacc']))
            records.append(dict(tick=tick,up_z=d['up_z'],voltage_min=neural['voltage_mv']['min'],voltage_max=neural['voltage_mv']['max']))
            previous,previous_phys = d,state['physiology']
        elif kind == 'condition_failure': failure_events.append(event['failure'])
        elif kind in ('actual_state_retained','state_retention_failure','cleanup_failure'): pass
        elif kind == 'condition_end':
            assert event['complete'] == condition['complete']
            assert event['returned_physical_ticks'] == physical_count
            assert event['validated_physical_ticks'] == condition['validated_physical_ticks']
        else: raise AssertionError('Unknown journal event: '+kind)

    journal.finish(condition['journal']);spikes.finish(condition['lossless_spikes'])
    assert sum(event_counts.values()) == condition['journal']['records']
    assert event_counts['condition_start'] == event_counts['initial'] == event_counts['condition_end'] == 1
    assert event_counts['ordered_spikes'] == spikes.blocks
    assert physical_count == condition['returned_physical_ticks'] == condition['completed_physical_ticks']
    assert condition['validated_physical_ticks'] <= complete_count <= physical_count
    assert failure_events == [f for f in condition['failures'] if 'type' in f]
    expected_interventions = [(kind,edge) for pair in plan['mute_intervals_ticks'] for edge in pair
        if edge < event_counts['coupling_start'] for kind in ('intervention_start','intervention_complete')] if design['motor_mute'] else []
    assert interventions == expected_interventions
    metrics = condition['metrics']
    assert metrics['completed_coupling_spikes'] == totals['completed_spikes']
    assert metrics['completed_coupling_edge_visits'] == totals['completed_edge_visits']
    assert metrics['monitored_spikes'] == {g:totals[g] for g in groups}
    assert metrics['behavior_counts'] == dict(behavior) and metrics['mute_intervals'] == muted_windows
    if records:
        same(metrics['min_voltage_mv'],min(r['voltage_min'] for r in records))
        same(metrics['max_voltage_mv'],max(r['voltage_max'] for r in records))
        same(metrics['min_up_z'],min(r['up_z'] for r in records))
        same(metrics['max_abs_qacc_native'],maxima['qacc_abs_native'])
        same(metrics['max_clock_error_s'],maxima['clock_error_s'])
        same(metrics['max_resource_residual'],maxima['resource_residual'])
    points = np.asarray(positions)
    path = float(np.linalg.norm(np.diff(points,axis=0),axis=1).sum())
    same(metrics['planar_path_mm'],path,1e-10)
    prefix_report = None
    if prefix:
        prefix.finish()
        prefix_report = dict(matched_ticks=prefix.count,differences=prefix.differences,
            matched_content_sha256=prefix.digest.hexdigest())
        if not prefix.differences and prefix.count == condition['original_prefix']['checked_ticks']:
            assert prefix.digest.hexdigest() == condition['original_prefix']['matched_content_sha256']
        assert condition['original_prefix']['passed'] == (condition['original_prefix']['checked_ticks'] == 1000)
    retained_receipt = condition['actual_final_or_failure_state']
    retained = read(ROOT/retained_receipt['state']['path'])
    assert sha(ROOT/retained_receipt['state']['path']) == retained_receipt['state']['sha256']
    assert retained['stage_clocks'] == retained_receipt['stage_clocks']
    assert retained['stage_clocks']['host_physiology_t_s'] is None
    cp_receipt = retained_receipt['brain_checkpoint'];assert sha(ROOT/cp_receipt['path']) == cp_receipt['sha256']
    with np.load(ROOT/cp_receipt['path'],allow_pickle=False) as archive:
        checkpoint = {k:archive[k] for k in archive.files}
    meta = json.loads(str(checkpoint.pop('metadata')))
    assert meta['graph_sha256'] == plan['graph_sha256'] and meta['parameters'] == plan['neural_parameters']
    assert meta['tick'] == spikes.blocks*20 and meta['tick']*.1 == retained['brain_time_ms']
    same(checkpoint['last_spike_tick'],last_spike)
    same(checkpoint['ablated'],blocked)
    same(checkpoint['rng_state'],[rng])
    same(checkpoint['current_mv'],np.zeros(len(ids)))
    assert np.isfinite(checkpoint['voltage_mv']).all() and np.isfinite(checkpoint['synaptic_mv']).all()
    same(checkpoint['voltage_mv'].min(),bundle['neural_complete']['voltage_mv']['min'])
    same(checkpoint['voltage_mv'].max(),bundle['neural_complete']['voltage_mv']['max'])
    by_slot = [[] for _ in range(19)]
    for t,i in pending_tail: by_slot[(t+18)%19].append(i)
    same(checkpoint['pending_count'],[len(v) for v in by_slot])
    same(checkpoint['pending'],np.asarray([i for slot in by_slot for i in slot],dtype=np.int32))
    previous_drive = np.asarray(bundle['neural_start']['actual_drive']['indices'])
    same(checkpoint['previous_drive'],previous_drive)
    expected_refractory = np.full(len(ids),22,dtype=np.int64);expected_refractory[previous_drive] = 0
    same(checkpoint['refractory_ticks'],expected_refractory)
    final_native = retained['cached_native_state']
    assert retained['completed_coupling_spikes'] == totals['completed_spikes']
    assert retained['completed_coupling_edge_visits'] == totals['completed_edge_visits']
    assert retained['latest_lossless_neural_batch'] == spikes.last
    final_array_finite = {}
    for key in ('qpos','qvel','qacc','act','ctrl','native_action','actuator_force_preceding_stage'):
        values = final_native.get(key,[])
        final_array_finite[key] = all(isinstance(v,(int,float)) and np.isfinite(v) for v in values)
    native_summary = dict(native_time_s=final_native.get('native_time_s'),tick=final_native.get('tick'),
        finite_flag=final_native.get('finite'),source_terminated=final_native.get('source_terminated'),
        warnings=final_native.get('warnings'),retained_array_finiteness=final_array_finite,
        brain_minus_native_s=retained['brain_time_ms']/1000-final_native['native_time_s'],
        cached_observation_t_s=retained['cached_physical_observation']['t_s'])
    if condition['complete']:
        assert final_native == previous and retained['cached_physical_observation']['t_s'] == previous['native_time_s']
        assert physical_count == complete_count == spikes.blocks == plan['ticks']
        assert not failure_events and not unhealthy
        assert prior_kinds == ['coupling_start','encoder','encoder','encoder','neural_start','ordered_spikes','neural_complete','physical_returned','physical_complete']
    independently_checkable_gates = (physical_count == complete_count == spikes.blocks == plan['ticks']
        and condition['validated_physical_ticks'] == plan['ticks'] and not failure_events and not unhealthy
        and (prefix is None or (prefix.count == plan['initial_prefix_ticks'] and not prefix.differences))
        and condition['worker_exit_code_after_close'] is not None and all(final_array_finite.values()))
    if condition['all_condition_gates_pass']:
        assert independently_checkable_gates
    return dict(condition=name,producer_complete=condition['complete'],producer_gates_pass=condition['all_condition_gates_pass'],
        independently_checkable_gates_pass=independently_checkable_gates,
        closed_journal_verified=True,physical_returned_ticks=physical_count,physical_summary_ticks=complete_count,
        producer_validated_ticks=condition['validated_physical_ticks'],lossless_neural_batches=spikes.blocks,
        lossless_spikes=spikes.events,completed_physical_spikes=totals['completed_spikes'],
        pending_physical_batch_spikes=spikes.events-totals['completed_spikes'],totals=dict(totals),behavior=dict(behavior),
        mute_windows=muted_windows,maxima=dict(maxima),minimum_sampled_voltage_mv=voltage_min,maximum_sampled_voltage_mv=voltage_max,
        planar_path_mm_2ms_chords=path,net_planar_displacement_mm=float(np.linalg.norm(points[-1]-points[0])),
        prefix=prefix_report,failures=condition['failures'],unhealthy_completed_records=unhealthy,
        final_native_state=native_summary,
        stage_clocks=retained['stage_clocks'],worker_exit_code=condition['worker_exit_code_after_close'],
        retained_files_verified=len(condition['files']),final_checkpoint_verified=True,
        journal_sha256=condition['journal']['sha256'],spikes_sha256=condition['lossless_spikes']['sha256']),neural_meta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--available',action='store_true')
    args = parser.parse_args()
    plan,results = read(OUT/'plan.json'),read(OUT/'results.json')
    assert sha(OUT/'plan.json') == results['plan_sha256'] == '3e5ca3ca6c91bbd240ff2530d351fd010dc5001e19078e2270a95022449c2498'
    if not results['complete'] and not args.available:
        raise SystemExit('Producer still running; use --available only for closed condition receipts.')
    if not results['conditions']:
        print('No closed condition receipts yet; active gzip streams were not read.');return
    sources = {}
    for path,expected in plan['source_sha256'].items():
        proc = subprocess.run(['git','show',plan['source_revision']+':'+path],cwd=ROOT,capture_output=True)
        data = proc.stdout if proc.returncode == 0 else (ROOT/path).read_bytes()
        actual = hashlib.sha256(data).hexdigest();assert actual == expected,path
        sources[path] = dict(sha256=actual,origin=plan['source_revision'] if proc.returncode == 0 else 'local ignored data')
    arrays = {name:np.load(ROOT/('data/processed/malecns_v1/'+name+'.npy'),mmap_mode='r',allow_pickle=False)
              for name in ('neuron_ids','indptr','targets','weights')}
    fingerprint = hashlib.sha256()
    for value in arrays.values(): fingerprint.update(str(value.shape).encode());fingerprint.update(memoryview(value).cast('B'))
    assert fingerprint.hexdigest() == plan['graph_sha256']
    ids = arrays['neuron_ids'];assert len(ids) == 166700 and len(arrays['targets']) == 25582938
    assert np.all(np.diff(ids)>0)
    degree = np.diff(arrays['indptr'])
    neurons = pd.read_feather(ROOT/'data/processed/malecns_v1/neurons.feather',columns=['bodyId','type','rootSide','somaSide','entryNerve'])
    same(neurons.bodyId.values,ids)
    group_info = source_groups(neurons)
    reviews,histories = [],[]
    for condition in results['conditions']:
        review,history = review_condition(condition,plan,ids,degree,neurons,group_info)
        reviews.append(review);histories.append(history)
        print(condition['condition'],review['physical_returned_ticks'],'physical ticks',review['lossless_spikes'],'ordered spikes checked',flush=True)
    paired = None
    if len(histories) >= 2:
        matched = True;first_input=first_downstream=first_under_matched=None
        for left,right in zip(histories[0],histories[1]):
            if left['ordered_drive_sha256'] != right['ordered_drive_sha256']:
                matched = False
                if first_input is None: first_input = left['tick']
            if matched:
                assert left['rng_state_before'] == right['rng_state_before'] and left['rng_state_after'] == right['rng_state_after']
            if left['downstream_event_sha256'] != right['downstream_event_sha256']:
                if first_downstream is None: first_downstream = left['tick']
                if matched and first_under_matched is None: first_under_matched = left['tick']
        paired = dict(paired_neural_intervals=min(map(len,histories[:2])),first_ordered_input_difference_tick=first_input,
            first_non_sensory_spike_event_difference_tick=first_downstream,
            first_downstream_difference_with_identical_input_history_tick=first_under_matched)
        if results['complete']:
            for key,value in paired.items(): assert results['locomotor_paired_mechanisms'][key] == value
    if results['complete']:
        assert len(reviews) == 3 and all(results['source_hashes_unchanged_after'].values())
        assert results['all_declared_gates_pass'] == all(r['producer_gates_pass'] for r in reviews)
    receipt = dict(created_utc=datetime.now(timezone.utc).isoformat(),passed_saved_record_checks=True,
        all_attempts_concluded=results['complete'],all_declared_experiment_gates_pass=results.get('all_declared_gates_pass'),
        scope='Independent saved gzip/binary-array/source review; no neural, policy or physical simulation.',
        plan_sha256=sha(OUT/'plan.json'),results_sha256=sha(OUT/'results.json'),reviewer_sha256=sha(__file__),
        frozen_sources=sources,graph_sha256=fingerprint.hexdigest(),conditions=reviews,paired_mechanisms=paired,
        limits=[
            'Closed condition-summary receipts are required. No active/truncated gzip is counted as a completed attempt.',
            'All full ordered spike IDs/times are independently hashed and counted, including retained neural batches preceding a failed physical return.',
            'Delayed edge visits count unblocked source outdegrees at delivery time, including edges whose target is refractory. They are not counts of successful postsynaptic updates.',
            'RNG transition reconstruction checks 20 draws per listed input index, including zero rates. Actual Bernoulli draws and applied input-event masks are not journaled in this experiment.',
            'Complete voltage/synaptic/mask state exists only in the final checkpoint. Per-interval finite/mask flags and voltage extrema remain producer assertions corroborated by the final arrays.',
            'Actor-input digests are retained, but full 741-value actor arrays and complete 66-frame references are absent from these journals. Separate bridge evidence establishes actor parity; current target integration and per-step sizes/counters are independently checked here.',
            'Initial reset/render/advance0 equality and worker reaping are producer receipts; initial/post-render comparison arrays and operating-system process history are not independently retained.',
            'Puff positions and full field state are absent. Recorded concentrations and encoder mappings are checkable; exact spatial plume sampling remains producer evidence.',
            'No independent host physiology elapsed-time clock exists. Failure clocks are reported separately without assigning cached host state the native clock.',
            'Graph transmission or motor-probe locomotion does not establish physiological firing/voltage, natural navigation, male body mechanics, reproduction, or indefinite stability.'
        ])
    (OUT/'independent-review.json').write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed_saved_record_checks=True,all_attempts_concluded=results['complete'],conditions=len(reviews)),indent=2))


if __name__ == '__main__':
    main()
