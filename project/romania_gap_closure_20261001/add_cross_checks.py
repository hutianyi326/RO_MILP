from pathlib import Path
from datetime import date,timedelta
from decimal import Decimal,ROUND_HALF_UP
import csv,io,json,hashlib,xml.etree.ElementTree as ET
import pandas as pd
R=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent;O=R/'countries/RO/gap_closure_20261001';OLD=R/'countries/RO/full_period_20261001';RAW=R/'data/raw/RO/gap_closure/20261001'
def receipt(sid):
    return next(json.loads(p.read_text(encoding='utf-8')) for p in RAW.glob(sid+'__*/receipt.json') if json.loads(p.read_text(encoding='utf-8'))['status']=='HTTP_OK_UNPARSED')
def save(name,rows):pd.DataFrame(rows).to_csv(O/name,index=False,encoding='utf-8-sig')
rates={};br=receipt('BNR2024_BOUNDARY');tree=ET.fromstring((R/br['raw_file']).read_bytes())
for c in tree.iter():
    if c.tag.endswith('Cube') and c.get('date'):
        for v in c:
            if v.get('currency')=='EUR':rates[date.fromisoformat(c.get('date'))]=float(v.text)/float(v.get('multiplier','1'))
bnr=pd.read_csv(OLD/'bnr_reference_rates.csv')
rates.update({date.fromisoformat(x.date):x.ron_per_eur for x in bnr.itertuples()})
da=pd.read_csv(OLD/'da_native.csv');points=[];policy=[]
for sid in ['DA_RON_2025-01-01','DA_RON_2025-03-30','DA_RON_2025-10-01','DA_RON_2025-10-26','DA_RON_2026-08-31']:
    m=receipt(sid);d=date.fromisoformat(sid[7:]);trade=d-timedelta(days=1);fix=max(x for x in rates if x<trade);fx=rates[fix]
    rows=list(csv.reader(io.StringIO((R/m['raw_file']).read_text(encoding='utf-8-sig'))));native=[x for x in rows if len(x)>=6 and x[0]=='Romania' and x[1].isdigit()]
    assert any('Pret de Inchidere a Pietei [lei/MWh]' in x for x in rows)
    assert any(d.strftime('%d/%m/%Y') in cell for x in rows for cell in x)
    eur=da[da.source_market_date==d.isoformat()].set_index('native_interval');ds=[]
    for row in native:
        iv=int(row[1]);price=float(row[2]);ep=float(eur.loc[iv,'price_eur_mwh']);dif=price-ep*fx;ds.append(dif)
        points.append(dict(source_id=sid,source_date=d,interval=iv,native_ron_mwh=price,eur_mwh=ep,bnr_fixing_date=fix,ron_per_eur=fx,difference_ron_mwh=dif,rounding_bound_A=fx*.005+.005,within_display_bound_A=abs(dif)<=fx*.005+.005+1e-8,volume_mw_matches=float(row[3])==float(eur.loc[iv,'volume_mw']),raw_sha256=m['sha256'],rule_application_interpretation='I: latest BNR published date strictly before trading day D-1; point validation only',whole_period_rule_verified=False))
    policy.append(dict(source_id=sid,delivery_source_date=d,trading_date_I=trade,fixing_date_I=fix,rate=fx,rows=len(native),max_abs_difference_ron=max(map(abs,ds)),all_points_match_A=all(abs(x)<=fx*.005+.005+1e-8 for x in ds)))
save('da_ron_eur_sample_checks.csv',points);save('fx_market_day_sample_policy.csv',policy)
vol25=[1648.62,1323.21,1346.73,1154.19,1184.72,1159.45,1302.94,1201.35,1160.23,1465.13,1277.54,1467.60];pr25=[693.74,782.31,529.34,430.21,434.86,434.73,524.95,396.63,492.44,620.18,617.91,598.84]
vol26=[1520.89,1475.09,1355.94,1139.36,1111.17,888.36];pr26=[766.48,508.18,535.81,486.89,571.64,644.67]
off=pd.read_csv(OLD/'monthly_official_reconciliation.csv').set_index('month');controls=[]
daily=[]
for d,g in da.groupby('source_market_date'):
    dd=date.fromisoformat(d)
    if not date(2025,1,1)<=dd<=date(2026,8,31):continue
    fix=max(x for x in rates if x<dd-timedelta(days=1));fx=rates[fix]
    daily.append(dict(source_date=d,month=d[:7],fixing_date_I=str(fix),ron_per_eur=fx,derived_ron_daily_mean_I=(g.price_eur_mwh*fx).mean(),native_rows=len(g)))
