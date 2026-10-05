"""Monthly EUR input-price statistics by Bucharest delivery date, not dispatch-weighted."""
import csv,json,hashlib,math,calendar
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2]
INPUT=ROOT/'data/processed/RO/prices_eur_v1_20261002/prices_eur_qh_20250101_20260831.csv'
OUT=ROOT/'outputs/monthly_price_statistics_20261005'
OUT.mkdir(exist_ok=True)
RO=ZoneInfo('Europe/Bucharest')
FIELDS={
'fcr_capacity_eur_per_mw_h':'fcr_capacity_price_eur_per_mw_h_proxy',
'afrr_up_capacity_eur_per_mw_h':'afrr_up_capacity_price_eur_per_mw_h_proxy',
'afrr_down_capacity_eur_per_mw_h':'afrr_down_capacity_price_eur_per_mw_h_proxy',
'afrr_up_activation_eur_per_mwh':'afrr_up_activation_price_eur_per_mwh_proxy',
'afrr_down_activation_eur_per_mwh':'afrr_down_activation_price_eur_per_mwh_proxy'}
def finite(s):
 try:v=float(s);return v if math.isfinite(v) else None
 except (ValueError,TypeError):return None
def save(name,rows):
 with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
months=defaultdict(list);hours=defaultdict(list);allrows=[]
with INPUT.open(encoding='utf-8-sig',newline='') as f:
 for q in csv.DictReader(f):
  t=datetime.fromisoformat(q['delivery_start_utc'].replace('Z','+00:00'));local=t.astimezone(RO)
  assert local.date().isoformat()==q['local_date'] and q['price_currency']=='EUR' and q['period_role']=='FORMAL'
  assert float(q['duration_hours'])==.25
  months[q['local_date'][:7]].append(q);hours[t.replace(minute=0,second=0,microsecond=0)].append(q);allrows.append(q)
assert len(allrows)==58364
byday=defaultdict(list)
for t,qs in hours.items():
 assert len(qs)==4
 values=[finite(q['da_price_eur_per_mwh']) for q in qs];assert all(v is not None for v in values)
 byday[t.astimezone(RO).date().isoformat()].append(sum(values)/4)
daily=[]
for day,values in sorted(byday.items()):
 assert len(values) in (23,24,25)
 v=sorted(values);daily.append(dict(local_date=day,hour_count=len(v),da_highest_2h_eur_per_mwh=sum(v[-2:])/2,da_lowest_2h_eur_per_mwh=sum(v[:2])/2))
assert len(daily)==608
result=[];coverage=[]
for month,qs in sorted(months.items()):
 ds=[d for d in daily if d['local_date'].startswith(month)];assert len(ds)==calendar.monthrange(int(month[:4]),int(month[5:]))[1]
 row={'month':month,'da_highest_2h_eur_per_mwh':sum(d['da_highest_2h_eur_per_mwh'] for d in ds)/len(ds),'da_lowest_2h_eur_per_mwh':sum(d['da_lowest_2h_eur_per_mwh'] for d in ds)/len(ds)}
 coverage.append(dict(month=month,series='DA_daily_high_low',expected_observations=len(ds),valid_observations=len(ds),missing_observations=0,zero_observations=None,negative_observations=None,coverage_pct=100.))
 for key,col in FIELDS.items():
  vals=[finite(q[col]) for q in qs];valid=[v for v in vals if v is not None]
  row[key]=sum(valid)/len(valid) if valid else None
  coverage.append(dict(month=month,series=key,expected_observations=len(qs),valid_observations=len(valid),missing_observations=len(qs)-len(valid),zero_observations=sum(v==0 for v in valid),negative_observations=sum(v<0 for v in valid),coverage_pct=100*len(valid)/len(qs)))
 result.append(row)
assert len(result)==20
save('monthly_prices_eur.csv',result);save('daily_da_highest_lowest_2h.csv',daily);save('coverage.csv',coverage)
meta={'status':'PASS','input':str(INPUT.relative_to(ROOT)),'input_sha256':hashlib.sha256(INPUT.read_bytes()).hexdigest(),'months':20,'days':608,'qh':58364,'timezone':'Europe/Bucharest','daily_da_selection':'two highest/lowest actual hours; not necessarily contiguous; QH DA time-averaged to UTC-identified delivery hours; monthly arithmetic average of daily pairs','other_price_average':'equal QH time weights; omit missing; retain published zero and negative values; no dispatch, activation-volume or supplier-capacity weighting; do not filter with MILP activation-validity mask','capacity_price':'EUR/(MW h); DAMAS average accepted price proxy','activation_price':'EUR/MWh; DAMAS marginal-price proxy; not average activated-energy settlement price','native_capacity_hour_repetition':'four identical QH prices per full hour; repetition does not multiply monthly price','outputs':['monthly_prices_eur.csv','daily_da_highest_lowest_2h.csv','coverage.csv']}
(OUT/'methodology.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
print('PARTIAL COVERAGE',json.dumps([x for x in coverage if x['coverage_pct']<100],ensure_ascii=False))
