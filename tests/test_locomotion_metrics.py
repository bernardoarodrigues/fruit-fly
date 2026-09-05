"""Analytic kinematic controls for the independent walking benchmark."""
import numpy as np
from scipy.spatial.transform import Rotation

from scripts.benchmark_freewalking import native_kinematics, leg_cycles


def test_quaternion_log_handles_sign_flips_and_heading_wrap():
    t=np.arange(801)/800
    rotation=Rotation.from_euler('z',(2*np.pi*t)[:,None])
    xyzw=rotation.as_quat()
    quat=xyzw[:,[3,0,1,2]]
    quat[::2]*=-1  # same rotation; four-coordinate differentiation would fail
    joints=(.4*np.sin(2*np.pi*10*t))[:,None]
    q=np.c_[2*t,-t,t*0,quat,joints]
    result=native_kinematics(q,800,10)
    assert result['velocity_world_mm_s'].shape==(800,3)
    np.testing.assert_allclose(result['velocity_world_mm_s'],np.tile([20,-10,0],(800,1)),atol=1e-10)
    np.testing.assert_allclose(result['angular_world_rad_s'],np.tile([0,0,2*np.pi],(800,1)),atol=1e-10)
    np.testing.assert_allclose(result['turn_rad_s'],2*np.pi,atol=1e-10)
    expected=np.diff(joints,axis=0)*800
    np.testing.assert_allclose(result['joint_velocity_rad_s'],expected)
    assert result['interval_midpoint_s'][0]==.5/800
    assert result['interval_midpoint_s'][-1]==799.5/800


def test_leg_cycle_frequency_recovers_known_positive_speed_pulses():
    fps=800
    t=np.arange(1601)/fps
    # Position derivative = 10 + 8 sin(2pi*10t), always positive and one
    # speed pulse per cycle. Absolute cosine would spuriously double frequency.
    x=10*t-8*np.cos(2*np.pi*10*t)/(2*np.pi*10)
    cycles,quality=leg_cycles(np.c_[x,0*t,0*t],fps)
    frequencies=np.array([fps/(b-a) for a,b in cycles])
    assert len(cycles)>=15
    np.testing.assert_allclose(frequencies,10,atol=.15)
    assert quality['phase_reversal_rejected']==0
    assert all(a>=24 and b<1600-24 for a,b in cycles)