daydf=pd.DataFrame(daily);save('da_fx_daily_candidate_application.csv',daily)
for y,vs,ps in [(2025,vol25,pr25),(2026,vol26,pr26)]:
    for mo,(vo,pr) in enumerate(zip(vs,ps),1):
        month=f'{y}-{mo:02d}';g=daydf[daydf.month==month];dv=float(off.loc[month,'native_derived_volume_mwh'])/1000;dp=g.derived_ron_daily_mean_I.mean();bound=g.ron_per_eur.max()*.005+.01
        controls.append(dict(month=month,anre_source_id='ANRE_MON_Iunie_2026',pdf_page=14,source_clock='CET OPCOM reprocessed by ANRE; daily-means arithmetic control',anre_volume_gwh=vo,opcom_native_volume_gwh=dv,difference_gwh=dv-vo,volume_display_bound_gwh_A=.005,volume_match=abs(dv-vo)<=.005+1e-10,anre_price_ron_mwh=pr,derived_fx_price_ron_mwh_I=dp,price_difference_ron_mwh=dp-pr,price_bound_A=bound,price_candidate_match_A=abs(dp-pr)<=bound,independent_measurement=False,same_utc_quarter_second_source_validation=False))
save('anre_opcom_monthly_cross_checks.csv',controls)
cap=pd.read_csv(OLD/'capacity_statistics.csv');prov=pd.read_csv(OLD/'capacity_provider_sum_checks.csv');cap['date_bucharest']=pd.to_datetime(cap.delivery_start_utc,utc=True).dt.tz_convert('Europe/Bucharest').dt.strftime('%Y-%m-%d')
rows=[]
for month in sorted(cap['source_month'].unique()):
 for prod in sorted(cap['product'].unique()):
    g=cap[(cap.source_month==month)&(cap['product']==prod)]
    q=prov[(prov['product']==prod)&(prov.delivery_start_utc.isin(g.delivery_start_utc))];rows.append(dict(month=month,product=prod,capacity_rows=len(g),unique_utc_starts=g.delivery_start_utc.nunique(),one_hour_duration_count=int((g.duration_hours==1).sum()),provider_checks=len(q),provider_sum_matches=int(q.complete_sum_check.sum()),provider_sum_unmatched=int((~q.complete_sum_check).sum()),early_FCR_public_auction_gap_interpretation='I: FCR daily competitive auctions start June2025 per STS Aug2025 p4; no zero service/payment inference' if prod=='FCR' and month<'2025-06' else '',payment_approved=False))
save('capacity_month_product_coverage_supplement.csv',rows)
dst=[]
for d in ['2025-03-30','2025-10-26','2026-03-29']:
    for prod in sorted(cap['product'].unique()):
        g=cap[(cap.date_bucharest==d)&(cap['product']==prod)];dst.append(dict(local_date=d,product=prod,hour_rows=len(g),unique_utc_starts=g.delivery_start_utc.nunique(),expected_physical_hours_A=25 if '10-26' in d else 23,all_duration_one_hour=bool((g.duration_hours==1).all()),not_a_provider_mapping_or_publication_check=True))
save('capacity_dst_observation.csv',dst)
summary=dict(fx_points=len(points),fx_point_matches=sum(x['within_display_bound_A'] for x in points),volume_matches=sum(x['volume_match'] for x in controls),anre_control_months=len(controls),candidate_price_matches=sum(x['price_candidate_match_A'] for x in controls),capacity_rows=len(cap),provider_matches=int(prov.complete_sum_check.sum()),provider_unmatched=int((~prov.complete_sum_check).sum()),all_model_gates_false=True)
(O/'supplement_cross_check_summary.json').write_text(json.dumps(summary,indent=2,default=int),encoding='utf-8');print(json.dumps(summary,default=int))
