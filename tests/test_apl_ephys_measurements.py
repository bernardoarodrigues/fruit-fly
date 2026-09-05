import numpy as np
import pytest
from scripts.apl_ephys_measurements import passive_resistance,fit_step_exponential,ahp_recovery


def test_passive_resistance_units_and_holding_offset():
    t=np.arange(-2000,10001)/10000
    v=np.full(len(t),-61.);i=np.full(len(t),-137.)
    step=(t>=0)&(t<.5);i[step]-=50;v[step]-=6*(1-np.exp(-t[step]/.01))
    r=passive_resistance(t,v,i,baseline_window_s=(-.2,-.05),plateau_window_s=(.4,.5),minimum_current_step_pA=1)
    assert r['resistance_MOhm']==pytest.approx(120,abs=1e-9)
    assert r['held_baseline_mV']==-61 and r['baseline_current_pA']==-137
    f=fit_step_exponential(t,v,onset_s=0,fit_window_s=(.0005,.1),tau_bounds_s=(.0001,1),minimum_voltage_span_mV=.1)
    assert f['tau_s']==pytest.approx(.01,rel=1e-6)
    assert f['asymptote_mV']==pytest.approx(-67,abs=1e-6)
    assert f['extrapolated_onset_mV']==pytest.approx(-61,abs=1e-6)
    assert not f['at_tau_bound'] and f['linear_design_rank']==2
    # Flat voltage does not return an arbitrary kinetic estimate.
    flat=fit_step_exponential(t,np.full(len(t),-60.),onset_s=0,fit_window_s=(0,.1),tau_bounds_s=(.0001,1),minimum_voltage_span_mV=.1)
    assert flat['tau_s'] is None and flat['status']=='insufficient_voltage_span'
    no_step=passive_resistance(t,v,np.zeros(len(t)),baseline_window_s=(-.2,-.05),plateau_window_s=(.4,.5),minimum_current_step_pA=1)
    assert no_step['resistance_MOhm'] is None


@pytest.mark.parametrize('tau',[.02,.1,.3])
def test_ahp_recovery_is_interval_not_tau(tau):
    t=np.arange(-2000,20001)/10000;v=np.full(len(t),-60.)
    v[t>=0]-=3*np.exp(-t[t>=0]/tau)
    r=ahp_recovery(t,v,baseline_window_s=(-.2,-.05),post_offset_window_s=(0,1.5),minimum_amplitude_mV=.2)
    assert r['status']=='measured' and r['amplitude_mV']==pytest.approx(3)
    assert r['recovery_70_to_30_s']==pytest.approx(tau*np.log(7/3),abs=2e-7)
    assert r['recovery_70_to_30_s']!=pytest.approx(tau,rel=.01)


def test_incomplete_weak_and_ambiguous_ahp_are_retained():
    t=np.arange(-2000,10001)/10000;v=np.full(len(t),-60.);post=t>=0
    v[post]-=.05*np.exp(-t[post]/.2)
    weak=ahp_recovery(t,v,baseline_window_s=(-.2,-.05),post_offset_window_s=(0,.8),minimum_amplitude_mV=.2)
    assert weak['status']=='insufficient_ahp_amplitude' and weak['recovery_70_to_30_s'] is None
    v[post]=-60-3*np.exp(-t[post]/.2)
    short=ahp_recovery(t,v,baseline_window_s=(-.2,-.05),post_offset_window_s=(0,.1),minimum_amplitude_mV=.2)
    assert short['status']=='incomplete_recovery_window' and short['crossings']['down_70_s']
    v[post]-=1.5*np.exp(-((t[post]-.4)/.015)**2)
    noisy=ahp_recovery(t,v,baseline_window_s=(-.2,-.05),post_offset_window_s=(0,.8),minimum_amplitude_mV=.2)
    assert noisy['status']=='ambiguous_recrossings' and len(noisy['crossings']['down_30_s'])>1


def test_bad_units_arrays_and_windows_do_not_silently_clip():
    t=np.array([0.,.1,.2,.3]);v=np.zeros(4)
    with pytest.raises(ValueError):passive_resistance(t,v,v,baseline_window_s=(-1,.1),plateau_window_s=(.1,.3),minimum_current_step_pA=1)
    with pytest.raises(ValueError):ahp_recovery([0,.1,.1,.3],v,baseline_window_s=(0,.1),post_offset_window_s=(.1,.3),minimum_amplitude_mV=.1)
    with pytest.raises(ValueError):fit_step_exponential(t,v,onset_s=.2,fit_window_s=(0,.3),tau_bounds_s=(.001,1),minimum_voltage_span_mV=.1)
