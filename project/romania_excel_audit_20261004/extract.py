import csv,json,hashlib
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
RUN=ROOT/'outputs/capacity_sensitivity_100mw_200mwh_20261002/v3/p100_run'
DATA=ROOT/'data/processed/RO/prices_eur_v1_20261002'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def dt(t):return datetime.fromisoformat(t.replace('Z','+00:00'))
def serial(t):return (dt(t).astimezone(ZoneInfo('Europe/Bucharest')).replace(tzinfo=None)-datetime(1899,12,30)).total_seconds()/86400
m=read(RUN/'manifest.json');tx=read(RUN/'windows/0000.json');nxt=read(RUN/'windows/0001.json')
assert m['identity']['config']['p_up']==m['identity']['config']['p_down']==m['identity']['config']['p_fcr']==1
for t in (tx,nxt):assert hashlib.sha256(canonical({k:v for k,v in t.items() if k!='sha256'}).encode()).hexdigest()==t['sha256']
assert tx['previous_sha256']==hashlib.sha256(canonical(m).encode()).hexdigest() and nxt['previous_sha256']==tx['sha256']
path=DATA/'prices_eur_qh_20250101_20260831.csv'
assert sha(path)==next(r['sha256'] for r in read(DATA/'manifest.json')['files'] if Path(r['path']).name==path.name)
with path.open(encoding='utf-8-sig',newline='') as f:raw=[r for r in csv.DictReader(f) if r['local_date'] in ('2025-01-01','2025-01-02')]
saved=tx['executed_qh']+nxt['executed_qh'];assert len(raw)==len(saved)==192
orders={**tx['initial_orders'],**tx['new_orders']}
for row in saved:
    keys=['DA|'+row['da_contract_id']]+[p+'|'+dt(row['delivery_start_utc']).replace(minute=0).isoformat().replace('+00:00','Z') for p in ('F','u','d')]
    for k,f in zip(keys,('da_mw','fcr_mw','afrr_up_mw','afrr_down_mw')):assert orders[k]['amount_mw']==row[f]
for r in saved[:96]:assert r['total_eur']==r['da_mw']==r['afrr_up_mw']==r['afrr_down_mw']==r['fcr_mw']==0 and r['ein_mwh']==r['eout_mwh']==10
assert all(a['delivery_start_utc']==b['delivery_start_utc'] for a,b in zip(raw,saved))
ph=tx['executed_phases']+nxt['executed_phases'];phases=[];cursor=None;elapsed=0
for p in ph:
    if p['start']!=cursor:cursor=p['start'];elapsed=0
    phases.append(dict(p,serial_start=serial(p['start'])+elapsed/24,serial_end=serial(p['start'])+(elapsed+p['hours'])/24,qh_index=next(i for i,r in enumerate(raw) if r['delivery_start_utc']==p['start'])))
    elapsed+=p['hours']
keys={r[k] for r in raw for k in r if k.endswith('source_key') and r[k]}
with (DATA/'source_registry.csv').open(encoding='utf-8-sig') as f:sources=[r for r in csv.DictReader(f) if r['source_key'] in keys]
payload=dict(raw=raw,saved=saved,phases=phases,orders=list(orders.values()),serials=[serial(r['delivery_start_utc']) for r in raw],metrics=tx['metrics'],initial=m['initial_state'],config=m['identity']['config'],sources=sources,provenance={'run_manifest_sha256':sha(RUN/'manifest.json'),'input_file_sha256':sha(path),'transaction_0000_payload_sha256':tx['sha256'],'transaction_0001_payload_sha256':nxt['sha256'],'code_sha256':m['identity']['code_sha256']})
(HERE/'payload.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'rows':len(raw),'phases':len(phases),'day1_cash':sum(r['total_eur'] for r in saved[:96]),'day2_plan_cash':sum(r['total_eur'] for r in saved[96:]),'day2_end_soc':saved[-1]['eout_mwh'],'sources':len(sources)}))
