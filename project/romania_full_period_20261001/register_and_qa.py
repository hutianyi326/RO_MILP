from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,math,re
import pandas as pd
R=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent;O=R/'countries/RO/full_period_20261001'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return pd.read_csv(O/n)
def write(n,x):pd.DataFrame(x).to_csv(O/n,index=False,encoding='utf-8-sig')
rows=[];checks=[]
def check(n,x,d=''):checks.append({'check':n,'pass':bool(x),'detail':d})
reuse=json.loads((W/'reused_samples.json').read_text(encoding='utf-8'))
new=[json.loads(p.read_text(encoding='utf-8'))|{'receipt_file':p.relative_to(R).as_posix()} for p in (R/'data/raw/RO/full_period/20261001').glob('*/receipt.json')]
for m in new+reuse:
    x=m.copy();p=R/m['raw_file'] if m.get('raw_file') else None
    if p:
        b=p.read_bytes();check(m['id']+' raw checksum',sha(p)==m['sha256'])
        fmt='PDF' if b.startswith(b'%PDF') else 'OLE XLS' if b.startswith(bytes.fromhex('d0cf11e0')) else 'ZIP' if b.startswith(b'PK') else 'XML' if b.lstrip().startswith(b'<?xml') else 'JSON' if b.lstrip().startswith(b'{') else 'CSV' if b.startswith(b'"Mcp') else 'HTML'
        x['actual_signature_format']=fmt;x['original_receipt_format_preserved']=True
        x['parse_status']='REFERENCE_ONLY_NOT_TIMESERIES' if fmt=='HTML' else 'NATIVE_PARSED_WITH_RESTRICTIONS' if m.get('report') in ['dailyConsumptionOverview','activatedBalancingEnergyOverview','scheduledExchanges','tenderStatistics'] or m.get('dataset') in ['D02','D05','D06','D08','D11','D14'] or m['id'].startswith(('MONTH_','TSO_GENERATION_ARCHIVE','TSO_INSTALLED','SETTLEMENT_SAMPLE_')) else 'REFERENCE_DOCUMENT_WITH_LOCATORS'
        x['region']='Romania' if m.get('dataset')!='D14' else 'BNR reference currencies'
        x['record_count_kind']='unknown/reference'
        if fmt=='JSON':
            obj=json.loads(b.decode('utf-8-sig'));items=obj.get('itemList',[]);x['source_record_count']=len(items);x['record_count_kind']='native JSON items; tender items are not expanded product hours'
            if items and 'timeInterval' in items[0]:
                x['actual_time_from']=min(i['timeInterval']['from'] for i in items);x['actual_time_to']=max(i['timeInterval']['to'] for i in items)
        elif fmt=='CSV':
            import csv,io
            rr=[r for r in csv.reader(io.StringIO(b.decode('utf-8-sig'))) if r and r[0]=='Romania'];x['source_record_count']=len(rr);x['source_numeric_price_count']=sum(bool(re.fullmatch(r'-?\d+(?:\.\d+)?',r[2])) for r in rr);x['record_count_kind']='native Romania contract intervals'
        elif fmt=='XML':
            from xml.etree import ElementTree as ET
            root=ET.fromstring(b);cubes=[e for e in root.iter() if e.tag.split('}')[-1]=='Cube'];x['source_record_count']=len(cubes);x['record_count_kind']='annual published dates, including dates outside target';x['actual_time_from']=min(c.get('date') for c in cubes);x['actual_time_to']=max(c.get('date') for c in cubes)
    else:x['actual_signature_format']='NO_BODY';x['parse_status']='FAILED_ATTEMPT_RETAINED'
    x['access_date']=m['retrieved_utc'][:10];x['publication_time']=m.get('publication_time');x['revision_time']=m.get('revision_time');x['not_asof_or_model_approved']=True;rows.append(x)
(O/'raw_manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');write('source_parse_registry.csv',rows)
old=json.loads((R/'countries/RO/data_samples_20260930/raw_manifest.json').read_text(encoding='utf-8'))
for m in old:
    if m.get('raw_file'):check('old sample raw preserved '+m['id'],sha(R/m['raw_file'])==m['sha256'])
baseline=json.loads((R/'project/romania_data_samples_20260930/baseline_integrity.json').read_text(encoding='utf-8'))
for m in baseline['files']:check('fixed baseline preserved '+m['file'],sha(R/m['file'])==m['expected_sha256'])
protected=json.loads((R/'project/romania_data_samples_20260930/final_delivery_manifest.json').read_text(encoding='utf-8'))
for m in protected['files']:
    if m['file']=='project/country_status.yaml':continue
    check('old delivery preserved '+m['file'],sha(R/m['file'])==m['sha256'])
