"""Independent raw/API/FX/input audit; never edits production inputs."""
import csv,json,hashlib,urllib.request,xml.etree.ElementTree as ET,zipfile
from pathlib import Path
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from decimal import Decimal as D
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
RAW=ROOT/'data/raw/RO/jan2_price_audit/20261004'
RAW.mkdir(parents=True,exist_ok=True)
DATA=ROOT/'data/processed/RO/prices_eur_v1_20261002'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stamp(t):return datetime.fromisoformat(t.replace('Z','+00:00'))
def loadcsv(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
sources=loadcsv(DATA/'source_registry.csv')
old=next(s for s in sources if s['source_id']=='marginalPricesOverview_2025-01')
oldpath=ROOT/old['raw_file'];assert sha(oldpath)==old['sha256']
records={stamp(r['timeInterval']['from']):r for r in read(oldpath)['itemList']}
base='https://newmarkets.transelectrica.ro/usy-durom-publicreportg01/00121002500000000000000000000100/publicReport/'
urls={'day':base+'marginalPricesOverview?timeInterval.from=2025-01-01T22%3A00%3A00Z&timeInterval.to=2025-01-02T22%3A00%3A00Z&pageInfo.pageSize=3000&pageInfo.pageIndex=0',
 'metadata':base+'metadata/get?reportCode=marginalPricesOverview',
 'bnr2024':'https://curs.bnr.ro/files/xml/years/nbrfxrates2024.xml',
 'bnr2025':'https://curs.bnr.ro/files/xml/years/nbrfxrates2025.xml'}
def fetch(pair):
 name,url=pair;p=RAW/(name+'.response');receipt={'url':url,'retrieved_utc':datetime.now(timezone.utc).isoformat()}
 if p.exists():receipt.update(status='REUSED_THIS_AUDIT',sha256=sha(p));return name,receipt
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=35) as resp:body=resp.read();receipt.update(status=resp.status,content_type=resp.headers.get('content-type'))
  with p.open('xb') as f:f.write(body)
  receipt.update(bytes=len(body),sha256=sha(p))
 except Exception as e:receipt.update(status='FAILED',error=str(e))
 return name,receipt
