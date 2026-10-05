"""Compare immutable prior run with FCR-only revision; preserve market decomposition."""
from pathlib import Path
import csv,json
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/fcr_competition_100mw_200mwh_20261005'
FIELDS=['da_eur','fcr_capacity_eur','afrr_up_capacity_eur','afrr_down_capacity_eur','afrr_up_activation_eur','afrr_down_activation_eur']
def agg(run):
 out=defaultdict(lambda:defaultdict(float))
 with (run/'executed_qh.csv').open(encoding='utf-8-sig',newline='') as f:
  for q in csv.DictReader(f):
   periods=[q['local_date'][:4],'TOTAL']
   if '2025-09-01'<=q['local_date']<'2026-09-01':periods+=['LATEST_12M']
   for p in periods:
    for k in FIELDS:out[p][k]+=float(q[k])
 for p in out:out[p]['total_eur']=sum(out[p].values())
 return out
old=agg(ROOT/'outputs/monthly_share_100mw_200mwh_20261004/run');new=agg(OUT/'run_v2')
rows=[]
for p in new:
 for k in [*FIELDS,'total_eur']:
  a=old[p][k];b=new[p][k];rows.append(dict(period=p,market=k,old_eur=a,new_eur=b,change_eur=b-a,change_pct=(b/a-1)*100 if a else None))
with (OUT/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(OUT/'comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([x for x in rows if x['market']=='total_eur' or x['period']=='TOTAL'],indent=2))
