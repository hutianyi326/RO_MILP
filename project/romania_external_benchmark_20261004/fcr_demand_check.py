"""Read-only checks of FCR demand, procurement proxy and project allocation."""
import csv, json, hashlib
from pathlib import Path
from collections import defaultdict
import openpyxl

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
cap=read(ROOT/'data/processed/RO/prices_eur_v1_20261002/capacity_native_hourly_eur.csv')
groups=defaultdict(list)
for r in cap:
    if r['product']=='FCR' and '2025-06-01'<=r['local_date']<='2026-08-31':groups[r['local_date'][:7]].append(r)
rows=[]
for month,rs in sorted(groups.items()):
    d=[float(r['demand_mw']) for r in rs if r['demand_mw']]
    a=[float(r['accepted_capacity_mw']) for r in rs if r['accepted_capacity_mw']]
    assert len({r['delivery_start_utc'] for r in rs})==len(rs)
    assert set(d)=={116. if month<'2026-01' else 128.}
    rows.append(dict(month=month,records=len(rs),valid_demand_records=len(d),demand_mw=d[0],
        valid_accepted_proxy_records=len(a),mean_accepted_proxy_mw=sum(a)/len(a),
        min_accepted_proxy_mw=min(a),max_accepted_proxy_mw=max(a),
        underfulfilled_records=sum(float(r['satisfied_ratio'])<1 for r in rs if r['satisfied_ratio']),
        note='Accepted MW is demand times published fulfillment ratio, not exact supplier-summed MW; missing records not zero'))
with (OUT/'fcr_demand_monthly.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

# Official supplier workbook: sum detail only, never duplicate Grand Total.
wb=openpyxl.load_workbook(OUT/'sources/fcr_purchased_20260831.xlsx',read_only=True,data_only=True)
by=defaultdict(list);hours=defaultdict(float)
for r in wb.active.iter_rows(min_row=9,values_only=True):
    if r[3]=='FCR' and r[4]!='Grand Total' and isinstance(r[8],(int,float)):
        assert r[7]==128
        by[r[4]].append(float(r[8]));hours[int(r[2])]+=float(r[8])
assert len(hours)==24 and all(len(v)==24 for v in by.values())
assert sum(hours.values())==2778
day=sorted([r for r in cap if r['product']=='FCR' and r['local_date']=='2026-08-31'],key=lambda x:x['delivery_start_utc'])
errors=[float(r['accepted_capacity_mw'])-hours[i+1] for i,r in enumerate(day)]
assert len(errors)==24 and max(abs(e) for e in errors)<.128+1e-8
aug=groups['2026-08']
assert len(aug)==744
q=read(ROOT/'outputs/capacity_sensitivity_100mw_200mwh_20261002/v3/p100_run/executed_qh.csv')
site=[float(r['fcr_mw']) for r in q if r['local_date'].startswith('2026-08')]
assert len(site)==2976
summary=dict(access_date='2026-10-04',suppliers_aug31={k:dict(mean_mw=sum(v)/24,min_mw=min(v),max_mw=max(v)) for k,v in by.items()},
    exact_aug31_procured_mean_mw=sum(hours.values())/24,
    aug31_max_abs_proxy_error_mw=max(abs(e) for e in errors),
    august_published_demand_mw=128,
    august_mean_procurement_proxy_mw=sum(float(r['accepted_capacity_mw']) for r in aug)/744,
    august_mean_positive_unfilled_proxy_mw=sum(max(0,128-float(r['accepted_capacity_mw'])) for r in aug)/744,
    august_site_mean_fcr_mw=sum(site)/len(site),
    august_site_to_demand=sum(site)/len(site)/128,
    august_site_to_procurement_proxy=sum(site)/4/sum(float(r['accepted_capacity_mw']) for r in aug),
    checks='PASS: monthly unique timestamps and constant demand; August 744/2976 hours/QH; supplier-day total 2778; API-derived quantity error <0.128 MW in sample; no solver rerun',
    note='Unfilled demand is not a BSP award probability; provider results are one-day sample only')
(OUT/'fcr_demand_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=True,indent=2))
