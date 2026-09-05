"""Extract retained author notebook tables as strings; execute no HTML or Python."""
from pathlib import Path
from html.parser import HTMLParser
import datetime,hashlib,json
BASE=Path(__file__).resolve().parents[1]
P=BASE/'data/raw/eon-public-code/drosophila_brain_model_lif/source/results/eon_1/demo_notebook.ipynb'
class Table(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.inside=False;self.section=None;self.rows=[];self.row=None;self.cell=None
 def handle_starttag(self,tag,attrs):
  if tag=='table':self.inside=True
  if not self.inside:return
  if tag in ('thead','tbody'):self.section=tag
  if tag=='tr':self.row=[]
  if tag in ('td','th'):self.cell={'tag':tag,'text':''}
 def handle_data(self,s):
  if self.inside and self.cell is not None:self.cell['text']+=s
 def handle_endtag(self,tag):
  if not self.inside:return
  if tag in ('th','td') and self.cell is not None:self.row.append(self.cell);self.cell=None
  if tag=='tr' and self.row is not None:self.rows.append({'section':self.section,'cells':self.row});self.row=None
  if tag=='table':self.inside=False
j=json.loads(P.read_text());tables=[]
for ci in [11,18,38]:
 c=j['cells'][ci]
 for oi,o in enumerate(c.get('outputs',[])):
  if 'text/html' not in o.get('data',{}):continue
  html=''.join(o['data']['text/html']);start=html.index('<table');end=html.index('</table>',start)+len('</table>');table_html=html[start:end]
  parser=Table();parser.feed(table_html)
  header=next(r['cells'] for r in parser.rows if r['section']=='thead');columns=[x['text'] for x in header]
  data=[]
  for r in parser.rows:
   if r['section']!='tbody':continue
   vals=[x['text']for x in r['cells']];assert len(vals)==len(columns)
   data.append({'flyid':vals[0],'name':vals[1],'rates_Hz_as_printed':dict(zip(columns[2:],vals[2:]))})
  tables.append({'cell_index_zero_based':ci,'output_index':oi,'execution_count':c.get('execution_count'),'source_cell':''.join(c['source']),'output_type':o['output_type'],'html_output_sha256':hashlib.sha256(html.encode()).hexdigest(),'table_html_sha256':hashlib.sha256(table_html.encode()).hexdigest(),'table_html':table_html,'raw_rows':parser.rows,'data_rows':data})
assert len(tables)==3
assert [len(t['data_rows'])for t in tables]==[4,6,6]
# Cross-table consistency checks concern retained text only, not generating simulations.
base={r['flyid']:r['rates_Hz_as_printed']['P9s_100Hz']for r in tables[0]['data_rows']}
for t in tables[1:]:
 for r in t['data_rows']:
  if r['flyid']in base:assert r['rates_Hz_as_printed']['P9s_100Hz']==base[r['flyid']]
assert any(v=='NaN'for t in tables for r in t['data_rows']for v in r['rates_Hz_as_printed'].values())
r={'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Upstream stored output transcription only. Neither the notebook nor HTML nor upstream model was executed. No claim of biological validation, local reproduction, backend parity or verified generating execution order.','repo':'eonsystemspbc/drosophila_brain_model_lif','commit':'c976c7a90b2ac5a472c028b5862974217e93573f','notebook_path':str(P.relative_to(BASE)),'notebook_sha256':hashlib.sha256(P.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'representation':'Every table cell remains a text string, including six-digit rounding, FlyWire IDs and literal NaN. No NaN-to-zero conversion. Header/index rows and table HTML retained exactly; HTML scripts outside table are not copied or executed.','checks':{'three_requested_tables':True,'row_counts':[4,6,6],'baseline_text_agrees_across_tables':True,'literal_NaN_preserved':True},'tables':tables}
out=BASE/'validation/eon-public-code-author-output-tables.json'
if out.exists():raise FileExistsError(out)
out.write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r['checks']))
