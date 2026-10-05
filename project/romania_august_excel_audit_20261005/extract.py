import csv, json, hashlib, math
from pathlib import Path
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RUN = ROOT / 'outputs/monthly_share_100mw_200mwh_20261004/run'
DATA = ROOT / 'data/processed/RO/prices_eur_v1_20261002'
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical(x): return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
def dt(t): return datetime.fromisoformat(t.replace('Z', '+00:00'))
def serial(t): return (dt(t).astimezone(ZoneInfo('Europe/Bucharest')).replace(tzinfo=None)-datetime(1899,12,30)).total_seconds()/86400
def eq(a,b,tol=1e-6):
    assert math.isfinite(a) and math.isfinite(b) and abs(a-b)<=tol, (a,b)

manifest=read(RUN/'manifest.json')
cfg=manifest['identity']['config']
assert cfg['power_mw']==100 and cfg['hours']==2 and cfg['capacity_share_mode']=='monthly'
assert not any(k in cfg for k in ('p_up','p_down','p_fcr','daily_p'))
n=(date(2026,8,1)-date(2025,1,1)).days
txs={i:read(RUN/'windows'/f'{i:04d}.json') for i in range(n-1,n+3)}
for i,t in txs.items():
    assert sha(RUN/'windows'/f'{i:04d}.json')
    assert hashlib.sha256(canonical({k:v for k,v in t.items() if k!='sha256'}).encode()).hexdigest()==t['sha256']
    if i-1 in txs: assert t['previous_sha256']==txs[i-1]['sha256']
for name in ('prices_eur_qh_20250101_20260831.csv','capacity_native_hourly_eur.csv'):
    assert sha(DATA/name)==manifest['input_evidence']['consumed_csv_sha256'][name]
with (DATA/'prices_eur_qh_20250101_20260831.csv').open(encoding='utf-8-sig',newline='') as f:
    raw=[r for r in csv.DictReader(f) if r['local_date'] in ('2026-08-01','2026-08-02','2026-08-03')]
saved=sum([txs[i]['executed_qh'] for i in range(n,n+3)],[])
assert len(raw)==len(saved)==288
assert all(a['delivery_start_utc']==b['delivery_start_utc'] for a,b in zip(raw,saved))
raw_index={r['delivery_start_utc']:i for i,r in enumerate(raw)}
with (DATA/'capacity_native_hourly_eur.csv').open(encoding='utf-8-sig',newline='') as f:
    capacity=[r for r in csv.DictReader(f) if r['local_date'] in ('2026-08-01','2026-08-02','2026-08-03')]
