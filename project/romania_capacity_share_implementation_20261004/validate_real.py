"""Real input preflight, all-order limits, and small audited rolling checks."""
from pathlib import Path
from dataclasses import replace
import sys, json, csv
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from ro_milp.config import Config, midnight, nextday, hash_object
from ro_milp.inputs import load_eur
from ro_milp.core import order_specs
from ro_milp.rolling import run,code_hash

data=load_eur(ROOT/'data/processed/RO/prices_eur_v1_20261002')
cfg=Config(time_limit=30,mip_rel_gap=1e-4)
OUT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'outputs/capacity_share_implementation_20261004/final'
checked=0;reasons={};maxima={};day=midnight('2025-01-01')
while day<midnight('2026-09-02'):
    orders=order_specs(data,data.window(day,nextday(day)),cfg)
    for o in orders.values():
        if o['product']=='DA':continue
        checked+=1;reasons[o['reason']]=reasons.get(o['reason'],0)+1
        if o['reason']=='VALID':
            assert o['share_limit_mw'] is not None and o['upper']<=o['share_limit_mw']+1e-9
            key=o['capacity_share_month']+'|'+o['product'];maxima[key]=max(maxima.get(key,0),o['upper'])
    day=nextday(day)
result=dict(status='PASS',code_sha256=code_hash(),input_sha256=data.source_hash,share_schedule_sha256=hash_object(cfg.monthly_capacity_shares),all_orders_checked=checked,reasons=reasons,monthly_maximum_upper_mw=maxima,runs=[])
print('All-date input and capacity-bound checks PASS',checked,flush=True)
for name,start,end in [('month_boundary','2025-01-31','2025-02-02'),('autumn_dst','2025-10-25','2025-10-27'),('terminal_observation','2026-08-30','2026-09-01')]:
    out=OUT/name
    r=run(data,cfg,midnight(start),midnight(end),out)
    assert r['status']=='COMPLETE',(name,r)
    with (out/'executed_qh.csv').open(encoding='utf-8-sig',newline='') as f:
        for q in csv.DictReader(f):
            for prefix in ('fcr','afrr_up','afrr_down'):assert float(q[prefix+'_mw'])<=float(q[prefix+'_upper'])+1e-6
            assert start<=q['local_date']<end
    result['runs'].append(dict(name=name,start=start,end=end,**r));print(name,'PASS',r['executed_qh'],'quarters',flush=True)
(OUT/'real_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS: real-data checks; not a full-period recalculation',flush=True)
