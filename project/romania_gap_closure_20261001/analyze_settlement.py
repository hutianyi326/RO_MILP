from pathlib import Path
from datetime import datetime,date,timedelta
import json,re,csv
from pypdf import PdfReader
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent;O=ROOT/'countries/RO/gap_closure_20261001'
m=json.loads((W/'settlement_parsing_manifest.json').read_text(encoding='utf8'))
for x in m['files']:
    text=PdfReader(ROOT/x['raw_file']).pages[0].extract_text()
    d=re.search(r'Data:\s*(\d{2}\.\d{2}\.\d{4})',text)
    x['body_document_date']=datetime.strptime(d.group(1),'%d.%m.%Y').date().isoformat() if d else None
    x['document_date_matches_catalog_parse']=x['body_document_date']==x['completion_date_iso_parse']
    x['selection_basis_I']='latest printed document date among currently observed versions; not publication nor proof of final unrevisable version'
df=pd.read_csv(O/'settlement_native_all_versions.csv',dtype={'interval_label':str,'raw_value':str},keep_default_na=False)
df['value_native']=pd.to_numeric(df.value_native,errors='coerce')
proof=json.loads((W/'settlement_rectangle_omissions_pdfium_check.json').read_text(encoding='utf8'))
assert len(proof)==262 and all(x['exact_match'] for x in proof)
for x in proof:
    hit=(df.source_id==x['source_id'])&(df.interval_ordinal==x['interval'])&(df.column_ordinal==x['column'])
    assert hit.sum()==1
    df.loc[hit,'value_native']=float(x['pdfium_cell_text'].replace(',',''))
    df.loc[hit,'cell_status']='NUMERIC_PDFIUM_VERIFIED_RECTANGLE_OMISSION'
df.to_csv(O/'settlement_native_all_versions_verified.csv',index=False,encoding='utf8')
selected={}
for x in m['files']:
    key=(x['kind'],x['catalog_month_I']);old=selected.get(key)
    if x['body_month_match'] and (not old or (x['body_document_date'] or '',x['table_ordinal'])>(old['body_document_date'] or '',old['table_ordinal'])):selected[key]=x
chosen={x['id'] for x in selected.values()}
latest=df[df.source_id.isin(chosen)].copy()
latest.to_csv(O/'settlement_native_latest_observed.csv',index=False,encoding='utf8')
selection=pd.DataFrame([{k:v for k,v in x.items() if k not in ['cross_disagreements']} for x in selected.values()]);selection.to_csv(O/'settlement_latest_selection.csv',index=False,encoding='utf8')
wide=latest.pivot(index=['body_date','interval_ordinal'],columns='kind',values='value_native')
expected=[];start=date(2025,1,1)
from zoneinfo import ZoneInfo
while start<=date(2026,8,31):
    z=ZoneInfo('Europe/Bucharest');a=datetime.combine(start,datetime.min.time(),z);b=a+timedelta(days=1);n=int((b.timestamp()-a.timestamp())/900)
    expected.extend((start.isoformat(),i) for i in range(1,n+1));start+=timedelta(days=1)
physical=wide.reindex(pd.MultiIndex.from_tuples(expected,names=wide.index.names))
physical['month']=physical.index.get_level_values(0).str[:7]
physical['pattern_I']=physical.apply(lambda r:('UNIQUE_ONLY' if pd.notna(r.UNIQUE) and pd.isna(r.DEFICIT) and pd.isna(r.SURPLUS) else 'DUAL_ONLY' if pd.isna(r.UNIQUE) and pd.notna(r.DEFICIT) and pd.notna(r.SURPLUS) else 'MISSING_ALL_PRICES' if pd.isna(r.UNIQUE) and pd.isna(r.DEFICIT) and pd.isna(r.SURPLUS) else 'OTHER_PATTERN_REQUIRES_RULE'),axis=1)
physical.to_csv(O/'settlement_joint_native_ordinals.csv',encoding='utf8')
coverage=physical.groupby('month').agg(physical_slots_A=('pattern_I','size'),unique_numeric=('UNIQUE','count'),deficit_numeric=('DEFICIT','count'),surplus_numeric=('SURPLUS','count'),system_numeric=('SYSTEM','count'))
counts=physical.groupby(['month','pattern_I']).size().unstack(fill_value=0);coverage=coverage.join(counts)
coverage.to_csv(O/'settlement_coverage_by_month.csv',encoding='utf8')
revisions=[]
for key in selected:
    group=sorted([x for x in m['files'] if (x['kind'],x['catalog_month_I'])==key],key=lambda x:(x['body_document_date'] or '',x['table_ordinal']))
    for a,b in zip(group,group[1:]):
        f=df[df.source_id==a['id']].set_index(['body_date','interval_ordinal']);g=df[df.source_id==b['id']].set_index(['body_date','interval_ordinal'])
        j=f[['value_native']].join(g[['value_native']],lsuffix='_old',rsuffix='_new',how='outer');both=j.dropna();diff=both.value_native_new-both.value_native_old
        revisions.append({'kind':key[0],'month':key[1],'old_source':a['id'],'new_source':b['id'],'old_printed_date':a['body_document_date'],'new_printed_date':b['body_document_date'],'both_numeric':len(both),'changed_numeric':int((diff.abs()>.0000001).sum()),'max_absolute_change_native':float(diff.abs().max()) if len(diff) else None,'old_missing_new_numeric':int((j.value_native_old.isna()&j.value_native_new.notna()).sum()),'old_numeric_new_missing':int((j.value_native_old.notna()&j.value_native_new.isna()).sum()),'publication_time':None})
pd.DataFrame(revisions).to_csv(O/'settlement_observed_revision_comparison.csv',index=False,encoding='utf8')
summary={'downloaded_parsed_catalog_versions':len(m['files']),'selected_files':len(chosen),'months':20,'native_all_version_cells':len(df),'latest_native_cells':len(latest),'physical_slots_A':len(physical),'patterns':physical.pattern_I.value_counts().to_dict(),'system_numeric_physical':int(physical.SYSTEM.notna().sum()),'rect_grid_cross_checks':sum(x['rect_grid_cross_checks'] for x in m['files']),'rectangle_omissions_independently_pdfium_verified':len(proof),'extractor_disagreement_cells_unresolved':0,'source_short_row_tables':[{'id':x['id'],'rows':x['rows']} for x in m['files'] if x['rows'] not in [96,100]],'system_title_conflict_versions':sum(x['system_title_conflict'] for x in m['files']),'document_catalog_date_mismatches':[{'id':x['id'],'catalog':x['completion_date_label'],'body':x['body_document_date']} for x in m['files'] if not x['document_date_matches_catalog_parse']],'revision_pairs':len(revisions),'pairs_with_changed_values':sum(x['changed_numeric']>0 for x in revisions),'utc_approved':False,'asof_approved':False,'cash_approved':False}
(O/'settlement_analysis_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
(W/'settlement_parsing_manifest_with_body_dates.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(summary,ensure_ascii=False))
