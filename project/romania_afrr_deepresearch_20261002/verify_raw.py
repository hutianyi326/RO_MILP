"""Independent full-history source check using raw JSON and Decimal arithmetic."""
from pathlib import Path
from datetime import datetime
from decimal import Decimal as D
import csv,json,hashlib
ROOT=Path(__file__).resolve().parents[2];WORK=Path(__file__).resolve().parent
manifest=json.loads((ROOT/'countries/RO/full_period_20261001/raw_manifest.json').read_text())
def t(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
energy={};cap={};sources=[];errors=[]
for m in manifest:
    if m.get('report') not in ['tenderStatistics','activatedBalancingEnergyOverview'] or m['status']!='HTTP_OK_UNPARSED':continue
    raw=(ROOT/m['raw_file']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=m['sha256']:errors.append('hash '+m['id'])
    obj=json.loads(raw,parse_float=D);sources.append({'id':m['id'],'raw_file':m['raw_file'],'sha256':m['sha256']})
    if m['report']=='activatedBalancingEnergyOverview':
        for r in obj['itemList']:
            key=t(r['timeInterval']['from']);values=(r.get('aFRR_Up'),r.get('aFRR_Down'))
            if key in energy:errors.append('duplicate raw energy '+str(key))
            energy[key]=values
    else:
        for tender in obj['itemList']:
            ta=t(tender['timeInterval']['from']);tb=t(tender['timeInterval']['to'])
            if not(t(m['requested_start_utc'])<=ta<t(m['requested_end_utc'])):continue
            for service in tender.get('tenderServiceList',[]):
                p=service['serviceCode']
                if p not in ['aFRRUp','aFRRDown']:continue
                for r in service['tenderStatistics']['timeIntervalList']:
                    ra=t(r['timeInterval']['from']);rb=t(r['timeInterval']['to'])
                    if not ta<=ra<rb<=tb:continue
                    k=(ra,p);v=D(r['tenderDemand'])*D(r['tenderSatisfiedDemand'])
                    if k in cap:errors.append('duplicate raw capacity '+str(k))
                    cap[k]=v
rows=list(csv.DictReader((WORK/'activation_diagnostic_all.csv').open(encoding='utf-8-sig',newline='')))
counts={'total_qh':0,'uncomputable_qh':0,'exceed_qh':0,'up_over_one':0,'down_over_one':0,'combined_only':0}
for r in rows:
    q=t(r['delivery_start_utc']);h=q.replace(minute=0,second=0,microsecond=0);up,dn=energy[q]
    au=cap.get((h,'aFRRUp'));ad=cap.get((h,'aFRRDown'));counts['total_qh']+=1
    for name,x in [('energy_up_mwh',up),('energy_down_mwh',dn),('up_capacity_mw',au),('down_capacity_mw',ad)]:
        v=None if r[name]=='' else D(r[name])
        if (v is None)!=(x is None) or (v is not None and abs(v-D(x))>D('0.00000001')):errors.append('field '+str(q)+' '+name)
    if None in (up,dn,au,ad) or au<=0 or ad<=0:counts['uncomputable_qh']+=1;continue
    u=D(up)/(au/D(4));d=D(dn)/(ad/D(4));over=u+d>D('1.000000001')
    if over:counts['exceed_qh']+=1;counts['up_over_one']+=int(u>D('1.000000001'));counts['down_over_one']+=int(d>D('1.000000001'));counts['combined_only']+=int(u<=D('1.000000001') and d<=D('1.000000001'))
    if over!=(r['exceeds_one']=='True'):errors.append('classification '+str(q))
out={'method':'Raw JSON from 40 historical files, independent Decimal arithmetic, field-by-field comparison; no input changes','sources':sources,'counts':counts,'errors':errors,'pass':not errors}
(WORK/'independent_raw_verification.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'counts':counts,'raw_files':len(sources),'errors':errors[:10],'pass':not errors}))
