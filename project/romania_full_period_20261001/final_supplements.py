from pathlib import Path
import json,pandas as pd
R=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent;O=R/'countries/RO/full_period_20261001'
s=json.loads((O/'analysis_summary.json').read_text(encoding='utf-8'));s['source_dates_mix']='2026-09-30 audited samples plus 2026-10-01 Asia/Shanghai batch; actual retrieved UTC dates per receipt';(O/'analysis_summary.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
# Rename unverified unit suffix only; no values changed. Research outputs not yet frozen.
for n in ['scada_native_hourly.csv','scada_price_joint_under_clock_A.csv','scada_negative_source_values.csv']:
    p=O/n;d=pd.read_csv(p,dtype={'sheet':'string','source_hour_label':'string','source_local_hour_end_label':'string'})
    if 'frequency_hz' in d:d=d.rename(columns={'frequency_hz':'frequency_source_unit_unconfirmed'});d.to_csv(p,index=False,encoding='utf-8-sig')
anomalies=pd.read_csv(O/'scada_clock_issues.csv').to_dict('records')
anomalies += [dict(issue='COLLECTOR_INITIAL_FORMAT_GUESS',source_id='TSO_GENERATION_ARCHIVE / CURRENT / INSTALLED_2026_0',location='receipts original.html vs actual ZIP/OLE bytes',handling='initial local collector default extension; raw receipt unchanged, actual signature in registry; not publisher error'),dict(issue='SETTLEMENT_MONTH_LABEL_URL_CONFLICT',source_id='TSO_FINAL_SETTLEMENT',location='Noiembrie 2025 VMA 21.01.2026 links filename EchSEN_202501',handling='catalog label and URL disagree; that particular body not verified, no silent month correction'),dict(issue='H1_EXPORT_YEAR_LABEL_REPEATED',source_id='TSO_H1_2026',location='PDF p24/printed20 physical export prose vs legend',handling='retain original labels; graph has 2025/2026 legend, no source prose relabel'),dict(issue='PROVIDER_SUM_NOT_EQUAL_DEMAND_TIMES_RATIO',source_id='tenderStatistics all months',location='capacity_provider_sum_checks.csv',count=12125,handling='exact comparison not matched; source precision/provider scope/revisions unknown; HHI limited to matched subset'),dict(issue='BNR_XML_NAMESPACE_DIFFERENCE',source_id='BNR_FX_2025 / 2026',location='root namespace http:// vs https://www.bnr.ro/xsd',handling='accept both official namespaces, validate nonempty Cube each year; do not assume transition date')]
pd.DataFrame(anomalies).to_csv(O/'source_anomalies_supplement.csv',index=False,encoding='utf-8-sig')
da=pd.read_csv(O/'da_qh_descriptive_alignment.csv');da['t']=pd.to_datetime(da.delivery_start_utc,utc=True);ph=da.set_index('t').price_eur_mwh.resample('h').mean().rename('price_eur_mwh').reset_index();sc=pd.read_csv(O/'scada_native_hourly.csv');sc=sc[sc.descriptive_usable_under_clock_A].copy();sc['t']=pd.to_datetime(sc.delivery_start_utc_provisional,utc=True);rows=[]
for shift in [-1,0,1]:
    g=sc.copy();g['t']=g.t+pd.Timedelta(hours=shift);g=g.merge(ph,on='t',validate='one_to_one');g['month']=g.source_local_date.str[:7]
    for month,h in g.groupby('month'):rows.append({'source_month':month,'clock_shift_from_A_hours':shift,'paired_hours':len(h),'pearson':h.scada_residual_consumption_minus_wind_solar_mw.corr(h.price_eur_mwh),'not_clock_definition_or_causal_proof':True})
pd.DataFrame(rows).to_csv(O/'scada_residual_clock_sensitivity.csv',index=False,encoding='utf-8-sig')
print('supplement anomalies',len(anomalies),'clock sensitivity rows',len(rows))
