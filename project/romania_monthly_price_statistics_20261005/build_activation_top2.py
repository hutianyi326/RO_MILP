"""Revise only activation averages to daily highest-two-hour prices (both directions)."""
import csv,json,hashlib,math
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2]
INPUT=ROOT/'data/processed/RO/prices_eur_v1_20261002/prices_eur_qh_20250101_20260831.csv'
PRIOR=ROOT/'outputs/monthly_price_statistics_20261005/monthly_prices_eur.csv'
OUT=ROOT/'outputs/monthly_price_statistics_activation_top2_20261005';OUT.mkdir(exist_ok=True)
RO=ZoneInfo('Europe/Bucharest')
FIELDS={'up':'afrr_up_activation_price_eur_per_mwh_proxy','down':'afrr_down_activation_price_eur_per_mwh_proxy'}
def value(s):
 try:v=float(s);return v if math.isfinite(v) else None
 except (TypeError,ValueError):return None
def save(name,rows):
 with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
hours=defaultdict(list)
with INPUT.open(encoding='utf-8-sig',newline='') as f:
 for q in csv.DictReader(f):
  t=datetime.fromisoformat(q['delivery_start_utc'].replace('Z','+00:00'))
  assert q['price_currency']=='EUR' and t.astimezone(RO).date().isoformat()==q['local_date']
  hours[t.replace(minute=0,second=0,microsecond=0)].append(q)
byday=defaultdict(list)
for t,qs in sorted(hours.items()):
 assert len(qs)==4
 row={'hour_start_utc':t.isoformat(),'local_time':t.astimezone(RO).isoformat()}
 for direction,col in FIELDS.items():
  values=[value(q[col]) for q in qs]
  row[direction]=sum(values)/4 if all(v is not None for v in values) else None
 byday[t.astimezone(RO).date().isoformat()].append(row)
daily=[];coverage=[]
for day,hs in sorted(byday.items()):
 row={'local_date':day,'actual_hour_count':len(hs)}
 for direction in FIELDS:
  valid=[h for h in hs if h[direction] is not None];assert len(valid)>=2
  selected=sorted(valid,key=lambda h:(-h[direction],h['hour_start_utc']))[:2]
  row['afrr_'+direction+'_activation_highest_2h_eur_per_mwh']=sum(h[direction] for h in selected)/2
  row[direction+'_selected_hours_local']=';'.join(h['local_time'] for h in selected)
  row[direction+'_valid_hour_count']=len(valid)
 daily.append(row)
assert len(daily)==608
with PRIOR.open(encoding='utf-8-sig',newline='') as f:previous=list(csv.DictReader(f))
monthly=[]
for old in previous:
 month=old['month'];ds=[d for d in daily if d['local_date'].startswith(month)];r={k:v for k,v in old.items() if k not in ['afrr_up_activation_eur_per_mwh','afrr_down_activation_eur_per_mwh']}
 for direction in FIELDS:
  col='afrr_'+direction+'_activation_highest_2h_eur_per_mwh';r[col]=sum(d[col] for d in ds)/len(ds)
  expected=sum(d['actual_hour_count'] for d in ds);valid=sum(d[direction+'_valid_hour_count'] for d in ds)
  coverage.append({'month':month,'direction':direction,'calendar_days':len(ds),'valid_daily_pairs':len(ds),'expected_hours':expected,'complete_price_hours':valid,'excluded_incomplete_hours':expected-valid})
 monthly.append(r)
assert len(monthly)==20
save('monthly_prices_eur.csv',monthly);save('daily_activation_highest_2h.csv',daily);save('coverage.csv',coverage)
meta={'input_sha256':hashlib.sha256(INPUT.read_bytes()).hexdigest(),'prior_monthly_sha256':hashlib.sha256(PRIOR.read_bytes()).hexdigest(),'timezone':'Europe/Bucharest','activation_selection':'For UP and DOWN independently: mean of four QH prices per hour; select two highest hourly means each local day, non-contiguous allowed; average daily pairs equally within month','missing':'Exclude any hour with missing/nonfinite QH price; do not interpolate or fill zeros; each day must contain at least two complete hours','zero_negative_prices':'Retained as numeric published values; highest means descending numeric value, not absolute magnitude','DA_capacity_columns':'Unchanged from previous summary','price_unit':'Activation and DA EUR/MWh; capacity EUR/(MW h); existing DAMAS proxy semantics retained','model_modified':False,'outputs':['monthly_prices_eur.csv','daily_activation_highest_2h.csv','coverage.csv']}
(OUT/'methodology.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
for r in monthly:print('| '+' | '.join([r['month']]+[f'{float(v):.2f}' if v else '--' for k,v in r.items() if k!='month'])+' |')
print('INCOMPLETE',json.dumps([r for r in coverage if r['excluded_incomplete_hours']],ensure_ascii=False))
