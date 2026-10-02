"""Frozen research validation; not market completeness or model acceptance."""
from pathlib import Path
from datetime import datetime,timezone,date,timedelta
import csv,json,hashlib,re,zipfile
import pandas as pd
import numpy as np
R=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent;O=R/'countries/RO/gap_closure_20261001';RAW=R/'data/raw/RO/gap_closure/20261001'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
receipts=[json.loads(p.read_text(encoding='utf-8')) for p in RAW.glob('*/receipt.json')];ok={m['id']:m for m in receipts if m['status']=='HTTP_OK_UNPARSED'}
checks=[]
def check(name,passed,detail):checks.append(dict(check=name,result='PASS' if passed else 'FAIL',detail=detail))
bad=[]
for m in ok.values():
    p=R/m['raw_file']
    if not p.exists() or p.stat().st_size!=m['bytes'] or sha(p)!=m['sha256']:bad.append(m['id'])
check('successful raw files match receipt hashes and sizes',not bad,dict(successful_ids=len(ok),bad=bad))
for name,expected in [('requests_id_full_period.json',1216),('requests_idct60_full_period.json',608)]:
    req=json.loads((W/name).read_text(encoding='utf-8'));missing=[m['id'] for m in req if m['id'] not in ok]
    check(name+' target query coverage',len(req)==expected and not missing,dict(logical_requests=len(req),missing=missing))
prior=json.loads((W/'prior_delivery_integrity_at_start.json').read_text(encoding='utf-8'));changes=[]
for m in prior['files']:
    p=R/m['file']
    if not p.exists() or sha(p)!=m['sha256'] or p.stat().st_size!=m['bytes']:changes.append(m['file'])
check('prior delivery immutable before new acceptance',not changes,dict(files=len(prior['files']),changed=changes))
check('prior final manifest unchanged',sha(R/prior['prior_final_manifest'])==prior['manifest_sha256'],prior['prior_final_manifest'])
check('country state unchanged before acceptance',sha(R/'project/country_status.yaml')==prior['state_at_start_sha256'],prior['state_at_start_sha256'])
ids=json.loads((O/'intraday_analysis_summary.json').read_text(encoding='utf-8'));audit=pd.read_csv(O/'intraday_file_round_audit.csv')
check('intraday parser schema date/header/row errors',not ids['errors'],ids['errors'])
check('intraday date coverage each market product608',all(ids[x]==608 for x in ['ida_dates','idct15_dates','idct60_dates']),{x:ids[x] for x in ['ida_dates','idct15_dates','idct60_dates']})
check('all native queried form dates match request',bool(audit.form_date_matches_query.all()),len(audit))
check('three IDA round row structures match A calendar',bool(audit[audit.kind=='IDA'].native_count_matches_A.eq(True).all()),'A structural test only; does not prove numeric coverage')
ida=pd.read_csv(O/'ida_native_publication.csv',low_memory=False)
check('IDA numeric and missing-state counts independently regrouped',len(ida)==ids['ida_rows'] and int(ida.published_cell_state.eq('NUMERIC_PAIR').sum())==ids['ida_numeric_pairs'],dict(rows=len(ida),numeric_pairs=ids['ida_numeric_pairs'],states=ida.published_cell_state.value_counts().to_dict()))
source_counts={};stats={};sequence_ok=True;identities_null=True;total_trades=0
for chunk in pd.read_csv(O/'idct_native_publication_occurrences.csv',usecols=['source_id','query_date','native_occurrence','price_eur_per_mwh','volume_mwh','trade_time','trade_id'],chunksize=100000):
    total_trades+=len(chunk);identities_null &= chunk.trade_time.isna().all() and chunk.trade_id.isna().all()
    for sid,g in chunk.groupby('source_id',sort=False):
        previous=source_counts.get(sid,0)
        sequence_ok &= np.array_equal(g.native_occurrence.to_numpy(),np.arange(previous+1,previous+1+len(g)))
        source_counts[sid]=previous+len(g)
    chunk['selector']=chunk.source_id.str.startswith('IDCT60_').map({True:'PT60',False:'PT15'})
    chunk['month']=chunk.query_date.str[:7]
    for key,g in chunk.groupby(['selector','month'],sort=False):
        s=stats.setdefault(key,dict(native_occurrences=0,numeric_price=0,numeric_volume=0,price_min=float('inf'),price_max=float('-inf')))
        s['native_occurrences']+=len(g);s['numeric_price']+=int(g.price_eur_per_mwh.count());s['numeric_volume']+=int(g.volume_mwh.count())
        s['price_min']=min(s['price_min'],float(g.price_eur_per_mwh.min()));s['price_max']=max(s['price_max'],float(g.price_eur_per_mwh.max()))
