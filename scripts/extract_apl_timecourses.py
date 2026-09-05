#!/usr/bin/env python3
"""Recover displayed Fig. 5 stroke envelopes, not raw biological samples."""
from pathlib import Path
import hashlib,json
import numpy as np
import pdfplumber
ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'validation/apl-timecourse-extraction-plan.json'
OUT=ROOT/'validation/apl-timecourse-extraction-results.json'
DATA=ROOT/'validation/apl-timecourse-traces.json'


def polygon_points(path,subdivisions):
    pts=[]
    for item in path:
        if item[0] in ('m','l'):pts.append(np.array(item[1],float))
        elif item[0]=='c':
            a=pts[-1];b,c,d=np.array(item[1:])
            for t in np.linspace(0,1,subdivisions+1)[1:]:
                pts.append((1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d)
        elif item[0]=='h':pts.append(pts[0])
        else:raise ValueError(item[0])
    pts=np.array(pts)
    return np.vstack([pts,pts[0]])


def section(points,x):
    a=points[:-1];b=points[1:];dx=b[:,0]-a[:,0]
    valid=((a[:,0]<=x)&(x<b[:,0]))|((b[:,0]<=x)&(x<a[:,0]))
    y=a[valid,1]+(x-a[valid,0])/dx[valid]*(b[valid,1]-a[valid,1])
    if len(y)<2:raise ValueError(f'Incomplete stroke section at {x}')
    return float(y.min()),float(y.max())


def exact_section(path,x):
    """Independent analytic line/cubic intersections; no flattening."""
    ys=[];current=None;start=None
    for item in path+([('h',)] if path[-1][0]!='h' else []):
        op=item[0]
        if op=='m':current=np.array(item[1]);start=current;continue
        if op in ('l','h'):
            b=np.array(item[1]) if op=='l' else start
            if min(current[0],b[0])<=x<max(current[0],b[0]):
                t=(x-current[0])/(b[0]-current[0]);ys.append(current[1]+t*(b[1]-current[1]))
            current=b;continue
        if op!='c':raise ValueError(op)
        a=current;b,c,d=np.array(item[1:]);current=d
        if x<min(a[0],b[0],c[0],d[0]) or x>max(a[0],b[0],c[0],d[0]):continue
        co=np.array([-a+3*b-3*c+d,3*a-6*b+3*c,-3*a+3*b,a])
        polynomial=co[:,0].copy();polynomial[-1]-=x
        for root in np.roots(np.trim_zeros(polynomial,'f')):
            if abs(root.imag)<1e-8 and 0<=root.real<1:
                t=root.real;ys.append(float(np.polyval(co[:,1],t)))
    if len(ys)<2:raise ValueError('Incomplete analytic section')
    return min(ys),max(ys)


def main():
    if OUT.exists() or DATA.exists():raise FileExistsError('Preserve completed extraction')
    plan=json.loads(PLAN.read_text())
    for s in plan['source_pins']:assert hashlib.sha256((ROOT/s['path']).read_bytes()).hexdigest()==s['sha256']
    page=pdfplumber.open(ROOT/plan['pdf']).pages[plan['page_index']]
    calcium_bar=page.lines[plan['scale_line_indices']['calcium_time']]
    dye_bar=page.lines[plan['scale_line_indices']['dye_time']]
    scales={'calcium':calcium_bar['width']/5,'dye':dye_bar['width']/5}
    heights={name:page.lines[index]['height']/plan['scale_amplitudes'][name] for name,index in plan['scale_vertical_indices'].items()}
    times=np.round(np.arange(plan['time_grid']['start'],plan['time_grid']['stop']+.001,plan['time_grid']['step']),10)
    baseline=(times>=-4)&(times<=-1);post=(times>=0)&(times<=12)
    traces=[];errors=[]
    for group in plan['groups']:
        stim=page.lines[group['stimulus_line_index']]['x0']
        xs=stim+times*scales['calcium']
        for rank,index in enumerate(group['curve_indices']):
            curve=page.curves[index]
            assert curve['fill'] and not curve['stroke'] and 45<curve['width']<52
            polygon=polygon_points(curve['path'],plan['cubic_subdivisions'])
            bounds=np.array([section(polygon,x) for x in xs]);mid=bounds.mean(1)
            refined=polygon_points(curve['path'],plan['cubic_subdivisions']*2)
            reference_ids=np.linspace(0,len(xs)-1,plan['reference_points_per_trace'],dtype=int)
            for k in reference_ids:
                exact=np.array(exact_section(curve['path'],xs[k]));fine=np.array(section(refined,xs[k]))
                err=float(max(np.abs(bounds[k]-exact).max(),np.abs(fine-exact).max()))
                assert err<plan['coordinate_atol_pt'];errors.append(err)
            base=float(mid[baseline].mean());factor=heights[group['signal']]
            signal=(base-mid)/factor
            # Envelopes include possible baseline stroke-position displacement.
            low=(bounds[baseline,0].mean()-bounds[:,1])/factor
            high=(bounds[baseline,1].mean()-bounds[:,0])/factor
            peak=int(np.flatnonzero(post)[np.argmax(signal[post])])
            row_times=times*scales['calcium']/scales[group['signal']]
            area=float(np.trapezoid(signal[post],times[post]))
            traces.append(dict(panel=group['panel'],stimulation=group['stimulation'],signal=group['signal'],
                color_rank=rank,color_rgb=curve['non_stroking_color'],pdf_curve_index=index,
                x_pdf_pt=xs.tolist(),y_center_pdf_pt=mid.tolist(),y_bounds_pdf_pt=bounds.tolist(),
                time_s_common_calcium_bar=times.tolist(),time_s_literal_row_bar=row_times.tolist(),
                baseline_pdf_pt=base,baseline_adjusted_dff=signal.tolist(),
                stroke_dff_lower=low.tolist(),stroke_dff_upper=high.tolist(),
                displayed_peak_dff=float(signal[peak]),displayed_peak_s_common_bar=float(times[peak]),
                displayed_peak_s_literal_row_bar=float(row_times[peak]),
                signed_area_0_12_common_s=area,
                area_over_peak_common_s=area/float(signal[peak]) if signal[peak]>0 else None))
    data=dict(scope='80 displayed mean curves; stroke envelopes are graphical uncertainty, not SEM. Negative values retained. No raw-frame or individual-fly claim.',traces=traces)
    with DATA.open('x') as f:json.dump(data,f,separators=(',',':'),allow_nan=False);f.write('\n')
    result=dict(status='extracted_displayed_apl_and_dye_timecourses',trace_count=len(traces),points_per_trace=len(times),
        numeric_reference_sections=len(errors),maximum_coordinate_error_pt=max(errors),
        time_scales_points_per_second=scales,amplitude_scales_points_per_dff=heights,
        dye_literal_time_multiplier=scales['calcium']/scales['dye'],
        plan_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest(),
        data=dict(path=str(DATA.relative_to(ROOT)),bytes=DATA.stat().st_size,sha256=hashlib.sha256(DATA.read_bytes()).hexdigest()),
        raw_sample_count_known=False,fit_performed=False,runtime_changed=False,
        caveats=plan['caveats'])
    with OUT.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
