"""Calibrate monthly research share caps; no production MILP changes."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import calendar, csv, gzip, hashlib, json, re, sys
import numpy as np
import pandas as pd
import openpyxl
from download_sources import ROOT, REPO, existing, discover, KINDS

TZ=ZoneInfo('Europe/Bucharest')
PRODUCTS={'FCR':'FCR','aFRR Up':'aFRRUp','aFRR Down':'aFRRDown'}
PETROM='30XROPETROM----4'

def save(name,rows):
    if not rows:
        (ROOT/name).write_text('',encoding='utf-8');return
    opener=gzip.open if name.endswith('.gz') else open
    with opener(ROOT/name,'wt',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def expected_hours(date):
    a=datetime.fromisoformat(date).replace(tzinfo=TZ)
    return int(((a+timedelta(days=1)).astimezone(timezone.utc)-a.astimezone(timezone.utc)).total_seconds()/3600)

def bsp(s):
    m=re.search(r'\(([^()]*)\)\s*$',str(s));assert m,s
    return m[1].strip()

def read(path):
    wb=openpyxl.load_workbook(path,read_only=True,data_only=True)
    rows=list(wb.active.values);wb.close()
    header=next(i for i,r in enumerate(rows[:20]) if r[0]=='DATE')
    norm=lambda s:re.sub('[^A-Z]','',str(s).upper())
    lookup={norm(v):i for i,v in enumerate(rows[header]) if v is not None}
    hourly='INTERVAL' in lookup
    names=['DATE','MTU','INTERVAL','SERVICE','BMP','TENDER_NO','BID','DEMANDED POWER','ACCEPTED_POWER'] if hourly else ['DATE','MTU','SERVICE','BMP','TENDER_NO','BID','DEMANDED POWER','ACCEPTED_POWER','AVERAGE PRICE']
    assert all(norm(n) in lookup or (norm(n)=='ACCEPTEDPOWER' and 'TOTALCOST' in lookup and 'AVERAGEPRICE' in lookup) for n in names),(path.name,lookup)
    canon=[]
    for r in rows[header+1:]:
        rr=tuple(r[lookup[norm(n)]] if norm(n) in lookup else (r[lookup['TOTALCOST']]/r[lookup['AVERAGEPRICE']] if r[lookup['AVERAGEPRICE']] not in (None,0) else None) for n in names)
        if not hourly:rr+=(r[lookup['OFFEREDPOWER']] if 'OFFEREDPOWER' in lookup else None,)
        canon.append(rr)
    schema=dict(file=path.name,header_row=header+1,offered_power_published='OFFEREDPOWER' in lookup,original_headers=list(rows[header]),accepted_derived_cost_divided_price='ACCEPTEDPOWER' not in lookup)
    return [None]*8+canon,schema

def day(date,files):
    nh=expected_hours(date);cache=ROOT/'parsed_days'/f'{date}.json'
    cache.parent.mkdir(exist_ok=True)
    hashes={k:r['sha256'] for k,(path,r) in files.items()}
    if cache.exists():
        old=json.loads(cache.read_text(encoding='utf-8'))
        if old.get('hashes')==hashes and old.get('parser_version')==3:return old
    result=dict(date=date,hashes=hashes,parser_version=3,expected_hours=nh,issues=[],inferences=[],mismatches=[],hourly=[],daily=[],market=[],offered_daily=[],schemas=[],checks={})
    rows={}
    for k,(path,r) in files.items():
        rows[k],schema=read(path);result['schemas'].append(dict(kind=k,**schema))
    dr=rows['ansTenderResults'];hr=rows['ansContractPurchasedReserves']
    dailybid={};totals={};daydem=defaultdict(set);names={}
    for r in dr[8:]:
        if r[2] not in PRODUCTS:continue
        assert r[0].strftime('%Y-%m-%d')==date,(date,'wrong daily date',r[0])
        p=PRODUCTS[r[2]]
        if r[3]=='Grand Total':
            assert p not in totals
            totals[p]=float(r[7]);continue
        b=bsp(r[3]);names[b]=r[3];key=(p,b,r[4],r[5])
        assert key not in dailybid,(date,'duplicate daily bid',key)
        assert r[7] is None or (isinstance(r[7],(int,float)) and r[7]>=0)
        dailybid[key]=r[7]
        if r[9] is not None:
            result['offered_daily'].append(dict(date=date,product=p,bsp=b,tender=r[4],bid=r[5],offered_mw_hours=float(r[9]),accepted_mw_hours=r[7]))
        daydem[p].add(float(r[6]))
    ds=defaultdict(float);badproducts=set()
    for p,total in totals.items():
        known=sum(v for k,v in dailybid.items() if k[0]==p and v is not None)
        if abs(known-total)>1e-7:
            result['issues'].append(dict(product=p,issue='daily_product_total_mismatch',detail=f'{known} vs {total}'));badproducts.add(p)
    for key,v in dailybid.items():
        if key[0] in badproducts:continue
        if v is None:
            result['inferences'].append(dict(product=key[0],bsp=key[1],kind='daily_blank_zero',cells=1,reason='Other nonnegative daily quantities exhaust product Grand Total'))
            v=0
        ds[key[:2]]+=v
    bids=defaultdict(dict);dem=defaultdict(set);labels=defaultdict(set)
    for r in hr[8:]:
        if r[3] not in PRODUCTS:continue
        assert r[0].strftime('%Y-%m-%d')==date,(date,'wrong hourly date',r[0])
        p=PRODUCTS[r[3]];b=bsp(r[4]);names[b]=r[4];key=(p,b,r[5],r[6]);i=int(r[2])
        assert i not in bids[key],(date,'duplicate hourly bid',key,i)
        assert r[8] is None or (isinstance(r[8],(int,float)) and r[8]>=0)
        bids[key][i]=r[8];dem[p,i].add(float(r[7]));labels[i].add(str(r[1]))
    # Report ordinal interval maps monotonically into the local delivery day's UTC hours.
    expected=set(range(1,nh+1));group=defaultdict(list);seen=defaultdict(set)
    for key,vs in bids.items():
        p,b,_,_=key
        if set(vs)!=expected:
            result['issues'].append(dict(product=p,issue='bid_interval_coverage',detail=f'{key}: {sorted(vs)} expected {nh}'));badproducts.add(p)
        seen[p].add(b)
        for i,v in vs.items():group[p,b,i].append(v)
        if key in dailybid and abs(sum(v for v in vs.values() if v is not None)-(dailybid[key] or 0))>1e-7:
            result['mismatches'].append(dict(product=p,bsp=b,tender=key[2],bid=key[3],hourly_known_sum=sum(v for v in vs.values() if v is not None),daily_bid_value=dailybid[key]))
    for p in PRODUCTS.values():
        if p not in seen:
            result['issues'].append(dict(product=p,issue='product_absent_from_hourly_report',detail='No observed requirement or supplier quantities; not inferred zero market demand'))
            continue
        if p not in totals or {b for pp,b in ds if pp==p}!=seen[p]:
            result['issues'].append(dict(product=p,issue='daily_hourly_supplier_set_mismatch',detail='Cannot reconcile'));badproducts.add(p)
        if any(len(dem[p,i])!=1 for i in expected):
            result['issues'].append(dict(product=p,issue='demand_conflict_or_missing',detail='Expected one unique demand per interval'));badproducts.add(p)
        if p in badproducts:continue
        if len(daydem[p])!=1 or abs(sum(next(iter(dem[p,i])) for i in expected)-next(iter(daydem[p])))>1e-7:
            result['issues'].append(dict(product=p,issue='demand_day_hour_mismatch',detail=str(daydem[p])));badproducts.add(p);continue
        for b in seen[p]:
            vals=[v for i in expected for v in group[p,b,i]]
            known=sum(v for v in vals if v is not None)
            if abs(known-ds[p,b])>1e-7:
                result['issues'].append(dict(product=p,issue='supplier_day_hour_mismatch',detail=f'{b}: {known} vs {ds[p,b]}'));badproducts.add(p)
            elif any(v is None for v in vals):
                result['inferences'].append(dict(product=p,bsp=b,kind='hourly_blank_zero',cells=sum(v is None for v in vals),reason='Known nonnegative hourly quantities exhaust daily supplier total; BID ids not joined'))
        if p in badproducts:continue
        for b in sorted(seen[p]):
            result['daily'].append(dict(date=date,product=p,bsp=b,name=names[b],awarded_mw_hours=ds[p,b],demand_mw_hours=next(iter(daydem[p])),system_awarded_mw_hours=totals[p],hours=nh))
        for i in sorted(expected):
            demand=next(iter(dem[p,i]));q={b:sum(v or 0 for v in group[p,b,i]) for b in seen[p]};total=sum(q.values())
            ts=datetime.fromisoformat(date).replace(tzinfo=TZ).astimezone(timezone.utc)+timedelta(hours=i-1)
            result['market'].append(dict(date=date,interval=i,delivery_start_utc=ts.isoformat(),product=p,demand_mw=demand,system_awarded_mw=total))
            for b,v in sorted(q.items()):
                result['hourly'].append(dict(date=date,interval=i,delivery_start_utc=ts.isoformat(),product=p,bsp=b,awarded_mw=v,demand_mw=demand,share_of_demand=v/demand if demand>0 else None))
    result['checks']=dict(valid_product_days=len({r['product'] for r in result['market']}),supplier_days_reconciled=len(result['daily']),hourly_rows=len(result['hourly']))
    cache.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    return result

def run():
    inventory=discover();found=existing();partial='--partial' in sys.argv
    for key,(path,r) in found.items():assert hashlib.sha256(path.read_bytes()).hexdigest()==r['sha256'],key
    if not partial and '--available' not in sys.argv:assert set(found)==set(inventory),(len(found),len(inventory))
    days=sorted({k[0] for k in found if all((k[0],kind) in found for kind in KINDS)})
    results=[];fatal=[]
    for ix,d in enumerate(days):
        try:results.append(day(d,{k:found[d,k] for k in KINDS}))
        except Exception as exc:fatal.append(dict(date=d,error_type=type(exc).__name__,detail=str(exc)))
        if (ix+1)%50==0:print('Parsed',ix+1,'/',len(days),'fatal',len(fatal),flush=True)
    (ROOT/'parse_errors.json').write_text(json.dumps(fatal,ensure_ascii=False,indent=2),encoding='utf-8')
    issues=[dict(date=r['date'],**v) for r in results for v in r['issues']]
    save('data_issues.csv',issues)
    (ROOT/'parse_progress.json').write_text(json.dumps(dict(parsed_days=len(results),fatal_days=len(fatal),issue_count=len(issues)),indent=2),encoding='utf-8')
    if partial:
        print('Partial audit',len(results),'days;',len(fatal),'fatal;',len(issues),'issues',flush=True);return
    assert not fatal,'See parse_errors.json'
    hourly=[v for r in results for v in r['hourly']];daily=[v for r in results for v in r['daily']];market=[v for r in results for v in r['market']]
    h=pd.DataFrame(hourly);d=pd.DataFrame(daily);m=pd.DataFrame(market)
    for f in (h,d,m):f['month']=f.date.str[:7]
    summaries=[];coverage=[]
    for month in pd.period_range('2025-01','2026-08',freq='M').astype(str):
        nd=calendar.monthrange(int(month[:4]),int(month[5:]))[1]
        nh=sum(expected_hours(f'{month}-{day:02d}') for day in range(1,nd+1))
        for p in PRODUCTS.values():
            mh=m[(m.month==month)&(m['product']==p)]
            coverage.append(dict(month=month,product=p,expected_days=nd,valid_days=mh.date.nunique(),expected_hours=nh,valid_hours=len(mh),demand_min_mw=float(mh.demand_mw.min()) if len(mh) else None,demand_max_mw=float(mh.demand_mw.max()) if len(mh) else None))
            sub=h[(h.month==month)&(h['product']==p)]
            for b,rs in sub.groupby('bsp'):
                qty=rs.awarded_mw;shares=rs.share_of_demand.dropna();reported_days=rs.date.nunique()
                if shares.empty:continue
                summaries.append(dict(month=month,product=p,bsp=b,name=d[(d.month==month)&(d['product']==p)&(d.bsp==b)].iloc[0]['name'],
                    reported_days=reported_days,reported_hours=len(rs),positive_hours=int((qty>0).sum()),
                    eligible_full_month=bool(reported_days==nd and len(rs)==nh and len(shares)==nh and qty.sum()>0),
                    eligible_complete_valid_sample=bool(len(mh)>=.9*nh and len(rs)==len(mh) and len(shares)==len(mh) and qty.sum()>0),
                    calendar_hour_coverage=float(len(rs)/nh),
                    mean_awarded_mw_reported_hours=float(qty.mean()),capacity_mw_hours=float(qty.sum()),
                    hourly_share_p50=float(np.quantile(shares,.5)),hourly_share_p90=float(np.quantile(shares,.9)),
                    share_of_observed_month_demand=float(qty.sum()/mh.demand_mw.sum())))
    parameters=[]
    for month in pd.period_range('2025-01','2026-08',freq='M').astype(str):
        ss=[r for r in summaries if r['month']==month];cv={r['product']:r for r in coverage if r['month']==month}
        f=[r for r in ss if r['product']=='FCR' and r['bsp']==PETROM and r['calendar_hour_coverage']>=.8 and r['positive_hours']>0]
        sf=f[0]['hourly_share_p90'] if f else None
        a={};counts={}
        for p in ('aFRRUp','aFRRDown'):
            ps=[r for r in ss if r['product']==p and r['eligible_complete_valid_sample']]
            counts[p]=len(ps);a[p]=float(np.median([r['hourly_share_p90'] for r in ps])) if ps else None
        sa=min(a.values()) if all(v is not None for v in a.values()) else None
        parameters.append(dict(month=month,fcr_market_share_cap=sf,afrr_market_share_cap=sa,
            afrr_up_directional_reference=a['aFRRUp'],afrr_down_directional_reference=a['aFRRDown'],
            fcr_status=('calibrated_PETROM_full_month_P90' if f[0]['eligible_full_month'] else 'calibrated_PETROM_partial_month_P90') if sf is not None else 'not_calibrated_no_full_month_PETROM',
            afrr_status=('calibrated_directional_minimum_full_month' if all(cv[p]['valid_hours']==cv[p]['expected_hours'] for p in ('aFRRUp','aFRRDown')) else 'calibrated_directional_minimum_valid_sample') if sa is not None else 'not_calibrated_missing_full_month_peers',
            fcr_reference_reported_days=f[0]['reported_days'] if f else None,
            fcr_reference_calendar_hour_coverage=f[0]['calendar_hour_coverage'] if f else None,
            afrr_up_peer_count=counts['aFRRUp'],afrr_down_peer_count=counts['aFRRDown'],
            fcr_demand_min_mw=cv['FCR']['demand_min_mw'],fcr_demand_max_mw=cv['FCR']['demand_max_mw'],
            fcr_cap_min_mw=sf*cv['FCR']['demand_min_mw'] if sf is not None else None,
            fcr_cap_max_mw=sf*cv['FCR']['demand_max_mw'] if sf is not None else None,
            afrr_up_demand_min_mw=cv['aFRRUp']['demand_min_mw'],afrr_up_demand_max_mw=cv['aFRRUp']['demand_max_mw'],
            afrr_down_demand_min_mw=cv['aFRRDown']['demand_min_mw'],afrr_down_demand_max_mw=cv['aFRRDown']['demand_max_mw']))
    # Fill only the proposed research input, retaining observed estimates separately.
    direct={r['month']:r['fcr_market_share_cap'] for r in parameters if r['fcr_market_share_cap'] is not None}
    direct_a={r['month']:r['afrr_market_share_cap'] for r in parameters if r['afrr_market_share_cap'] is not None}
    for r in parameters:
        r['afrr_direct_calibrated_share']=r['afrr_market_share_cap']
        r['afrr_reference_month']=r['month'] if r['afrr_market_share_cap'] is not None else None
        if r['afrr_market_share_cap'] is None and direct_a:
            prior_a=[m for m in direct_a if m<r['month']]
            ref_a=max(prior_a) if prior_a else min(direct_a)
            r['afrr_market_share_cap']=direct_a[ref_a];r['afrr_reference_month']=ref_a
            r['afrr_status']='proxy_previous_valid_month_pending_download' if prior_a else 'proxy_next_valid_month_ex_post_only'
        r['fcr_direct_calibrated_share']=r['fcr_market_share_cap']
        r['fcr_reference_month']=r['month'] if r['fcr_market_share_cap'] is not None else None
        if r['month']<'2025-06':
            r['fcr_market_share_cap']=0.0;r['fcr_status']='disabled_existing_baseline_no_FCR_input_not_estimated_zero_share'
        elif r['fcr_market_share_cap'] is None and direct:
            prior=[m for m in direct if m<r['month']]
            ref=max(prior) if prior else min(direct)
            r['fcr_market_share_cap']=direct[ref];r['fcr_reference_month']=ref
            r['fcr_status']='proxy_previous_valid_month' if prior else 'proxy_next_valid_month_ex_post_only'
    # Existing official tenderStatistics demand fills only the requirement series,
    # never supplier awards. Check overlapping Excel demand independently.
    native=pd.read_csv(REPO/'data/processed/RO/prices_eur_v1_20261002/capacity_native_hourly_eur.csv')
    native=native[native.local_date.between('2025-01-01','2026-08-31')].copy()
    native['utc']=pd.to_datetime(native.delivery_start_utc,utc=True);m['utc']=pd.to_datetime(m.delivery_start_utc,utc=True)
    joined=m.merge(native[['utc','product','demand_mw']],on=['utc','product'],how='left',suffixes=('_excel','_native'),validate='one_to_one')
    matched=joined.demand_mw_native.notna()
    assert (joined.loc[matched,'demand_mw_excel']-joined.loc[matched,'demand_mw_native']).abs().max()<1e-8
    native['month']=native.local_date.str[:7]
    for r in parameters:
        for prod,prefix,coef in [('FCR','fcr',r['fcr_market_share_cap']),('aFRRUp','afrr_up',r['afrr_market_share_cap']),('aFRRDown','afrr_down',r['afrr_market_share_cap'])]:
            vals=native.loc[(native.month==r['month'])&(native['product']==prod),'demand_mw']
            r[prefix+'_demand_min_mw']=float(vals.min()) if len(vals) else None
            r[prefix+'_demand_max_mw']=float(vals.max()) if len(vals) else None
            r[prefix+'_cap_min_mw']=float(vals.min()*coef) if len(vals) and coef is not None else None
            r[prefix+'_cap_max_mw']=float(vals.max()*coef) if len(vals) and coef is not None else None
    for r in parameters:
        for prefix in ('fcr','afrr_up','afrr_down'):
            for bound in ('min','max'):
                value=r[prefix+'_cap_'+bound+'_mw']
                r[prefix+'_cap_'+bound+'_integer_mw']=int(np.floor(value+1e-9)) if value is not None else None
    pending=[v for k,v in inventory.items() if k not in found]
    save('pending_source_downloads.csv',pending)
    save('excel_hours_absent_from_existing_demand_input.csv',joined.loc[~matched].drop(columns='utc').to_dict('records'))
    save('monthly_recommended_share_caps.csv',parameters);save('monthly_supplier_summary.csv',summaries);save('monthly_data_coverage.csv',coverage)
    save('supplier_hourly_shares.csv.gz',hourly);save('supplier_daily_awards.csv',daily);save('market_hourly_demand_and_awards.csv',market)
    save('source_schema_inventory.csv',[dict(date=r['date'],**v) for r in results for v in r['schemas']])
    save('available_daily_offered_quantities.csv',[v for r in results for v in r['offered_daily']])
    save('zero_inference_log.csv',[dict(date=r['date'],**v) for r in results for v in r['inferences']])
    save('cross_report_bid_number_mismatches.csv',[dict(date=r['date'],**v) for r in results for v in r['mismatches']])
    selected=[dict(**r,local_path=str(path.relative_to(REPO))) for key,(path,r) in sorted(found.items())]
    (ROOT/'selected_sources.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2),encoding='utf-8')
    checks=dict(expected_source_files=len(inventory),all_source_files_downloaded=set(found)==set(inventory),overlapping_native_demand_hours_checked=int(matched.sum()),excel_hours_missing_in_existing_input=int((~matched).sum()),files_verified=len(found),days_parsed=len(results),fatal_parse_errors=len(fatal),product_days_reconciled=len(d.groupby(['date','product'])),supplier_days_reconciled=len(d),market_hours=len(m),supplier_hours=len(h),issues=len(issues),months=len(parameters),milp_modified=False,milp_rerun=False)
    (ROOT/'validation_summary.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    print(json.dumps(checks,indent=2),flush=True)
    print(pd.DataFrame(parameters)[['month','fcr_market_share_cap','afrr_market_share_cap','afrr_up_peer_count','afrr_down_peer_count']].to_string(index=False),flush=True)

if __name__=='__main__':run()