check('IDCT source occurrence identity contiguous and unique',bool(sequence_ok) and total_trades==ids['idct_occurrences'],total_trades)
check('IDCT unavailable identities remain null',bool(identities_null),'no constructed trade identity')
id_audit=audit[audit.kind=='IDCT'];groups=pd.read_csv(O/'idct_native_group_audit.csv')
check('IDCT full raw cell consumption and caption date',bool(id_audit.full_native_cell_consumption.eq(True).all() and id_audit.conclusion_caption_matches_query.eq(True).all() and id_audit.native_data_cells.eq(id_audit.consumed_data_cells).all()),len(id_audit))
check('IDCT product group declared rowspan equals raw triplets and extracted occurrences',bool(groups.declared_rowspan.eq(groups.raw_triplet_count).all() and groups.declared_rowspan.eq(groups.extracted_occurrences).all() and int(groups.declared_rowspan.sum())==total_trades),dict(groups=len(groups),occurrences=total_trades))
check('IDCT per-source CSV counts equal all raw group declarations',all(source_counts.get(x.source_id,0)==int(x.sum_declared_rowspans)==int(x.native_rows) for x in id_audit.itertuples()),len(id_audit))
verification=json.loads((W/'idct_source_stream_verification.json').read_text(encoding='utf-8'))
check('IDCT every raw occurrence independently reconciled against CSV tokens and locators',verification['passed'] and verification['verified_files']==1216 and verification['verified_occurrences']==total_trades and verification['csv_sha256']==sha(O/'idct_native_publication_occurrences.csv') and verification['audit_sha256']==sha(O/'intraday_file_round_audit.csv'),{k:verification[k] for k in ['method','verified_files','verified_occurrences','occurrences_by_selector','product_groups','no_published_occurrence_source_ids']})
check('IDCT counts agree with first-review independent raw totals',ids['idct15_occurrences']==2180829 and ids['idct60_occurrences']==1560495 and total_trades==3741324,'PT15 2180829; PT60 1560495; native webpage occurrences only')
fx=pd.read_csv(O/'da_ron_eur_sample_checks.csv');check('339 official RON/EUR sample contracts within A display bound with matching MW',len(fx)==339 and fx.within_display_bound_A.all() and fx.volume_mw_matches.all(),len(fx))
sst=json.loads((O/'settlement_analysis_summary.json').read_text(encoding='utf-8'));pdfium=json.loads((W/'settlement_rectangle_omissions_pdfium_check.json').read_text(encoding='utf-8'))
check('settlement extractor disagreements resolved with preserved native source',sst['extractor_disagreement_cells_unresolved']==0 and sst['rectangle_omissions_independently_pdfium_verified']==262 and len(pdfium)==262 and all(x['exact_match'] for x in pdfium),dict(versions=sst['downloaded_parsed_catalog_versions'],grid_checks=sst['rect_grid_cross_checks']))
cap=pd.read_csv(O/'capacity_month_product_coverage_supplement.csv');check('100 prospective capacity product-months including5 empty early FCR months',len(cap)==100 and int(cap.capacity_rows.sum())==69327 and int(cap.provider_sum_matches.sum())==57202 and int(cap.provider_sum_unmatched.sum())==12125,dict(product_months=len(cap),native_rows=int(cap.capacity_rows.sum())))
for name in ['engineering_assumption_register.md','closure_ledger.md','data_dictionary.md','supplement_report.md','source_directory.md','acquisition_endpoints_supplement.md','evidence_register.csv','fee_timeline.csv','storage_cutoff_ledger.csv','source_anomalies.csv','historical_event_and_asof_register.csv']:
    check('required delivery exists '+name,(O/name).exists(),name)
summary=dict(checked_utc=datetime.now(timezone.utc).isoformat(),checks=checks,passed=sum(x['result']=='PASS' for x in checks),failed=sum(x['result']=='FAIL' for x in checks),intraday=ids,raw_successful_ids=len(ok),raw_attempt_receipts=len(receipts),prior_files=len(prior['files']),whole_third_step_exit=False,model_approved=False,asof_approved=False,distinction='PASS means this check executed successfully; real source anomalies and missing semantic/history proofs remain in closure ledger')
(O/'validation_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=int),encoding='utf-8')
monthly=audit.groupby(['kind','product_minutes',audit.query_date.str[:7]],dropna=False).agg(files=('source_id','nunique'),round_records=('source_id','size'),native_rows=('native_rows','sum'),numeric_pairs=('numeric_price_volume_pairs','sum'),blank_rows=('blank_rows','sum'),dash_rows=('dash_rows','sum')).reset_index().rename(columns={'query_date':'month'})
monthly.to_csv(O/'intraday_monthly_publication_coverage.csv',index=False,encoding='utf-8-sig')
numeric=ida[ida.published_cell_state=='NUMERIC_PAIR'];numeric.to_csv(O/'ida_numeric_pairs_only.csv',index=False,encoding='utf-8-sig')
pd.DataFrame([dict(selector=k[0],month=k[1],**v) for k,v in sorted(stats.items())]).to_csv(O/'idct_native_occurrence_statistics.csv',index=False,encoding='utf-8-sig')
print(json.dumps({k:summary[k] for k in ['passed','failed','raw_successful_ids','raw_attempt_receipts','prior_files','whole_third_step_exit']},default=int))
if summary['failed']:raise SystemExit('validation failed; do not freeze for review')
