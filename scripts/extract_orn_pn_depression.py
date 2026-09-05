#!/usr/bin/env python3
"""Fig8F native-raster digitization only. Prepare freezes choices before conversion.

Bundled Python supplies pdfplumber/Pillow; project Python supplies matplotlib
for --plot. No PDF authoring, fitting, normalization inference or model imports.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import io
import json
import traceback

ROOT=Path(__file__).resolve().parents[1]
PDF='data/raw/orn-pn-physiology/kazama-wilson-2008.pdf'
PDF_SHA='fb1d77bef1a95ca5274e57eeb7aae3be45f4d80dc972b40718fc62d4da2ddbe6'
JPEG_SHA='9a1768a2215234e65a06b9dc84b966cf4a1750496f7094fdd9efa512f73b65a9'
PIXEL_SHA='82f8dc3694d953505ad07ae5a3361a947cea84b00821aab73e689d7acc3f1230'
PREFIX=ROOT/'validation/orn-pn-depression-fig8f'
COMPONENT_ROI=[88,785,365,1025]
# IDs are deterministic top-to-bottom connected white-interior components in the ROI.
# ID1 is the legend triangle and is excluded. ID0 is one shared initial drawing.
SERIES={15:[0,2,4,7,8,9,11,12],20:[0,3,5,10,14,13,17,16,18,19],
        50:[0,6,15,20,21,29,33,38,39,40,35,32,22,37,36,31,34,25,27,41,30,23,26,24,28]}
# column and inclusive search limits; select two >=3px black runs surrounding marker.
BARS={2:[133,802,836],4:[168,811,842],7:[203,827,862],8:[238,840,861],9:[274,834,874],11:[309,849,869],12:[344,848,885],
      5:[150,830,854],10:[176,843,874],14:[203,872,936],13:[229,881,907],17:[255,880,936],16:[281,882,931],18:[308,895,932],19:[334,898,954],
      6:[108,806,880],15:[119,876,934],20:[129,906,969],21:[140,935,993],29:[150,967,1014],33:[160,981,1013],
      39:[181,991,1021],40:[192,990,1021],35:[202,989,1014],32:[213,985,1006],22:[223,964,995],37:[234,988,1018],
      36:[245,991,1014],31:[255,978,1012],34:[266,990,1007],25:[276,976,996],27:[287,978,1001],41:[297,995,1020],
      30:[308,984,1004],23:[318,966,996],26:[329,977,998],28:[350,973,1005]}
UNRESOLVED={0:'overlapping_initial_markers_and_bars_cannot_be_resolved_by_frequency',
            3:'20Hz_marker_obscures_any_separate_error_stem',38:'50Hz_marker_obscures_short_error_stem',24:'50Hz_marker_obscures_any_separate_error_stem'}
TICKS={'x':[(0,[93,1023,102,1032]),(250,[225,1023,235,1032]),(500,[356,1023,366,1032])],
       'y':[(0,[85,990,93,1002]),(50,[85,893,93,903]),(100,[85,794,93,805])]}


def out(suffix):return Path(str(PREFIX)+suffix)
def now():return datetime.now(timezone.utc).isoformat()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canon(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def record(path):return dict(path=str(Path(path).relative_to(ROOT)),bytes=Path(path).stat().st_size,sha256=sha(path))
def load(path):return json.loads(Path(path).read_text())


def source():
    import pdfplumber
    import PIL
    from PIL import Image
    import numpy as np
    from collections import deque
    assert sha(ROOT/PDF)==PDF_SHA
    with pdfplumber.open(ROOT/PDF) as d:
        p=d.pages[7];image=p.images[0];encoded=image['stream'].get_data()
        assert len(d.pages)==13 and len(p.images)==1 and image['srcsize']==(830,1090)
        assert hashlib.sha256(encoded).hexdigest()==JPEG_SHA
        im=Image.open(io.BytesIO(encoded));pixels=np.array(im)
        assert im.format=='JPEG' and im.mode=='L' and hashlib.sha256(pixels.tobytes()).hexdigest()==PIXEL_SHA
        meta=dict(source=PDF,page_index=7,page_number=8,figure='8F',embedded_image_name=image['name'],
            image_bbox_pdf_points=[image['x0'],image['top'],image['x1'],image['bottom']],native_size=[830,1090],
            encoded_sha256=JPEG_SHA,pixel_sha256=PIXEL_SHA,encoding='DCTDecode/JPEG,8bit,DeviceGray',
            page_object_counts={k:len(v) for k,v in p.objects.items()},
            no_panel_vector_geometry='All ten page curves are publisher logo paths; figure8 is one raster image.',
            parser=dict(pdfplumber=pdfplumber.__version__,Pillow=PIL.__version__),
            figure_caption=p.extract_text().split('releaseisalso')[0],
            pixel_coordinate_convention='Integer pixel centers, native embedded image, x right and y downward; no enlarged-image measurements.')
    x0,y0,x1,y1=COMPONENT_ROI;white=pixels[y0:y1,x0:x1]>=160
    visited=np.zeros(white.shape,bool);components=[];label_id=0
    for row in range(white.shape[0]):
        for col in range(white.shape[1]):
            if not white[row,col] or visited[row,col]:continue
            label_id+=1;queue=deque([(row,col)]);visited[row,col]=True;points=[]
            while queue:
                yy,xx=queue.popleft();points.append((yy,xx))
                for dy,dx in [(-1,0),(0,-1),(0,1),(1,0)]:
                    y2,x2=yy+dy,xx+dx
                    if 0<=y2<white.shape[0] and 0<=x2<white.shape[1] and white[y2,x2] and not visited[y2,x2]:
                        visited[y2,x2]=True;queue.append((y2,x2))
            coords=np.array(sorted(points),np.int64);lo=coords.min(axis=0);hi=coords.max(axis=0);area=len(points)
            if 2<=area<=35 and np.all(hi-lo+1<=9):
                coords[:,0]+=y0;coords[:,1]+=x0
                components.append(dict(id=len(components),label=label_id,x0=int(lo[1])+x0,x1=int(hi[1])+x0,y0=int(lo[0])+y0,y1=int(hi[0])+y0,area=area,pixels_yx=coords.tolist()))
    meta['components']=components
    return pixels,meta,encoded


def prepare():
    for suffix in ['-plan.json','-results.json']:
        if out(suffix).exists():raise FileExistsError(str(out(suffix)))
    pixels,geometry,encoded=source();assert len(geometry['components'])==42
    plan=dict(schema=1,frozen_utc=now(),script=record(__file__),source_pdf=record(ROOT/PDF),
        selected_geometry_sha256=hashlib.sha256(canon(geometry)).hexdigest(),parser=geometry['parser'],
        series_component_ids=SERIES,bar_column_search_y_inclusive=BARS,unresolved_component_reasons=UNRESOLVED,
        component_roi=COMPONENT_ROI,component_rule='4-connected white pixels >=160; areas2..35px, width/height1..9px. Center=interior bbox midpoint; preserve pixel masks. Exclude legend ID1. First ID0 is shared, not three independent means.',
        error_rule='At each fixed column and search interval, retain all dark pixels<128; exactly two contiguous runs of at least3px must bracket the marker center. Use extreme run pixel centers as drawn upper/lower endpoints. No recentering, symmetrizing or zero substitution.',
        ticks=TICKS,tick_rule='Dark pixels<128 within fixed native-pixel ROIs; use midpoint of coordinates tied for maximum dark-pixel count along tick direction.',
        calibration='First/last labeled ticks define affine axes; holdout middle ticks and independently use lower/middle and middle/upper anchor pairs to quantify raster calibration differences. No least squares.',
        sensitivity=dict(marker_center_pixels=1.5,error_endpoint_pixels=1.5,anchor_pixels=1.,
            interpretation='Declared raster-placement sensitivity only, not a certified error enclosure, SEM or confidence interval. Evaluate all independent anchor/point-offset corners; never add to biological SEM.'),
        timing='Retain plotted x coordinates and ordinal; never snap to nominal periods or infer baseline-to-test pulse phase.',
        biological_context=dict(glomerulus='VM2',sex='female',age_days=[2,7],caption_n_cells=6,frequencies_hz=[15,20,50],
            baseline='7Hz for4s;500ms test; D/E examples20/50Hz;15Hz is explicitly in panelF legend',
            measure='somatic PN voltage-clamp uEPSC amplitude as percent initial',
            normalization_limit='Axis says percent initial; exact per-cell/per-trial normalization and pooling operation not recovered from this panel.',
            error_convention='General main-paper Data Analysis: mean +/- SEM across experiments; Fig8F caption n=6cells, no point-level covariance/individual measurements.'),
        initial_shared_policy='Store shared marker pixel geometry and its common plotted ordinate, but individual first-point means/SEM are null. Do not count reused initial marker as independent frequency observations.',
        source_access_notes=['Local PDF raster inspected natively. Initial decoding as raw uncompressed bytes failed (JPEG stream); standard JPEG decoding succeeded before any extraction plan/numeric reduction.',
            'Initial prepare stopped before plan creation because bundled Python lacked SciPy. Four-connected component traversal is implemented directly with a standard-library queue; no numerical reduction had run.',
            'One official higher-resolution check: https://pmc.ncbi.nlm.nih.gov/articles/PMC2429849/ returned a browser verification page; no alternate figure downloaded.'],
        allowed_outputs=['-geometry.json','-embedded.jpg','-native-panel.png','-calibration.csv','-points.csv','-results.json','-overlay.png','-plot-receipt.json'],
        no_model=True,no_fitting=True,no_other_panel_digitization=True)
    write(out('-plan.json'),plan);print(json.dumps(record(out('-plan.json'))))


def extract():
    import numpy as np
    from PIL import Image
    outputs=[out(s) for s in ['-geometry.json','-embedded.jpg','-native-panel.png','-calibration.csv','-points.csv','-results.json']]
    if any(p.exists() for p in outputs):raise FileExistsError('Preserve first extraction attempt')
    plan=load(out('-plan.json'));assert record(__file__)==plan['script'] and record(ROOT/PDF)==plan['source_pdf']
    checks=[];error=None;rows=[];cal=[];geometry=None
    def check(name,value,context=None):
        checks.append(dict(name=name,passed=bool(value),context=context))
        if not value:raise ValueError(name+': '+str(context))
    try:
        pixels,geometry,encoded=source();check('frozen_geometry_and_parser',hashlib.sha256(canon(geometry)).hexdigest()==plan['selected_geometry_sha256'] and geometry['parser']==plan['parser'])
        write(out('-geometry.json'),geometry)
        with out('-embedded.jpg').open('xb') as f:f.write(encoded)
        Image.fromarray(pixels[735:1090,0:380]).save(out('-native-panel.png'))
        axes={}
        for axis,definitions in TICKS.items():
            ticks=[]
            for value,bbox in definitions:
                x0,y0,x1,y1=bbox;dark=pixels[y0:y1,x0:x1]<128
                tally=dark.sum(axis=0 if axis=='x' else 1);coords=np.flatnonzero(tally==tally.max())+(x0 if axis=='x' else y0)
                check('axis_tick_narrow_peak',len(coords)<=3 and tally.max()>=4,(axis,value))
                coord=float((coords.min()+coords.max())/2);ticks.append([value,coord]);cal.append(dict(axis=axis,label=value,native_coordinate=coord,peak_pixel_coordinates=coords.tolist(),max_ink_count=int(tally.max())))
            low,high=ticks[0],ticks[-1];scale=(high[0]-low[0])/(high[1]-low[1]);axes[axis]=dict(ticks=ticks,scale=scale,anchor=low)
            for r,(value,coord) in zip(cal[-3:],ticks):
                r['converted_axis_value']=(coord-low[1])*scale+low[0];r['residual_axis_units']=r['converted_axis_value']-value
            check('middle_tick_pixel_residual',abs(ticks[1][1]-(low[1]+(ticks[1][0]-low[0])/scale))<=.75,axis)
        def convert(axis,coord):
            a=axes[axis];return (coord-a['anchor'][1])*a['scale']+a['anchor'][0]
        def sensitivity(axis,coord,pixel_sensitivity):
            ticks=axes[axis]['ticks'];values=[]
            for dl in [-1.,1.]:
                for dh in [-1.,1.]:
                    for dp in [-pixel_sensitivity,pixel_sensitivity]:
                        low=ticks[0][1]+dl;high=ticks[-1][1]+dh
                        values.append((coord+dp-low)/(high-low)*(ticks[-1][0]-ticks[0][0])+ticks[0][0])
            return min(values),max(values)
        def alternate(axis,coord):
            t=axes[axis]['ticks'];return [(coord-a[1])/(b[1]-a[1])*(b[0]-a[0])+a[0] for a,b in [(t[0],t[1]),(t[1],t[2])]]
        for freq,ids in SERIES.items():
            for ordinal,cid in enumerate(ids):
                c=geometry['components'][cid];x=(c['x0']+c['x1'])/2;y=(c['y0']+c['y1'])/2
                raw=dict(frequency_hz=freq,point_ordinal=ordinal,component_id=cid,marker_x_native_px=x,marker_y_native_px=y,
                    time_ms=convert('x',x),time_sensitivity_ms=list(sensitivity('x',x,1.5)),
                    plotted_marker_percent_initial=convert('y',y),marker_sensitivity_percent_initial=list(sensitivity('y',y,1.5)),
                    mean_percent_initial=None if cid==0 else convert('y',y),mean_status='shared_initial_geometry_unresolved_by_frequency' if cid==0 else 'raster_marker_estimate',
                    sem_percent_initial=None,error_low_percent_initial=None,error_high_percent_initial=None,
                    error_x_native_px=None,error_top_native_px=None,error_bottom_native_px=None,error_pixel_runs=None,
                    error_status=UNRESOLVED.get(cid,'resolved_drawn_stem'),error_midpoint_minus_marker_px=None,
                    lower_extent_from_marker=None,upper_extent_from_marker=None,
                    time_alternate_middle_anchor_ms=alternate('x',x),mean_alternate_middle_anchor_percent=alternate('y',y))
                if cid in BARS:
                    column,ylow,yhigh=BARS[cid];ink=np.flatnonzero(pixels[ylow:yhigh+1,column]<128)+ylow
                    runs=[g for g in np.split(ink,np.flatnonzero(np.diff(ink)>1)+1) if len(g)>=3]
                    check('two_separate_bar_stems',len(runs)==2 and runs[0][-1]<y<runs[1][0],(freq,ordinal,cid))
                    top=float(runs[0][0]);bottom=float(runs[1][-1]);check('marker_bar_alignment',abs(column-x)<=1.5 and abs((top+bottom)/2-y)<=1.5,(freq,ordinal))
                    low,high=convert('y',bottom),convert('y',top)
                    raw.update(sem_percent_initial=(high-low)/2,error_low_percent_initial=low,error_high_percent_initial=high,
                        error_x_native_px=column,error_top_native_px=top,error_bottom_native_px=bottom,
                        error_pixel_runs=[g.tolist() for g in runs],error_midpoint_minus_marker_px=(top+bottom)/2-y,
                        lower_extent_from_marker=convert('y',y)-low,upper_extent_from_marker=high-convert('y',y),
                        error_low_sensitivity_percent=list(sensitivity('y',bottom,1.5)),error_high_sensitivity_percent=list(sensitivity('y',top,1.5)))
                rows.append(raw)
            check('source_event_coordinates_increase',all(rows[-len(ids)+i]['time_ms']<rows[-len(ids)+i+1]['time_ms'] for i in range(len(ids)-1)),freq)
        check('series_event_and_shared_geometry_counts',len(rows)==43 and len({r['component_id'] for r in rows})==41 and len({r['component_id'] for r in rows if r['component_id']})==40)
        check('resolved_mean_and_SEM_counts',sum(r['mean_percent_initial'] is not None for r in rows)==40 and sum(r['sem_percent_initial'] is not None for r in rows)==37)
        check('no_missing_uncertainty_as_zero',all(r['sem_percent_initial'] is None if r['component_id'] in UNRESOLVED else r['sem_percent_initial']>0 for r in rows))
        for axis in ['x','y']:
            for r in rows:
                coord=r['marker_x_native_px' if axis=='x' else 'marker_y_native_px'];a=axes[axis]
                check('axis_inverse_reprojection',abs((convert(axis,coord)-a['anchor'][0])/a['scale']+a['anchor'][1]-coord)<1e-10,axis)
        columns=list(dict.fromkeys(k for r in rows for k in r))
        with out('-points.csv').open('x',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
            for r in rows:writer.writerow({k:json.dumps(v,separators=(',',':')) if isinstance(v,list) else v for k,v in r.items()})
        with out('-calibration.csv').open('x',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(cal[0]));writer.writeheader();writer.writerows(cal)
        with out('-points.csv').open(newline='') as f:csv_rows=list(csv.DictReader(f))
        check('csv_scalar_roundtrip',len(csv_rows)==43 and all(a[k]==('' if v is None else str(v)) if not isinstance(v,(float,list)) else (float(a[k])==v if isinstance(v,float) else json.loads(a[k])==v) for a,b in zip(csv_rows,rows) for k,v in b.items()))
        check('source_and_script_still_frozen',record(__file__)==plan['script'] and record(ROOT/PDF)==plan['source_pdf'])
    except Exception as exc:error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
    result=dict(schema=1,completed_utc=now(),passed=error is None and all(c['passed'] for c in checks),plan=record(out('-plan.json')),
        checks=checks,error=error,check_count=len(checks),axes=locals().get('axes'),rows=rows,
        artifacts=[record(p) for p in outputs[:-1] if p.exists()],
        scope='Fig8F only: raster-level event coordinates,40 individual mean estimates and37 separated SEM stem spans; three shared initial means and six SEMs unresolved.',
        limits=['SEM is inferred from paper-wide mean+/-SEM convention and panel n=6, not a source per-trial data release.',
            'Pixel sensitivity envelopes are declared placements, not confidence intervals or certified total errors; JPEG and glyph-center bias remain.',
            'No pulse-phase snapping, no initial normalization-operation assumption, no fits, no Fig9/S8 extraction, no biological model or network run.'])
    write(out('-results.json'),result);print(json.dumps(dict(passed=result['passed'],checks=len(checks),error=error,rows=len(rows),result=record(out('-results.json'))),indent=2))
    return 0 if result['passed'] else 1


def plot():
    import numpy as np
    from PIL import Image
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    if out('-overlay.png').exists() or out('-plot-receipt.json').exists():raise FileExistsError('Preserve first overlay attempt')
    result=load(out('-results.json'));assert result['passed']
    source_hash=sha(out('-results.json'));image=np.array(Image.open(out('-embedded.jpg')))
    colors={15:'#2767A3',20:'#D67C0F',50:'#19855C'};markers={15:'o',20:'s',50:'^'}
    fig,(a,b)=plt.subplots(1,2,figsize=(12,6.8));fig.subplots_adjust(left=.055,right=.98,bottom=.20,top=.84,wspace=.18)
    a.imshow(image,cmap='gray',vmin=0,vmax=255,interpolation='nearest');a.set_xlim(82,370);a.set_ylim(1035,790)
    for r in result['rows']:
        if r['component_id']==0:continue
        c=colors[r['frequency_hz']];a.plot(r['marker_x_native_px'],r['marker_y_native_px'],'+',color=c,ms=4,mew=.8)
        if r['sem_percent_initial'] is not None:
            a.plot([r['error_x_native_px']]*2,[r['error_top_native_px'],r['error_bottom_native_px']],linestyle='none',marker='_',color=c,ms=5,mew=.9)
    a.set_title('Native raster + marker centers / bar endpoints',fontsize=11);a.set_xlabel('Embedded-image x (native pixels)');a.set_ylabel('Embedded-image y (native pixels, downward)')
    for freq in [15,20,50]:
        rs=[r for r in result['rows'] if r['frequency_hz']==freq and r['mean_percent_initial'] is not None]
        b.plot([r['time_ms'] for r in rs],[r['mean_percent_initial'] for r in rs],color=colors[freq],marker=markers[freq],ms=4,lw=.8,label=f'{freq} Hz')
        for r in rs:
            if r['sem_percent_initial'] is not None:b.vlines(r['time_ms'],r['error_low_percent_initial'],r['error_high_percent_initial'],color=colors[freq],lw=.8)
            else:b.scatter(r['time_ms'],r['mean_percent_initial'],s=70,facecolors='none',edgecolors='#B53B2E',linewidths=1.1)
    b.axhline(0,color='.6',lw=.7);b.set_xlim(-8,505);b.set_ylim(-18,108);b.set_xlabel('Plotted event coordinate (ms; phase not assigned)');b.set_ylabel('uEPSC amplitude (% initial)');b.set_title('Individual means; visible stem extents only',fontsize=11);b.legend(frameon=False);b.grid(alpha=.2)
    fig.suptitle('Kazama & Wilson 2008, Fig. 8F: VM2 synaptic depression',fontsize=16)
    fig.text(.06,.085,'Native JPEG extraction; n=6 cells in panel caption. General methods specify mean ± SEM.\n'
        '40 individual means / 37 resolved bars; shared initial means omitted. Red rings: unresolved SEM, not zero.\n'
        'Raster sensitivity is separate from SEM. No fit, event-phase inference, or transfer to the neural runtime.',fontsize=10,linespacing=1.5)
    fig.savefig(out('-overlay.png'),dpi=180);plt.close(fig)
    assert sha(out('-results.json'))==source_hash
    write(out('-plot-receipt.json'),dict(created_utc=now(),source_results_sha256=source_hash,script_sha256=sha(__file__),output=record(out('-overlay.png')),plot_only=True))
    print(json.dumps(record(out('-overlay.png'))))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','extract','plot']);args=parser.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='extract':raise SystemExit(extract())
    else:plot()
