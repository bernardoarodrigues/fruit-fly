"""Independently check source XLSX XML and summarize fixed workbook identities."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'validation/apl-sk-workbook-join.json'
OUT=ROOT/'validation/apl-sk-workbook-review.json'
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def same(a,b):
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):
        return math.isclose(a,b,rel_tol=1e-13,abs_tol=1e-12)
    return a==b


def colnum(col):
    n=0
    for c in col:n=26*n+ord(c)-64
    return n


def colstr(n):
    text=''
    while n:n,r=divmod(n-1,26);text=chr(65+r)+text
    return text


def translate_shared(formula,origin,destination):
    a=re.fullmatch(r'([A-Z]+)([0-9]+)',origin);b=re.fullmatch(r'([A-Z]+)([0-9]+)',destination)
    dc=colnum(b[1])-colnum(a[1]);dr=int(b[2])-int(a[2])
    def shift(m):
        ac,c,ar,r=m.groups()
        return ac+(c if ac else colstr(colnum(c)+dc))+ar+str(int(r)+(0 if ar else dr))
    return re.sub(r'(?<![A-Za-z0-9_])(\$?)([A-Z]+)(\$?)([0-9]+)',shift,formula)


def main():
    if OUT.exists():raise FileExistsError('Preserve completed source review')
    data=json.loads(SOURCE.read_text());checks=0;formula_checks=[];groups=[]
    for book in data['books']:
        with zipfile.ZipFile(ROOT/book['path']) as z:
            strings=[]
            if 'xl/sharedStrings.xml' in z.namelist():
                strings=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',NS)]
            rels={x.attrib['Id']:x.attrib['Target'] for x in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
            for ss in ET.fromstring(z.read('xl/workbook.xml')).findall('m:sheets/m:sheet',NS):
                sheet=next(s for s in book['sheets'] if s['name']==ss.attrib['name'])
                target=rels[ss.attrib['{'+NS['r']+'}id']]
                part=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
                cells={c['coordinate']:c for c in sheet['cells']};xml_populated=set();shared={}
                for c in ET.fromstring(z.read(part)).findall('m:sheetData/m:row/m:c',NS):
                    v=c.find('m:v',NS);f=c.find('m:f',NS);inline=c.find('m:is',NS)
                    if v is None and f is None and inline is None:continue
                    raw=None if v is None else v.text;kind=c.attrib.get('t','n')
                    value=(strings[int(raw)] if kind=='s' else ''.join(inline.itertext()) if kind=='inlineStr'
                           else float(raw) if kind=='n' and raw is not None else bool(int(raw)) if kind=='b' else raw)
                    coord=c.attrib['r'];xml_populated.add(coord)
                    expected=cells[coord]
                    assert same(value,expected['cached_value']),(book['member'],sheet['name'],coord)
                    formula=None
                    if f is not None:
                        if f.attrib.get('t')=='shared':
                            if f.text is not None:shared[f.attrib['si']]=(f.text,coord)
                            master,origin=shared[f.attrib['si']]
                            formula=translate_shared(master,origin,coord)
                        else:formula=f.text
                    assert same('='+formula if f is not None else value,expected['value']),(coord,formula,expected['value'])
                    checks+=2
                assert xml_populated=={c['coordinate'] for c in sheet['cells'] if c['value'] is not None}
                checks+=1
        for sheet in book['sheets']:
            if sheet['name'] not in ('intrinsic','AHP(2nA)'):continue
            cs={c['coordinate']:c for c in sheet['cells']}
            records=[j for j in data['joins'] if j['workbook']==book['member'] and j['sheet']==sheet['name']]
            standard=book['member'].endswith('APL_NS_SD_RS_final.xlsx')
            def get(col,row):return cs.get(f'{col}{row}',{}).get('cached_value')
            counts=Counter(r['state'] if standard else r['genotype'] for r in records)
            fly_cells=defaultdict(list)
            for row in records:fly_cells[row['fly']].append(row['cell'])
            group=dict(workbook=book['member'],sheet=sheet['name'],row_count=len(records),condition_counts=dict(counts),
                unique_fly_count=len(fly_cells),shared_fly_ids={k:v for k,v in fly_cells.items() if len(v)>1},
                matched_rows=sum(bool(r['matched_abf_members']) for r in records))
            if sheet['name']=='intrinsic':
                for r in records:
                    row=r['row'];raw,adj,dv,rin=('D','E','F','G') if standard else ('E','F','G','H')
                    specs=[(adj,f'={raw}{row}-15.7',get(raw,row)-15.7,'mV'),
                           (rin,f'={dv}{row}/-0.05',get(dv,row)/-.05,'MOhm despite Gohm header')]
                    if standard and isinstance(get('O',row),(int,float)):
                        specs += [('P',f'=O{row}/-0.05',get('O',row)/-.05,'MOhm despite Gohm header'),
                                  ('V',f'=T{row}-K{row}',get('T',row)-get('K',row),'mV signed deflection difference')]
                    for col,formula,value,unit in specs:
                        c=cs[f'{col}{row}']
                        assert c['value']==formula and same(c['cached_value'],value)
                        formula_checks.append(dict(workbook=book['member'],sheet=sheet['name'],cell=c['coordinate'],formula=formula,
                                                   independently_calculated=value,cached_value=c['cached_value'],interpretation=unit))
            if standard:
                group['numeric_recovery_counts']=dict(Counter(r['state'] for r in records if isinstance(get('L',r['row']),(int,float))))
                group['unmeasured_recovery_rows']=[dict(row=r['row'],cell=r['cell'],state=r['state'],value=get('L',r['row'])) for r in records if not isinstance(get('L',r['row']),(int,float))]
                paired=[r for r in records if isinstance(get('T',r['row']),(int,float))]
                group['paired_drug_counts']=dict(Counter(r['state'] for r in paired))
                group['paired_drug_rows']=[dict(row=r['row'],cell=r['cell'],state=r['state'],members=r['matched_abf_members']) for r in paired]
            groups.append(group)
    nested=[b for b in data['books'] if '/raw/' in b['member']]
    a,b=nested[:2]
    def raw_b(book):return [c['cached_value'] for c in book['sheets'][0]['cells'] if c['coordinate'].startswith('B')]
    nested_equal=raw_b(a)==raw_b(b)
    result=dict(completed_utc=datetime.now(timezone.utc).isoformat(),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),xml_cell_checks=checks,
        independently_recomputed_formula_count=len(formula_checks),formula_checks=formula_checks,groups=groups,
        unmatched_workbook_rows=[r for r in data['joins'] if not r['matched_abf_members']],
        unmatched_abf_members=data['unmatched_abf_members'],
        identical_nested_amplitude_vectors=dict(workbooks=[a['member'],b['member']],equal=nested_equal,count=len(raw_b(a)),
          scope='Exact equality of stored raw-sheet column B. Different baseline-average formulas; no conclusion about which cell generated this vector.'),
        scope='Source transcription, arithmetic and identity review, not physiological fitting or a complete ABF-to-workbook numerical reproduction.')
    OUT.write_text(json.dumps(result,indent=2)+'\n')
    print('XML checks',checks,'independent formulas',len(formula_checks))
    for g in groups:print(g['sheet'],g['condition_counts'],'matched',g['matched_rows'],'flies',g['unique_fly_count'],'recovery',g.get('numeric_recovery_counts'),'drug',g.get('paired_drug_counts'))
    print('Duplicate nested vectors',nested_equal,len(raw_b(a)))


if __name__=='__main__':main()
