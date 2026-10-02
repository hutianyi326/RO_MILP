"""Ex-post descriptive research, not model implementation or trading simulation."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal
from collections import Counter
from xml.etree import ElementTree as ET
import csv, hashlib, io, json, math, re
import pandas as pd
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[2];WORK=Path(__file__).resolve().parent
OUT=ROOT/'countries/RO/full_period_20261001';OUT.mkdir(parents=True,exist_ok=True)
UTC=timezone.utc;RO=ZoneInfo('Europe/Bucharest');CET=ZoneInfo('Europe/Brussels')
START=datetime(2025,1,1,tzinfo=RO).astimezone(UTC)
END=datetime(2026,9,1,tzinfo=RO).astimezone(UTC)
MONTHS=[f'{y}-{m:02}' for y in [2025,2026] for m in range(1,13) if (y,m)<=(2026,8)]
checks=[];anomalies=[];coverage=[];attempts=[]
def dump(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
def write(name,rows):
    if isinstance(rows,pd.DataFrame):rows.to_csv(OUT/name,index=False,encoding='utf-8-sig');return
    if not rows:return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def check(name,ok,detail=''):
    checks.append(dict(check=name,pass_=bool(ok),detail=detail))
def dt(t):return datetime.fromisoformat(t.replace('Z','+00:00'))
def iso(t):return t.astimezone(UTC).isoformat().replace('+00:00','Z')
def monthbounds(month,tz=RO):
    y,m=map(int,month.split('-'));a=datetime(y,m,1,tzinfo=tz)
    b=datetime(y+1,1,1,tzinfo=tz) if m==12 else datetime(y,m+1,1,tzinfo=tz)
    return a.astimezone(UTC),b.astimezone(UTC)
def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def provenance(m):return dict(source_id=m['id'],raw_file_hash=m['sha256'],retrieved_utc=m['retrieved_utc'],publication_time='',revision_time='',quality_flag='EX_POST_SNAPSHOT;NOT_ASOF_OR_MODEL_APPROVED')
def interval(a,b):return dict(delivery_start_utc=iso(a),delivery_end_utc=iso(b),local_time=a.astimezone(RO).isoformat(),duration_hours=(b-a).total_seconds()/3600)
for p in sorted((ROOT/'data/raw/RO/full_period/20261001').glob('*/receipt.json')):
    m=json.loads(p.read_text(encoding='utf-8'));m['receipt_file']=p.relative_to(ROOT).as_posix();attempts.append(m)
reuse=json.loads((WORK/'reused_samples.json').read_text(encoding='utf-8'))
for m in reuse:m['reused_from']='audited sample batch 20260930';attempts.append(m)
successful={}
for m in attempts:
    if not m.get('raw_file'):continue
    raw=ROOT/m['raw_file'];data=raw.read_bytes()
    check(m['id']+' raw SHA256',hashlib.sha256(data).hexdigest()==m['sha256'])
    if m.get('id') not in successful or m['retrieved_utc']>successful[m['id']]['retrieved_utc']:successful[m['id']]=m
write('source_attempts.csv',attempts)

# DA retains native contracts; QH replication below is descriptive alignment only.
da=[];daychecks=[]
for m in successful.values():
    if m.get('dataset')!='D02':continue
    text=(ROOT/m['raw_file']).read_text(encoding='utf-8-sig')
    if not text.startswith('"Mcp'):
        check(m['id']+' DA response format',False,'not native CSV');continue
    day=m.get('source_date',m['id'][3:13]);step=60 if day<'2025-10-01' else 15
    rows=list(csv.reader(io.StringIO(text)));records=[r for r in rows if r and r[0]=='Romania']
    a=datetime.fromisoformat(day).replace(tzinfo=CET).astimezone(UTC)
    b=(datetime.fromisoformat(day).replace(tzinfo=CET)+timedelta(days=1)).astimezone(UTC)
    expected=int((b-a).total_seconds()/(step*60))
    check(day+' DA native interval IDs',[int(r[1]) for r in records]==list(range(1,expected+1)))
    check(day+' DA native numeric fields',all(len(r)>=6 and all(re.fullmatch(r'-?\d+(?:\.\d+)?',s) for s in r[2:6]) for r in records))
    energy=Decimal(0);cash=Decimal(0);roundbound=Decimal(0);hours=Decimal(step)/60
    for r in records:
        price,volume,buy,sell=map(Decimal,r[2:6]);start=a+timedelta(minutes=step*(int(r[1])-1))
        check(day+' DA volume relation '+r[1],volume==max(buy,sell))
        energy+=volume*hours;cash+=price*volume*hours
        roundbound+=hours*(abs(volume)*Decimal('.005')+abs(price)*Decimal('.05')+Decimal('.00025'))
        da.append(dict(source_market_date=day,native_interval=int(r[1]),native_contract_id=day+'_'+r[1],native_resolution_minutes=step,price_eur_mwh=float(price),volume_mw=float(volume),buy_mw=float(buy),sell_mw=float(sell),energy_mwh=float(volume*hours),source_price=r[2],source_volume=r[3],currency='EUR',**interval(start,start+timedelta(minutes=step)),**provenance(m)))
    summary=next((r for r in rows if r and r[0].startswith('ROPEX_DAM_Base')),None)
    if summary and abs(energy-Decimal(summary[2]))>Decimal('.050001'):
        anomalies.append(dict(issue='DA_SUMMARY_ENERGY_MISMATCH',source_id=m['id'],date=day,source_value=summary[2],derived_value=str(energy),handling='source retained; use native MW × duration, not summary'))
    daychecks.append(dict(date=day,actual=len(records),expected=expected,duration_hours=float((b-a).total_seconds()/3600),energy_mwh=str(energy),price_volume_product_eur=str(cash),rounding_bound_A_eur=str(roundbound),source_id=m['id'],boundary_only=day<'2025-01-01'))
da=pd.DataFrame(da).sort_values('delivery_start_utc')
write('da_native.csv',da);write('da_daily_checks.csv',daychecks)
native=da.loc[(da.source_market_date>='2025-01-01')&(da.source_market_date<='2026-08-31')].copy()
check('DA native full source-day count',native.source_market_date.nunique()==608)
check('DA native unique UTC contracts',not da.delivery_start_utc.duplicated().any())
qh=[]
for r in da.to_dict('records'):
    a=dt(r['delivery_start_utc']);b=dt(r['delivery_end_utc'])
    while a<b:
        if START<=a<END:
            qh.append({k:r[k] for k in ['native_contract_id','native_resolution_minutes','price_eur_mwh','volume_mw','source_id','raw_file_hash','retrieved_utc']}|dict(delivery_start_utc=iso(a),delivery_end_utc=iso(a+timedelta(minutes=15)),local_time=a.astimezone(RO).isoformat(),duration_hours=.25,energy_mwh=r['volume_mw']*.25,mapping_only_no_independent_decision=True))
        a+=timedelta(minutes=15)
prices=pd.DataFrame(qh).sort_values('delivery_start_utc')
prices['t']=pd.to_datetime(prices.delivery_start_utc,utc=True)
prices['month']=prices.t.dt.tz_convert(RO).dt.strftime('%Y-%m')
prices['local_date']=prices.t.dt.tz_convert(RO).dt.strftime('%Y-%m-%d')
prices['hour']=prices.t.dt.tz_convert(RO).dt.hour
prices['weekend']=prices.t.dt.tz_convert(RO).dt.dayofweek>=5
expected_index=pd.date_range(START,END,freq='15min',inclusive='left')
check('DA Bucharest target QH complete',len(prices)==len(expected_index) and pd.DatetimeIndex(prices.t).equals(expected_index))
write('da_qh_descriptive_alignment.csv',prices.drop(columns='t'))
monthly=[]
for month,g in prices.groupby('month'):
    a,b=monthbounds(month);expected=int((b-a).total_seconds()/900)
    coverage.append(dict(dataset='DA',field='price',month=month,expected=expected,structural=len(g),numeric=g.price_eur_mwh.notna().sum(),timezone='Bucharest target; source Brussels',unit='EUR/MWh',role='descriptive mapping; not extra QH decisions'))
    p=g.price_eur_mwh
    monthly.append(dict(month=month,intervals=len(g),hours=len(g)/4,time_mean_eur_mwh=p.mean(),volume_weighted_mean_eur_mwh=(p*g.energy_mwh).sum()/g.energy_mwh.sum(),median=p.median(),p05=p.quantile(.05),p95=p.quantile(.95),std_population=p.std(ddof=0),minimum=p.min(),maximum=p.max(),negative_hours=(p<0).sum()/4,zero_hours=(p==0).sum()/4,observed_market_volume_mwh=g.energy_mwh.sum()))
write('da_monthly_statistics.csv',monthly)
hourly=prices.groupby(['month','hour']).price_eur_mwh.agg(['mean','count']).reset_index()
write('da_hourly_heatmap_values.csv',hourly)
groupstats=prices.groupby(['month','weekend']).price_eur_mwh.agg(['mean','count','min','max']).reset_index();write('da_weekday_weekend.csv',groupstats)
windows=[];rollingstats=[]
for hours,n in [(2,8),(4,16)]:
    rolling=prices.price_eur_mwh.rolling(n,min_periods=n).mean()
    # Physical clock elapsed length, including repeated/skipped DST local hours.
    good=(prices.t-prices.t.shift(n-1))==pd.Timedelta(minutes=15*(n-1))
    valid=rolling[good]
    rollingstats.append(dict(duration_hours=hours,valid_windows=len(valid),minimum_mean=valid.min(),maximum_mean=valid.max(),median_mean=valid.median(),negative_mean_windows=(valid<0).sum(),cross_day_allowed=True,interpretation='overlapping price windows; no device operation, transaction sequence, efficiency or income'))
    for day,g in prices.groupby('local_date'):
        v=g.price_eur_mwh.rolling(n,min_periods=n).mean().dropna()
        if v.empty:continue
        lo=v.idxmin();hi=v.idxmax()
        windows.append(dict(local_date=day,duration_hours=hours,valid_daily_windows=len(v),low_mean=v.loc[lo],high_mean=v.loc[hi],price_window_range=v.loc[hi]-v.loc[lo],low_start_utc=prices.loc[lo-n+1,'delivery_start_utc'],high_start_utc=prices.loc[hi-n+1,'delivery_start_utc'],daily_hours=len(g)/4,chronology_not_enforced=True,not_bess_revenue=True))
write('price_windows_2h_4h_daily.csv',windows);write('price_windows_2h_4h_full.csv',rollingstats)
events=[]
negative=prices.price_eur_mwh<0
segments=(negative.ne(negative.shift())|prices.t.diff().ne(pd.Timedelta(minutes=15))).cumsum()
for _,g in prices[negative].groupby(segments):
    events.append(dict(kind='negative_price_run',start_utc=g.delivery_start_utc.iloc[0],end_utc=g.delivery_end_utc.iloc[-1],duration_hours=len(g)/4,minimum_price=g.price_eur_mwh.min(),source_id=g.source_id.iloc[0]))
write('negative_price_events.csv',events)

# Wider native system tables preserve every scalar and every exchange component.
tables={r:[] for r in ['dailyConsumptionOverview','activatedBalancingEnergyOverview','scheduledExchanges']};capacity=[];capdays=[];providers=[]
for m in successful.values():
    report=m.get('report')
    if report not in list(tables)+['tenderStatistics']:continue
    obj=json.loads((ROOT/m['raw_file']).read_text(encoding='utf-8-sig'))
    items=obj.get('itemList',[]);page=obj.get('pageInfo',{})
    check(m['id']+' pagination complete',page.get('total')==len(items))
    check(m['id']+' public report error map',not obj.get('uuAppErrorMap'))
    a,b=dt(m['requested_start_utc']),dt(m['requested_end_utc'])
    if report=='tenderStatistics':
        for tender in items:
            ta,tb=map(dt,[tender['timeInterval']['from'],tender['timeInterval']['to']])
            if not (a<=ta<b):continue
            code=tender['tenderCode']
            for service in tender.get('tenderServiceList',[]):
                product=service['serviceCode'];rr=service.get('tenderStatistics',{}).get('timeIntervalList',[]);kept=[]
                for r in rr:
                    ra,rb=map(dt,[r['timeInterval']['from'],r['timeInterval']['to']])
                    if not (ta<=ra<rb<=tb):
                        anomalies.append(dict(issue='CAP_OUTSIDE_TENDER',source_id=m['id'],date=ta.astimezone(RO).date().isoformat(),product=product,start_utc=iso(ra),handling='retained in raw; excluded from in-tender descriptive table'));continue
                    kept.append(r)
                    capacity.append(dict(tender_code=code,product=product,source_month=m['month'],price_scheme=tender.get('priceScheme'),demand_mw=r.get('tenderDemand'),satisfied_ratio=r.get('tenderSatisfiedDemand'),tender_price_LEI_denominator_unknown=r.get('tenderPrice'),average_offered_price_LEI_denominator_unknown=r.get('averageOfferedPrice'),average_accepted_price_LEI_denominator_unknown=r.get('averageAcceptedPrice'),price_not_payment=True,**interval(ra,rb),**provenance(m)))
                expected=int((tb-ta).total_seconds()/3600)
                actual_hours=sum((dt(r['timeInterval']['to'])-dt(r['timeInterval']['from'])).total_seconds()/3600 for r in kept)
                capdays.append(dict(date=ta.astimezone(RO).date().isoformat(),product=product,tender_code=code,expected_tender_hours=expected,raw_intervals=len(rr),in_tender_hours=actual_hours,complete=actual_hours==expected,source_id=m['id']))
                if actual_hours!=expected:anomalies.append(dict(issue='CAP_TENDER_MISSING_HOUR',source_id=m['id'],date=ta.astimezone(RO).date().isoformat(),product=product,expected=expected,actual=actual_hours,handling='no interpolation; mark product-day incomplete'))
                if 'contractedPower' in service:providers.append(dict(tender_code=code,product=product,source_id=m['id'],contracted_power=service['contractedPower']))
        continue
    starts=[]
    for r in items:
        ra,rb=map(dt,[r['timeInterval']['from'],r['timeInterval']['to']]);starts.append(ra)
        check(m['id']+' interval bounds '+iso(ra),a<=ra<rb<=b and (rb-ra).total_seconds()==900)
        values={}
        if report=='dailyConsumptionOverview':values={k:r.get(k) for k in ['grossRealizedConsumption','grossForecastConsumption']};values['source_last_update']=r.get('lastUpdate')
        elif report=='activatedBalancingEnergyOverview':values={k:r.get(k) for k in ['fcr','aFRR_Up','aFRR_Down','mFRR_Up','mFRR_Down','rr_Up','rr_Down']}
        else:values={border+'.'+component:v for border in ['huro','rohu','mdro','romd','roua','uaro','bgro','robg','rors','rsro'] for component,v in r.get(border,{}).items()}
        tables[report].append(dict(source_month=m['month'],**interval(ra,rb),**values,**provenance(m)))
    check(m['id']+' native QH count',len(items)==int((b-a).total_seconds()/900))
    check(m['id']+' native UTC distinct contiguous',len(set(starts))==len(starts) and sorted(starts)==[a+timedelta(minutes=15*i) for i in range(len(items))])
write('capacity_statistics.csv',capacity);write('capacity_product_days.csv',capdays);dump('capacity_provider_structures.json',providers)
system={}
for report,rows in tables.items():
    df=pd.DataFrame(rows).sort_values('delivery_start_utc')
    check(report+' native UTC unique',not df.delivery_start_utc.duplicated().any())
    df['t']=pd.to_datetime(df.delivery_start_utc,utc=True)
    df=df[(df.t>=START)&(df.t<END)].copy()
    df['month']=df.t.dt.tz_convert(RO).dt.strftime('%Y-%m')
    write(report+'.csv',df.drop(columns='t'));system[report]=df
    check(report+' Bucharest target structural coverage',pd.DatetimeIndex(df.t).equals(expected_index))
    fields=['grossRealizedConsumption','grossForecastConsumption'] if report=='dailyConsumptionOverview' else ['fcr','aFRR_Up','aFRR_Down','mFRR_Up','mFRR_Down','rr_Up','rr_Down'] if report=='activatedBalancingEnergyOverview' else [c for c in df.columns if '.' in c]
    for month,g in df.groupby('month'):
        ma,mb=monthbounds(month);expected=int((mb-ma).total_seconds()/900)
        for field in fields:
            coverage.append(dict(dataset=report,field=field,month=month,expected=expected,structural=len(g),numeric=g[field].map(finite).sum(),timezone='Bucharest target',unit='MWh' if report=='activatedBalancingEnergyOverview' else 'MW',role='system actual' if field=='grossRealizedConsumption' else 'latest forecast not historical vintage' if field=='grossForecastConsumption' else 'system aggregate; not station outcome'))

load=system['dailyConsumptionOverview'];loadstats=[]
for month,g in load.groupby('month'):
    v=g.grossRealizedConsumption;valid=v.notna()
    loadstats.append(dict(month=month,structural=len(g),numeric=valid.sum(),mean_mw=v.mean(),peak_mw=v.max(),minimum_mw=v.min(),observed_energy_mwh=v.sum(min_count=1)*.25,complete_month=valid.all()))
write('load_monthly_statistics.csv',loadstats)
load['hour']=load.t.dt.tz_convert(RO).dt.hour
write('load_hourly_profile.csv',load.groupby(['month','hour']).grossRealizedConsumption.agg(['mean','count']).reset_index())
ramp=load[['delivery_start_utc','grossRealizedConsumption']].copy();ramp['change_mw_15min']=load.grossRealizedConsumption.diff().where(load.t.diff()==pd.Timedelta(minutes=15));write('load_ramps.csv',ramp)
act=system['activatedBalancingEnergyOverview'];actstats=[]
for month,g in act.groupby('month'):
    for field in ['fcr','aFRR_Up','aFRR_Down','mFRR_Up','mFRR_Down','rr_Up','rr_Down']:
        v=g[field];actstats.append(dict(month=month,product_direction=field,structural=len(g),numeric=v.notna().sum(),positive_intervals=(v>0).sum(),zero_intervals=(v==0).sum(),observed_energy_mwh=v.sum(min_count=1),maximum_interval_mwh=v.max(),complete_month=v.notna().all()))
write('activation_monthly_statistics.csv',actstats)
actevents=[]
for field in ['aFRR_Up','aFRR_Down']:
    positive=act[field]>0;groups=(positive.ne(positive.shift())|act.t.diff().ne(pd.Timedelta(minutes=15))).cumsum()
    for _,g in act[positive].groupby(groups):actevents.append(dict(product=field,start_utc=g.delivery_start_utc.iloc[0],end_utc=g.delivery_end_utc.iloc[-1],duration_hours=len(g)/4,energy_mwh=g[field].sum(),source_id=g.source_id.iloc[0],not_station_delivery=True))
write('activation_continuous_events.csv',actevents)
both=(act.aFRR_Up>0)&(act.aFRR_Down>0);write('afrr_both_directions.csv',act.loc[both,['delivery_start_utc','aFRR_Up','aFRR_Down','source_id']])
exchange=system['scheduledExchanges'];borderstats=[]
for month,g in exchange.groupby('month'):
    for border in ['huro','rohu','mdro','romd','roua','uaro','bgro','robg','rors','rsro']:
        v=g[border+'.commercial'];borderstats.append(dict(month=month,direction=border,component='commercial',numeric=v.notna().sum(),structural=len(g),observed_scheduled_energy_mwh=v.sum(min_count=1)*.25,mean_mw=v.mean(),not_physical_flow=True))
write('commercial_exchange_monthly.csv',borderstats)
inc=['huro','mdro','uaro','bgro','rsro'];out=['rohu','romd','roua','robg','rors']
exchange['net_scheduled_import_mw']=exchange[[x+'.commercial' for x in inc]].sum(axis=1,min_count=5)-exchange[[x+'.commercial' for x in out]].sum(axis=1,min_count=5)
write('commercial_net_import.csv',exchange[['delivery_start_utc','net_scheduled_import_mw','source_id']])

cap=pd.DataFrame(capacity);cap['t']=pd.to_datetime(cap.delivery_start_utc,utc=True);cap['month']=cap.t.dt.tz_convert(RO).dt.strftime('%Y-%m')
check('capacity native tender/product/UTC keys unique',not cap.duplicated(['tender_code','product','delivery_start_utc']).any())
capstats=[]
for month,product in [(m,p) for m in MONTHS for p in ['FCR','aFRRUp','aFRRDown','mFRRUp','mFRRDown']]:
    g=cap[(cap['month']==month)&(cap['product']==product)]
    ma,mb=monthbounds(month);expected=int((mb-ma).total_seconds()/3600)
    coverage.append(dict(dataset='capacity',field=product+' demand MW',month=month,expected=expected,structural=len(g),numeric=g.demand_mw.notna().sum(),timezone='Bucharest',unit='MW',role='missing tender ≠ zero demand; historical applicability unknown'))
    for field in ['satisfied_ratio','tender_price_LEI_denominator_unknown','average_offered_price_LEI_denominator_unknown','average_accepted_price_LEI_denominator_unknown']:
        coverage.append(dict(dataset='capacity',field=product+' '+field,month=month,expected=expected,structural=len(g),numeric=g[field].notna().sum(),timezone='Bucharest',unit='ratio' if field=='satisfied_ratio' else 'LEI denominator unknown',role='not payment; missing tender not zero'))
    price=g.average_accepted_price_LEI_denominator_unknown
    capstats.append(dict(month=month,product=product,in_tender_hours=g.duration_hours.sum(),demand_numeric=g.demand_mw.notna().sum(),demand_mean_mw=g.demand_mw.mean(),demand_min_mw=g.demand_mw.min(),demand_max_mw=g.demand_mw.max(),satisfied_ratio_mean=g.satisfied_ratio.mean(),accepted_price_numeric=price.notna().sum(),accepted_price_mean_raw_LEI=price.mean(),accepted_price_min_raw_LEI=price.min(),accepted_price_max_raw_LEI=price.max(),price_denominator='UNVERIFIED; NOT PAYMENT'))
write('capacity_monthly_statistics.csv',capstats)

# Joint descriptive price-load table uses actual UTC intersection, no residual load proxy.
joint=prices[['delivery_start_utc','price_eur_mwh','month']].merge(load[['delivery_start_utc','grossRealizedConsumption']],on='delivery_start_utc',how='inner',validate='one_to_one').merge(exchange[['delivery_start_utc','net_scheduled_import_mw']],on='delivery_start_utc',how='inner',validate='one_to_one')
write('joint_descriptive_price_load_exchange.csv',joint)
correlations=[]
for month,g in joint.groupby('month'):
    for field in ['grossRealizedConsumption','net_scheduled_import_mw']:
        valid=g[['price_eur_mwh',field]].dropna();correlations.append(dict(month=month,field=field,paired_intervals=len(valid),pearson=valid.price_eur_mwh.corr(valid[field]),causality_not_established=True))
write('descriptive_correlations.csv',correlations)

# Official monthly PDF control extraction, no source figures guessed if extraction fails.
controls=[];pdfindex=[];bnr=[]
for m in successful.values():
    path=ROOT/m['raw_file'];body=path.read_bytes()
    if body.startswith(b'%PDF'):
        reader=PdfReader(path);texts=[p.extract_text() or '' for p in reader.pages]
        destination=WORK/'pdf_text'/f"{m['id']}.txt";destination.parent.mkdir(exist_ok=True);destination.write_text('\n\n'.join(f'PDF PAGE {i+1}\n{text}' for i,text in enumerate(texts)),encoding='utf-8')
        pdfindex.append(dict(source_id=m['id'],pages=len(reader.pages),raw_file=m['raw_file'],sha256=m['sha256'],text_file=destination.relative_to(ROOT).as_posix()))
        if m['id'].startswith('MONTH_'):
            # Preserve actual PDF page text for independently checking each parsed control.
            controls.append(dict(month=m['id'][6:],source_id=m['id'],location='PDF p2; Day-Ahead Market comparison table',page2_text=texts[1] if len(texts)>1 else '',parse_status='CONTROL_TEXT_REQUIRES_TABLE_EXTRACTION'))
    if m['id'].startswith('BNR_FX_') and body.lstrip().startswith(b'<?xml'):
        doc=ET.fromstring(body);namespace=doc.tag.split('}')[0].lstrip('{');ns={'b':namespace}
        check(m['id']+' official XML namespace',namespace in ['http://www.bnr.ro/xsd','https://www.bnr.ro/xsd'])
        cubes=doc.findall('.//b:Cube',ns)
        check(m['id']+' annual XML contains dated cubes',bool(cubes))
        for cube in cubes:
            day=cube.get('date')
            if not ('2025-01-01'<=day<='2026-08-31'):continue
            eur=cube.find("b:Rate[@currency='EUR']",ns)
            if eur is not None:bnr.append(dict(date=day,ron_per_eur=float(eur.text),source_value=eur.text,unit='RON/EUR',source_id=m['id'],raw_file_hash=m['sha256'],publication_time='',settlement_usage_day_unconfirmed=True,no_weekend_fill=True))
write('monthly_pdf_control_text.csv',controls);write('pdf_index.csv',pdfindex);write('bnr_reference_rates.csv',bnr)
write('source_anomalies.csv',anomalies);write('monthly_coverage.csv',coverage)

summary=dict(target_timezone='Europe/Bucharest',start_utc=iso(START),end_utc_exclusive=iso(END),expected_qh=len(expected_index),native_DA_days=native.source_market_date.nunique(),native_DA_intervals=len(native),DA_target_qh=len(prices),target_hours=len(prices)/4,DA_time_mean_eur_mwh=prices.price_eur_mwh.mean(),DA_negative_hours=(prices.price_eur_mwh<0).sum()/4,DA_zero_hours=(prices.price_eur_mwh==0).sum()/4,DA_minimum=prices.price_eur_mwh.min(),DA_maximum=prices.price_eur_mwh.max(),load_numeric=load.grossRealizedConsumption.notna().sum(),activation_aFRR_Up_numeric=act.aFRR_Up.notna().sum(),activation_aFRR_Down_numeric=act.aFRR_Down.notna().sum(),afrr_both_direction_intervals=both.sum(),capacity_hours=len(cap),capacity_products=sorted(cap['product'].unique().tolist()),capacity_product_days=len(capdays),capacity_incomplete_product_days=sum(not d['complete'] for d in capdays),BNR_rates=len(bnr),monthly_pdf_controls=len(controls),source_anomalies=len(anomalies),new_attempts=len(attempts)-len(reuse),reused_DA_originals=len(reuse),source_dates_mix='2026-09-30 audited samples plus 2026-10-01 Asia/Shanghai batch; actual retrieved UTC dates per receipt',asof_input_approved=False,complete_step3=False)
summary={k:int(v) if hasattr(v,'dtype') and str(v.dtype).startswith('int') else v for k,v in summary.items()}
dump('analysis_summary.json',summary)
dump('verification.json',dict(status='PASS' if all(c['pass_'] for c in checks) else 'FAIL',checks=len(checks),failed=[c for c in checks if not c['pass_']],scope='integrity, structural coverage and transformations; source anomalies and semantic restrictions separate',detail=checks))
print(json.dumps(summary,ensure_ascii=False,default=str));print('checks',len(checks),'fail',sum(not c['pass_'] for c in checks))
