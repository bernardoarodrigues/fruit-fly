"""Independent scalar-loop checks of the full AHP measurement batch."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pyabf
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/apl-ahp-measurement-review.json'


def reference(t,v,bounds,post,floor):
    b0,b1=bounds;p0,p1=post;base=math.fsum(map(float,v[b0:b1]))/(b1-b0)
    peak=min(range(p0,p1),key=lambda k:v[k]);amplitude=base-float(v[peak])
    cross={}
    if amplitude>floor:
        for level in (.7,.3):
            down=[];up=[]
            for k in range(peak,p1-1):
                x=(base-float(v[k]))/amplitude-level;y=(base-float(v[k+1]))/amplitude-level
                if (x>0 and y<=0) or (x<=0 and y>0):
                    stamp=float(t[k]+(t[k+1]-t[k])*x/(x-y))
                    (down if x>0 else up).append(stamp)
            cross[f'down_{round(level*100)}_s']=down;cross[f'up_{round(level*100)}_s']=up
    return base,amplitude,float(t[peak]),cross


def main():
    if OUT.exists():raise FileExistsError('Preserve review')
    p=json.loads((ROOT/'validation/apl-ahp-measurement-plan.json').read_text())
    r=json.loads((ROOT/'validation/apl-ahp-measurements.json').read_text())
    checks=0;maximum=0.;rows=[]
    def compare(x,y):
        nonlocal checks,maximum
        error=abs(x-y);maximum=max(maximum,error);assert error<1e-9,(x,y);checks+=1
    for f,src in zip(r['files'],p['files'],strict=True):
        assert f['member']==src['member'];a=pyabf.ABF(str(ROOT/src['extracted_path']));voltage=[]
        for sweep in f['sweeps']:
            a.setSweep(sweep['sweep'],channel=0);voltage.append(a.sweepY.copy())
        # Independent mean accumulation using a stack/reduction rather than producer loop.
        all_traces=voltage+[np.mean(np.stack(voltage),axis=0,dtype=np.float64)]
        measured=[s['measurements'] for s in f['sweeps']]+[f['mean_trace_measurements']]
        for signal,variants in zip(all_traces,measured,strict=True):
            for post,saved in zip(f['post_sample_ranges'],variants,strict=True):
                base,amp,peak,cross=reference(a.sweepX,signal,f['baseline_sample_range'],post,p['minimum_amplitude_mV'])
                for x,y in ((base,saved['held_baseline_mV']),(amp,saved['amplitude_mV']),(peak,saved['peak_time_s'])):compare(x,y)
                if not cross:
                    assert saved['status']=='insufficient_ahp_amplitude' and saved['recovery_70_to_30_s'] is None
                else:
                    for key,stamps in cross.items():
                        assert len(stamps)==len(saved['crossings'][key])
                        for x,y in zip(stamps,saved['crossings'][key],strict=True):compare(x,y)
                    down70=cross['down_70_s'];down30=cross['down_30_s']
                    if down70 and down30:
                        ordered=[x for x in down30 if x>=down70[0]]
                        if ordered:
                            compare(ordered[0]-down70[0],saved['recovery_70_to_30_s'])
                            ambiguous=len(down70)>1 or len(down30)>1 or bool(cross['up_70_s']) or bool(cross['up_30_s'])
                            assert saved['status']==('ambiguous_recrossings' if ambiguous else 'measured')
                    else:assert saved['status']=='incomplete_recovery_window'
                checks+=1
        q=f['mean_trace_measurements'];author=f['author_row'];original=author['row_values']
        rows.append(dict(cell=author['cell'],fly=author['fly'],genotype=author['genotype'],sweeps=len(f['sweeps']),
            mean_trace_amplitude_mV=q[0]['amplitude_mV'],author_amplitude_mV=-original['G1'],
            mean_trace_first_interval_s=q[0]['recovery_70_to_30_s'],author_interval_s=original['H1']/1000,
            mean_trace_status=q[0]['status'],peak_delay_s=q[0]['peak_time_s']-f['offset_sample']/f['sample_rate_Hz'],
            amplitude_change_20ms_start_mV=q[1]['amplitude_mV']-q[0]['amplitude_mV'],
            scope='Author interval interpreted in ms using inspected Figure 4J axis. First crossing remains flagged and is not a fitted kinetic parameter.'))
    deliveries=[s['delivery']['delta_current_pA'] for f in r['files'] for s in f['sweeps'] if s['delivery']]
    summary=dict(completed_utc=datetime.now(timezone.utc).isoformat(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        result_sha256=hashlib.sha256((ROOT/'validation/apl-ahp-measurements.json').read_bytes()).hexdigest(),
        scalar_and_status_checks=checks,max_absolute_error=maximum,
        primary_sweep_status_counts=dict(Counter(s['measurements'][0]['status'] for f in r['files'] for s in f['sweeps'])),
        mean_trace_status_counts=dict(Counter(f['mean_trace_measurements'][0]['status'] for f in r['files'])),
        recorded_current_count=len(deliveries),recorded_current_min_max_pA=[min(deliveries),max(deliveries)],
        all_recorded_deliveries_within_tolerance=all(s['delivery']['within_tolerance'] for f in r['files'] for s in f['sweeps'] if s['delivery']),
        mean_trace_comparisons=rows,
        scope='Complete scalar measurement/crossing reproduction with same pyABF decoder. No threshold retuning, smoothing, fit or promotion. Source amplitude comparisons are all-sweep means versus author-selected analysis, not an exact reproduction.')
    OUT.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='mean_trace_comparisons'},indent=2))


if __name__=='__main__':main()