with ThreadPoolExecutor(max_workers=4) as pool:receipts=dict(pool.map(fetch,urls.items()))
(HERE/'download_receipts.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
grid=[r for r in loadcsv(DATA/'prices_eur_qh_20250101_20260831.csv') if r['local_date']=='2025-01-02']
assert len(grid)==96
live={}; live_path=RAW/'day.response'
if live_path.exists():
 obj=read(live_path);assert not obj.get('uuAppErrorMap');assert obj['pageInfo']['total']==len(obj['itemList'])==96
 live={stamp(r['timeInterval']['from']):r for r in obj['itemList']}
fxrecords=[]
for year in [2024,2025]:
 source=next(s for s in sources if s['source_id']==('BNR2024_BOUNDARY' if year==2024 else 'BNR_FX_2025'))
 path=ROOT/source['raw_file'];assert sha(path)==source['sha256']
 for cube in ET.parse(path).getroot().iter():
  if cube.tag.endswith('Cube'):
   for rate in cube:
    if rate.get('currency')=='EUR':fxrecords.append((cube.get('date'),rate.text,source['source_key']))
fixing,fx,fxkey=max(r for r in fxrecords if r[0]<'2025-01-02')
livefx=[]
for year in [2024,2025]:
 path=RAW/f'bnr{year}.response'
 if path.exists():
  for cube in ET.parse(path).getroot().iter():
   if cube.tag.endswith('Cube'):
    for rate in cube:
     if rate.get('currency')=='EUR':livefx.append((cube.get('date'),rate.text))
assert max(r for r in livefx if r[0]<'2025-01-02')==(fixing,fx)
assert not any('2025-01-01'<=r[0]<='2025-01-02' for r in livefx)
out=[];maxerror=D(0);mismatch=[]
for i,g in enumerate(grid):
 t=stamp(g['delivery_start_utc']);assert t==stamp(grid[0]['delivery_start_utc'])+timedelta(minutes=15*i)
 assert t.astimezone(ZoneInfo('Europe/Bucharest')).date().isoformat()=='2025-01-02'
 assert g['fx_fixing_date']==fixing and D(g['fx_ron_per_eur'])==D(fx)
 r=records[t];row={'local_time':g['local_time'],'utc':g['delivery_start_utc'],'raw_record_id':r['id'],'fx_date':fixing,'ron_per_eur':fx}
 for direction,key in [('up','aFRR_Up'),('down','aFRR_Down')]:
  raw=D(str(r[key]));expected=raw/D(fx);actual=D(g[f'afrr_{direction}_activation_price_eur_per_mwh_proxy']);err=abs(actual-expected);maxerror=max(maxerror,err)
  assert err<D('0.000000001')
  if live and live[t][key]!=r[key]:mismatch.append([str(t),key,r[key],live[t][key]])
  row.update({direction+'_raw_ron_per_mwh':str(raw),direction+'_expected_eur_per_mwh':str(expected),direction+'_input_eur_per_mwh':str(actual),direction+'_difference_eur_per_mwh':str(err)})
 out.append(row)
with (HERE/'jan2_activation_price_reconciliation.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
summary={'scope':'2025-01-02 Europe/Bucharest; 96 QH, two aFRR directions','fx_date':fixing,'ron_per_eur':fx,'fx_source_key':fxkey,'conversion_max_error_eur_per_mwh':str(maxerror),'live_api_rows':len(live),'live_source_mismatches':mismatch,'source_sha256':sha(oldpath),'raw_source':old,'statistics':{},'first_hour':out[:4]}
for d in ['up','down']:
 values=[D(r[d+'_input_eur_per_mwh']) for r in out]
 summary['statistics'][d]={'min':str(min(values)),'max':str(max(values)),'mean_including_published_zero':str(sum(values)/96),'negative_count':sum(v<0 for v in values),'zero_count':sum(v==0 for v in values),'max_rows':[r for r in out if D(r[d+'_input_eur_per_mwh'])==max(values)],'min_rows':[r for r in out if D(r[d+'_input_eur_per_mwh'])==min(values)]}
summary['status']='PASS_ARITHMETIC_AND_LIVE_SOURCE' if len(live)==96 and not mismatch else 'ARITHMETIC_PASS_LIVE_CHECK_INCOMPLETE_OR_DIFFERENT'
summary['live_bnr_fixing_verified']=True
# Independently verify the exported Excel and settlement ledger, without importing model code.
book=ROOT/'outputs/01a0f118-8c45-7e53-9dc7-5c2b28a5ed1c/20250101_audit/RO_100MW_200MWh_20250101_MILP审计.xlsx'
ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(book) as z:
 sheet=ET.fromstring(z.read('xl/worksheets/sheet5.xml'))
 cells={c.get('r'):c.find('m:v',ns).text for c in sheet.findall('.//m:c',ns) if c.find('m:v',ns) is not None}
 for i,row in enumerate(out):
  for col,direction in [('F','up'),('G','down')]:assert abs(D(cells[f'{col}{i+7}'])-D(row[direction+'_expected_eur_per_mwh']))<D('1e-9')
ledger=read(ROOT/'outputs/capacity_sensitivity_100mw_200mwh_20261002/v3/p100_run/windows/0001.json')['executed_qh']
cash={'up':D(0),'down':D(0)}
for row,g in zip(ledger,out):
 assert row['delivery_start_utc']==g['utc']
 for direction,sign in [('up',1),('down',-1)]:
  amount=D(str(row[f'afrr_{direction}_activation_mwh']))*D(g[direction+'_expected_eur_per_mwh'])*sign
  assert abs(amount-D(str(row[f'afrr_{direction}_activation_eur'])))<D('1e-8');cash[direction]+=amount
summary['excel_price_values_verified']=192
summary['ledger_activation_cash_values_verified']=192
summary['activation_cash_eur']={k:str(v) for k,v in cash.items()}
summary['unit_evidence']='DAMAS public marginalPricesOverview page observed 2026-10-04: aFRR Up [LEI], aFRR Down [LEI]. JSON does not itself supply denominator; EUR/MWh remains the registered energy-price proxy.'
summary['limitations']=['Official report values verified, not independent certification of underlying TSO calculations or final BSP invoices.','MWh denominator and applying system activation/price to a hypothetical plant retain existing modeling assumptions.']
(HERE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k not in ['statistics','raw_source','first_hour']},ensure_ascii=False,indent=2))