p=read('da_qh_descriptive_alignment.csv');a=read('activatedBalancingEnergyOverview.csv');l=read('dailyConsumptionOverview.csv');ex=read('scheduledExchanges.csv');c=read('capacity_statistics.csv');s=read('scada_native_hourly.csv');ctrl=read('monthly_official_reconciliation.csv');fx=read('bnr_reference_rates.csv')
check('20 monthly controls explicitly parsed',len(ctrl)==20 and ctrl.month.nunique()==20)
for field in ['volume_match_within_display_precision','weighted_price_match_2decimal','cash_within_public_precision_bound_A']:check('monthly '+field,ctrl[field].all())
check('BNR both annual namespaces parsed',set(fx.source_id)=={'BNR_FX_2025','BNR_FX_2026'} and len(fx)==413)
check('BNR dates unique and only published dates retained',not fx.date.duplicated().any() and fx.date.min()>='2025-01-01' and fx.date.max()<='2026-08-31')
check('SCADA native hour key unique',not s.duplicated(['member','sheet','row']).any())
check('SCADA missing calendar day retained',len(s)==14567 and s.source_local_date.nunique()==607)
check('SCADA autumn repeated hour retained',(s.source_hour_label=='03 bis').sum()==1)
check('SCADA identities numerical only, no independent validation',s.balance_identity_difference_mw.abs().max()<1e-8 and s.generation_sum_including_storage_difference_mw.abs().max()<1e-8)
check('SCADA negative source values retained',(s.wind_mw<0).any())
check('capacity product-month cross product 100 rows',len(read('capacity_monthly_statistics.csv'))==100)
check('capacity demands actual product IDs',set(c['product'])=={'FCR','aFRRUp','aFRRDown','mFRRUp','mFRRDown'})
windows=read('price_windows_2h_4h_daily.csv');check('2h/4h same 608 calendar days',windows.groupby('duration_hours').local_date.nunique().to_dict()=={2:608,4:608})
check('2h/4h explicit no income claim',windows.not_bess_revenue.all() and windows.chronology_not_enforced.all())
pc=read('capacity_provider_native_filtered.csv');check('provider keys unique',not pc.duplicated(['tender_code','product','delivery_start_utc','provider_source_label']).any())
cost=read('official_settlement_cost_samples.csv');check('cost samples four actual months/version examples',cost.groupby('source_id').size().to_dict()=={'SETTLEMENT_SAMPLE_1':2976,'SETTLEMENT_SAMPLE_2':2976,'SETTLEMENT_SAMPLE_3':2976,'SETTLEMENT_SAMPLE_4':2976})
check('cost identity within 0.02 LEI printed precision',cost.identity_diff_lei.abs().max()<=.020001)
check('no cost treated as imbalance price',cost.not_imbalance_price.all())
# Continuous UTC segments are descriptive intersections only, not approved model intervals.
base=pd.to_datetime(p.delivery_start_utc,utc=True);mask=pd.Series(True,index=base.index)
joint=p[['delivery_start_utc']].merge(a[['delivery_start_utc','aFRR_Up','aFRR_Down']],on='delivery_start_utc',validate='one_to_one')
segments=[];counts=[]
def runs(label,valid,reason):
    valid=pd.Series(valid,index=base.index);groups=(valid.ne(valid.shift())|base.diff().ne(pd.Timedelta(minutes=15))).cumsum();n=0;longest=0
    for _,g in pd.DataFrame({'t':base,'valid':valid})[valid].groupby(groups):
        start=g.t.iloc[0];end=g.t.iloc[-1]+pd.Timedelta(minutes=15);duration=len(g)/4;longest=max(longest,duration);n+=1;segments.append({'use':label,'start_utc':start.isoformat(),'end_exclusive_utc':end.isoformat(),'qh':len(g),'hours':duration,'cut_reason':reason,'not_model_or_asof_approved':True})
    counts.append({'use':label,'numeric_common_qh':int(valid.sum()),'segments':n,'longest_hours':longest,'restrictions':reason})
runs('DA + gross actual load + commercial schedules',mask,'full descriptive grid; same data publisher controls not independent')
runs('DA + aFRR both directions numeric',joint[['aFRR_Up','aFRR_Down']].notna().all(axis=1),'missing any aFRR value cuts; amounts not station activation')
for product,g in c.groupby('product'):
    starts=set(pd.to_datetime(g[g[['demand_mw','average_accepted_price_LEI_denominator_unknown']].notna().all(axis=1)].delivery_start_utc,utc=True))
    valid=[t.floor('h') in starts for t in base]
    runs('DA + '+product+' demand and raw accepted price',valid,'native hourly statistics aligned for description; cash denominator and DST holes unresolved')
write('continuous_descriptive_segments.csv',segments);write('joint_sample_counts.csv',counts)
metadata={'generated_utc':datetime.now(timezone.utc).isoformat(),'new_attempts':len(new),'new_success_bodies':sum(bool(m.get('raw_file')) for m in new),'reused_DA_bodies':len(reuse),'prior_sample_raw_files_checked':sum(bool(m.get('raw_file')) for m in old),'checks':len(checks),'failed':[x for x in checks if not x['pass']],'status':'PASS' if all(x['pass'] for x in checks) else 'FAIL','scope':'integrity, native preservation, field coverage, derived controls and boundaries; does not close U/DS, independent institution checks or stage/model gates','detail':checks}
(O/'supplement_verification.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in metadata.items() if k!='detail'},ensure_ascii=False))