cap_index={(r['delivery_start_utc'],r['product']):r for r in capacity}
windows=[]; plan=[]; phases=[]; order_rows=[]
cash_keys=['da_eur','fcr_capacity_eur','afrr_up_capacity_eur','afrr_down_capacity_eur','afrr_up_activation_eur','afrr_down_activation_eur','total_eur']
for wi,i in enumerate((n,n+1)):
    t=txs[i]; prev=txs[i-1]; orders={**prev['next_state']['frozen'],**t['initial_orders'],**t['new_orders']}
    ledger=t['executed_qh']+txs[i+1]['executed_qh']
    eq(prev['next_state']['soc_mwh'],ledger[0]['ein_mwh'])
    eq(ledger[95]['eout_mwh'],ledger[96]['ein_mwh'])
    eq(sum(r['total_eur'] for r in ledger),t['metrics']['plan_cash_eur'],1e-5)
    eq(t['metrics']['plan_cash_eur']+t['metrics']['salvage_eur'],t['metrics']['incumbent_eur'],1e-5)
    assert t['metrics']['status']==0 and t['metrics']['audit']=='PASS'
    for qi,row in enumerate(ledger):
        h=dt(row['delivery_start_utc']).replace(minute=0).isoformat().replace('+00:00','Z')
        keys=['DA|'+row['da_contract_id']]+[p+'|'+h for p in ('F','u','d')]
        for k,field in zip(keys,('da_mw','fcr_mw','afrr_up_mw','afrr_down_mw')): eq(orders[k]['amount_mw'],row[field])
        plan.append(dict(raw_index=raw_index[row['delivery_start_utc']],window=wi,qh=qi,role='当日执行' if qi<96 else '次日冻结计划复原',ledger=row))
        rawrow=raw[raw_index[row['delivery_start_utc']]]
        if row['afrr_hour_data_valid']:
            au=float(rawrow['afrr_up_system_activation_energy_mwh'])/(float(rawrow['afrr_up_accepted_capacity_mw'])*.25)
            ad=float(rawrow['afrr_down_system_activation_energy_mwh'])/(float(rawrow['afrr_down_accepted_capacity_mw'])*.25)
            assert au+ad<=1
        else: au=ad=0.
        for field,power,alpha in [('afrr_up_activation_mwh','afrr_up_mw',au),('afrr_down_activation_mwh','afrr_down_mw',ad)]: eq(row[field],row[power]*alpha*.25)
        eq(row['da_eur'],row['da_mw']*float(rawrow['da_price_eur_per_mwh'])*.25)
        for prod,prefix,field in [('FCR','fcr','fcr_mw'),('aFRRUp','afrr_up','afrr_up_mw'),('aFRRDown','afrr_down','afrr_down_mw')]:
            cr=cap_index[(h,prod)]
            share=row[prefix+'_capacity_share_coefficient']; demand=float(cr['demand_mw'])
            assert row[field]<=math.floor(share*demand+1e-9)
            pval=rawrow[prefix+'_capacity_price_eur_per_mw_h_proxy']
            expected=row[field]*float(pval)*.25 if row[field] else 0.
            eq(row[prefix+'_capacity_eur'],expected)
        eq(row['afrr_up_activation_eur'],row['afrr_up_activation_mwh']*float(rawrow['afrr_up_activation_price_eur_per_mwh_proxy']) if row['afrr_up_activation_mwh'] else 0.)
        eq(row['afrr_down_activation_eur'],-row['afrr_down_activation_mwh']*float(rawrow['afrr_down_activation_price_eur_per_mwh_proxy']) if row['afrr_down_activation_mwh'] else 0.)
    ph=t['executed_phases']+txs[i+1]['executed_phases']
    assert len(ph)==t['metrics']['phase_count']
    cursor=None; elapsed=0.; prev_soc=prev['next_state']['soc_mwh']
    for p in ph:
        if p['start']!=cursor: cursor=p['start']; elapsed=0.
        eq(p['ein'],prev_soc); eq(p['eout'],p['ein']+(.92*p['C']-p['D']/.92)*p['hours'])
        idx=raw_index[p['start']]; pi=wi*192+(idx-wi*96)
        phases.append(dict(p,window=wi,plan_index=pi,serial_start=serial(p['start'])+elapsed/24,serial_end=serial(p['start'])+(elapsed+p['hours'])/24))
        elapsed+=p['hours']; prev_soc=p['eout']
    for o in sorted(orders.values(),key=lambda x:(x['start'],x['product'])):
        if dt(t['start'])<=dt(o['start'])<dt(t['start'])+timedelta(days=2):
            order_rows.append(dict(o,window=wi,origin='前窗已冻结' if o['key'] in prev['next_state']['frozen'] else '本窗新增并冻结'))
    windows.append(dict(sequence=i,start=t['start'],serial=serial(t['start']),start_soc=ledger[0]['ein_mwh'],end_execution_soc=ledger[95]['eout_mwh'],end_plan_soc=ledger[-1]['eout_mwh'],metrics=t['metrics'],sha256=t['sha256'],prior_sha256=prev['sha256'],execution_cash={k:sum(r[k] for r in ledger[:96]) for k in cash_keys},plan_cash={k:sum(r[k] for r in ledger) for k in cash_keys}))
keys={r[k] for r in raw for k in r if k.endswith('source_key') and r[k]}
with (DATA/'source_registry.csv').open(encoding='utf-8-sig') as f: sources=[r for r in csv.DictReader(f) if r['source_key'] in keys]
payload=dict(raw=raw,saved=saved,serials=[serial(r['delivery_start_utc']) for r in raw],plan=plan,phases=phases,orders=order_rows,windows=windows,capacity=capacity,sources=sources,config=cfg,prior_end_soc=txs[n-1]['next_state']['soc_mwh'],provenance=dict(run_manifest_sha256=sha(RUN/'manifest.json'),input_file_sha256=sha(DATA/'prices_eur_qh_20250101_20260831.csv'),capacity_file_sha256=sha(DATA/'capacity_native_hourly_eur.csv'),code_sha256=manifest['identity']['code_sha256'],transactions={str(i):t['sha256'] for i,t in txs.items()}))
HERE.mkdir(parents=True,exist_ok=True)
(HERE/'payload.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(status='PASS',raw_rows=len(raw),plan_rows=len(plan),phase_rows=len(phases),orders=len(order_rows),prior_soc=payload['prior_end_soc'],days=[w['execution_cash'] for w in windows]),ensure_ascii=False))
