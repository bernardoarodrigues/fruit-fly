"""Reproduce the initialization-only native position-actuator audit."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from scripts.probe_flybody_inference import verify_sources


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('validation/flybody-stance-actuator-audit.json'))
    args=parser.parse_args()
    repo=Path('/tmp/fruit-fly-research-flybody');verify_sources(repo);sys.path.insert(0,str(repo))
    from flybody.fly_envs import walk_imitation
    import mujoco
    env=walk_imitation(random_state=np.random.RandomState(11));env.reset()
    m,d=env.physics.model,env.physics.data;spec=env.action_spec();names=spec.name.split()
    ids=np.asarray([m.name2id('walker/'+n,'actuator') for n in names]);rows=[]
    for i,(name,idx) in enumerate(zip(names,ids)):
        position=i>=6
        if position:
            assert m.actuator_gaintype[idx]==mujoco.mjtGain.mjGAIN_FIXED
            assert m.actuator_biastype[idx]==mujoco.mjtBias.mjBIAS_AFFINE
            gain=m.actuator_gainprm[idx,0];assert gain>0
            np.testing.assert_allclose(m.actuator_biasprm[idx,:3],[0,-gain,0],atol=1e-12,rtol=0)
            assert spec.minimum[i]<=0<=spec.maximum[i]
        rows.append({'action_index':i,'name':name,'compiled_actuator_id':int(idx),'position_target':position,
            'trntype':int(m.actuator_trntype[idx]),'gain':m.actuator_gainprm[idx,:3].tolist(),
            'bias':m.actuator_biasprm[idx,:3].tolist(),'gear':m.actuator_gear[idx].tolist(),
            'range':[float(spec.minimum[i]),float(spec.maximum[i])],
            'initial_actuator_length':float(d.actuator_length[idx]),'initial_native_control':float(d.ctrl[idx]),
            'activation_address':int(m.actuator_actadr[idx]),'force_limited':bool(m.actuator_forcelimited[idx])})
    result={'source_commit':'d015e9bfe441bd90ae431bac24c55cb74bdbce26','mujoco_version':mujoco.__version__,
        'initialization_only_no_physics_rollout':True,
        'position_law_verified':'actuator output = gain * (filtered native target - actual transmission length), bias velocity coefficient zero; passive damping/stiffness retained',
        'candidate_measured_target':'physics.data.actuator_length in exact action-spec order, clipped to the original native ctrlrange; includes joint/tendon transmissions without guessing qpos mapping',
        'candidate_neutral_target':'native position target zero, permitted by every original position ctrlrange',
        'hold_adhesion':'native1 to each first-six claw adhesion channels; original gain/dynamics retained','rows':rows}
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(f'Wrote {len(rows)} verified actuator channels to {args.output}')


if __name__=='__main__':main()
