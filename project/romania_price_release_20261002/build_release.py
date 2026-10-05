"""Reparse official raw prices and generate traceable inputs; no optimisation code."""
from pathlib import Path
from datetime import timedelta
from xml.etree import ElementTree as ET
import csv, hashlib, io, json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]; WORK=Path(__file__).resolve().parent
OUT=ROOT/'data/processed/RO/prices_v1_20261002'
PRIOR=ROOT/'countries/RO/full_period_20261001'
RO='Europe/Bucharest'; CET='Europe/Brussels'
START=pd.Timestamp('2025-01-01',tz=RO).tz_convert('UTC')
END=pd.Timestamp('2026-09-01',tz=RO).tz_convert('UTC')
OBSEND=pd.Timestamp('2026-09-02',tz=RO).tz_convert('UTC')
CHECKS=[]; USED={}; EXCLUDED=[]

def check(name,ok,detail=''):
    CHECKS.append(dict(check=name,passed=bool(ok),detail=detail))
    if not ok: raise AssertionError(name+': '+str(detail))
def save(name,df):df.to_csv(OUT/name,index=False,encoding='utf-8-sig')
def dump(name,obj): (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
def stamp(t):return pd.Timestamp(t).isoformat().replace('+00:00','Z')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    sources=pd.read_csv(PRIOR/'source_attempts.csv').fillna('').to_dict('records')
    fresh=json.loads((WORK/'download_results.json').read_text(encoding='utf-8'))
    sources+=fresh
    sources+=json.loads((ROOT/'project/romania_gap_closure_20261001/requests_boundary_fx_id60_results.json').read_text(encoding='utf-8'))
    by_pair={(s['id'],s.get('sha256')):s for s in sources if s.get('raw_file')}
    by_id={s['id']:s for s in sources if s.get('raw_file')}
    def raw(s):
        key=s['id']+'@'+s['sha256'][:12]
        if key not in USED:
            path=ROOT/s['raw_file'];check(key+' SHA256',digest(path)==s['sha256'])
            USED[key]=dict(source_key=key,source_id=s['id'],publisher=s.get('publisher') or ('OPCOM' if s['id'].startswith('DA_') else 'BNR' if s['id'].startswith('BNR') else 'Transelectrica'),
                url=s['url'],raw_file=s['raw_file'],sha256=s['sha256'],retrieved_utc=s.get('retrieved_utc',''),publication_time=s.get('publication_time') or '',revision_time=s.get('revision_time') or '')
        return (ROOT/s['raw_file']).read_text(encoding='utf-8-sig'),key
    def chosen(frame):
        return [by_pair[(r.source_id,r.raw_file_hash)] for r in frame[['source_id','raw_file_hash']].drop_duplicates().itertuples()]
    def interval_rows(s):
        text,key=raw(s);obj=json.loads(text);items=obj['itemList']
        check(key+' pagination',len(items)==obj['pageInfo']['total'])
        check(key+' empty error map',not obj.get('uuAppErrorMap'))
        return items,key

    # DA is reconstructed from published CSV, preserving the native exchange contract.
    old_da=pd.read_csv(PRIOR/'da_native.csv');da=[]
    for s in chosen(old_da)+[by_id['DA_2026-09-01_OBSERVATION']]:
        text,key=raw(s);day=s.get('source_date') or s['id'][3:13];step=60 if day<'2025-10-01' else 15
        a=pd.Timestamp(day,tz=CET).tz_convert('UTC');b=(pd.Timestamp(day)+pd.Timedelta(days=1)).tz_localize(CET).tz_convert('UTC')
        rows=[r for r in csv.reader(io.StringIO(text)) if r and r[0]=='Romania']
        check(key+' DA interval sequence',[int(r[1]) for r in rows]==list(range(1,int((b-a).total_seconds()/(step*60))+1)))
        for r in rows:
            t=a+pd.Timedelta(minutes=step*(int(r[1])-1));z=t+pd.Timedelta(minutes=step)
            if not (START<=t<OBSEND):continue
            da.append(dict(delivery_start_utc=stamp(t),delivery_end_utc=stamp(z),source_market_date=day,native_interval=int(r[1]),native_contract_id=day+'_'+r[1],native_resolution_minutes=step,da_price_eur_per_mwh=float(r[2]),source_price=r[2],source_key=key))
    da=pd.DataFrame(da).sort_values('delivery_start_utc')
    check('DA unique contracts',not da.native_contract_id.duplicated().any())
    check('DA all finite',np.isfinite(da.da_price_eur_per_mwh).all())
    save('da_native_contracts.csv',da)
    dq=[]
    for r in da.to_dict('records'):
        for t in pd.date_range(r['delivery_start_utc'],r['delivery_end_utc'],freq='15min',inclusive='left'):
            dq.append(dict(t=t,da_price_eur_per_mwh=r['da_price_eur_per_mwh'],da_contract_id=r['native_contract_id'],da_native_resolution_minutes=r['native_resolution_minutes'],da_source_key=r['source_key']))
    dq=pd.DataFrame(dq).set_index('t');check('DA unique mapped QH',not dq.index.duplicated().any())

    # Capacities use averageAcceptedPrice, preserving tender price / offered mean as diagnostics.
    old_cap=pd.read_csv(PRIOR/'capacity_statistics.csv');caps=[]
    for s in chosen(old_cap)+[by_id['tenderStatistics_2026-09-01_OBSERVATION']]:
        items,key=interval_rows(s)
        ra=pd.Timestamp(s['requested_start_utc']);rb=pd.Timestamp(s['requested_end_utc'])
        for tender in items:
            ta=pd.Timestamp(tender['timeInterval']['from']);tb=pd.Timestamp(tender['timeInterval']['to'])
            if not ra<=ta<rb:continue
            for service in tender['tenderServiceList']:
                prod=service['serviceCode']
                if prod not in ['FCR','aFRRUp','aFRRDown']:continue
                for r in service['tenderStatistics']['timeIntervalList']:
                    t=pd.Timestamp(r['timeInterval']['from']);z=pd.Timestamp(r['timeInterval']['to'])
                    if not ta<=t<z<=tb:
                        EXCLUDED.append(dict(source_key=key,product=prod,tender_code=tender['tenderCode'],start_utc=stamp(t),end_utc=stamp(z),reason='OUTSIDE_PUBLISHED_TENDER_INTERVAL'));continue
                    if not START<=t<OBSEND:continue
                    check(key+' capacity 1 hour '+stamp(t),(z-t).total_seconds()==3600)
                    caps.append(dict(delivery_start_utc=stamp(t),delivery_end_utc=stamp(z),product=prod,tender_code=tender['tenderCode'],capacity_order_id=prod+'_'+stamp(t),price_scheme=tender.get('priceScheme'),
                        average_accepted_price_ron_per_mw_h_candidate=r.get('averageAcceptedPrice'),average_offered_price_raw=r.get('averageOfferedPrice'),tender_price_raw=r.get('tenderPrice'),demand_mw=r.get('tenderDemand'),satisfied_ratio=r.get('tenderSatisfiedDemand'),source_key=key))
    cap=pd.DataFrame(caps).sort_values(['delivery_start_utc','product'])
    check('capacity unique product UTC',not cap.duplicated(['delivery_start_utc','product']).any())
    cap['accepted_capacity_mw']=cap.demand_mw*cap.satisfied_ratio
    save('capacity_native_hourly.csv',cap)
    save('source_rows_excluded.csv',pd.DataFrame(EXCLUDED,columns=['source_key','product','tender_code','start_utc','end_utc','reason']))

    def qhseries(ss,kind):
        rows=[]
        for s in ss:
            items,key=interval_rows(s);ts=[]
            for r in items:
                t=pd.Timestamp(r['timeInterval']['from']);z=pd.Timestamp(r['timeInterval']['to']);ts.append(t)
                check(key+' 15min '+stamp(t),(z-t).total_seconds()==900)
                rows.append(dict(delivery_start_utc=stamp(t),delivery_end_utc=stamp(z),fcr_raw=r.get('fcr'),afrr_up_raw=r.get('aFRR_Up'),afrr_down_raw=r.get('aFRR_Down'),source_key=key))
            expected=pd.date_range(s['requested_start_utc'],s['requested_end_utc'],freq='15min',inclusive='left')
            check(key+' exact UTC grid',pd.DatetimeIndex(ts).equals(expected))
        df=pd.DataFrame(rows).sort_values('delivery_start_utc')
        check(kind+' unique QH',not df.delivery_start_utc.duplicated().any())
        save(kind+'_native_qh.csv',df)
        df.index=pd.to_datetime(df.delivery_start_utc,utc=True)
        return df
    activation=qhseries([s for s in fresh if s.get('report')=='marginalPricesOverview'],'activation_price')
    old_energy=pd.read_csv(PRIOR/'activatedBalancingEnergyOverview.csv')
    energy=qhseries(chosen(old_energy)+[by_id['activatedBalancingEnergyOverview_2026-09-01_OBSERVATION']],'system_activation_energy')

    # FX: source dates, not assumed publication timestamps. Strictly prior date by approved A07.
    fx=[]
    for id in ['BNR2024_BOUNDARY','BNR_FX_2025','BNR_FX_2026']:
        text,key=raw(by_id[id]);tree=ET.fromstring(text)
        for cube in tree.iter():
            if cube.tag.split('}')[-1]!='Cube' or 'date' not in cube.attrib:continue
            for rate in cube:
                if rate.attrib.get('currency')=='EUR':fx.append(dict(fixing_date=cube.attrib['date'],ron_per_eur=float(rate.text),source_key=key))
    fx=pd.DataFrame(fx).sort_values('fixing_date');check('FX unique dates',not fx.fixing_date.duplicated().any());check('FX positive',fx.ron_per_eur.gt(0).all())
    save('fx_native_reference_rates.csv',fx)
    index=pd.date_range(START,OBSEND,freq='15min',inclusive='left')
    g=pd.DataFrame(index=index);g.index.name='t'
    g['delivery_start_utc']=[stamp(t) for t in index];g['delivery_end_utc']=[stamp(t+pd.Timedelta(minutes=15)) for t in index]
    g['local_time']=[t.tz_convert(RO).isoformat() for t in index];g['local_date']=[t.tz_convert(RO).strftime('%Y-%m-%d') for t in index]
    g['duration_hours']=.25;g['period_role']=np.where(index<END,'FORMAL','LOOKAHEAD_ONLY')
    g['capacity_hour_start_utc']=[stamp(t.floor('h')) for t in index]
    g=g.join(dq)
    fdays=fx.fixing_date.to_numpy(); positions=np.searchsorted(fdays,g.local_date.to_numpy(),side='left')-1
    check('FX earlier fixing exists',(positions>=0).all())
    ff=fx.iloc[positions];g['fx_fixing_date']=ff.fixing_date.to_numpy();g['fx_ron_per_eur']=ff.ron_per_eur.to_numpy();g['fx_source_key']=ff.source_key.to_numpy()
    check('FX strictly prior local date',(g.fx_fixing_date<g.local_date).all())
    for prod,prefix in [('FCR','fcr'),('aFRRUp','afrr_up'),('aFRRDown','afrr_down')]:
        c=cap[cap['product']==prod].set_index('delivery_start_utc')
        for out,col in [('capacity_price_ron_per_mw_h_candidate','average_accepted_price_ron_per_mw_h_candidate'),('accepted_capacity_mw','accepted_capacity_mw'),('capacity_order_id','capacity_order_id'),('capacity_source_key','source_key')]:
            g[prefix+'_'+out]=g.capacity_hour_start_utc.map(c[col])
        p=g[prefix+'_capacity_price_ron_per_mw_h_candidate']
        g[prefix+'_capacity_price_eur_per_mw_h_proxy']=p/g.fx_ron_per_eur
        g[prefix+'_capacity_status']=np.where(p.notna(),'PUBLISHED_PROXY',np.where(g[prefix+'_capacity_source_key'].notna(),'SOURCE_PRICE_NULL','MISSING_SOURCE_HOUR'))
        if prod=='FCR':g.loc[g.local_date<'2025-06-01',prefix+'_capacity_status']='OUT_OF_RESEARCH_COVERAGE_PRE_2025_06'
    for prefix,col in [('fcr','fcr_raw'),('afrr_up','afrr_up_raw'),('afrr_down','afrr_down_raw')]:
        g[prefix+'_activation_price_ron_per_mwh_candidate']=activation[col]
        g[prefix+'_activation_price_eur_per_mwh_proxy']=activation[col]/g.fx_ron_per_eur
        g[prefix+'_activation_price_status']=np.where(activation[col].notna(),'PUBLISHED_PROXY','SOURCE_NULL')
        g[prefix+'_system_activation_energy_mwh']=energy[col]
    g['activation_price_source_key']=activation.source_key;g['activation_energy_source_key']=energy.source_key
    check('FCR independent activation not numeric',g.fcr_activation_price_ron_per_mwh_candidate.isna().all())
    g['fcr_activation_price_status']='SOURCE_NULL_NOT_MODELED'
    g['da_price_status']=np.where(g.da_price_eur_per_mwh.notna(),'PUBLISHED_NATIVE','MISSING_SOURCE')

    # M10-M11 data gates, independent of site size/eligibility, p and frozen commitments.
    for d in ['up','down']:
        g['alpha_'+d+'_raw']=g['afrr_'+d+'_system_activation_energy_mwh']/(g['afrr_'+d+'_accepted_capacity_mw']*.25)
    g['alpha_sum_raw']=g.alpha_up_raw+g.alpha_down_raw
    g['alpha_computable']=np.isfinite(g.alpha_up_raw)&np.isfinite(g.alpha_down_raw)&g.afrr_up_accepted_capacity_mw.gt(0)&g.afrr_down_accepted_capacity_mw.gt(0)
    g['alpha_strict_valid']=g.alpha_computable&g.alpha_up_raw.ge(0)&g.alpha_down_raw.ge(0)&g.alpha_sum_raw.le(1)
    g['afrr_price_inputs_valid']=g[['afrr_up_capacity_price_eur_per_mw_h_proxy','afrr_down_capacity_price_eur_per_mw_h_proxy','afrr_up_activation_price_eur_per_mwh_proxy','afrr_down_activation_price_eur_per_mwh_proxy']].notna().all(axis=1)
    g['afrr_qh_data_valid']=g.alpha_strict_valid&g.afrr_price_inputs_valid
    g['afrr_hour_data_valid']=g.groupby('capacity_hour_start_utc').afrr_qh_data_valid.transform('all')
    g['fcr_qh_data_valid']=g.local_date.ge('2025-06-01')&g.fcr_capacity_price_eur_per_mw_h_proxy.notna()&g.fcr_accepted_capacity_mw.gt(0)
    g['fcr_hour_data_valid']=g.groupby('capacity_hour_start_utc').fcr_qh_data_valid.transform('all')
    g['da_contract_data_valid']=g.groupby('da_contract_id').da_price_eur_per_mwh.transform(lambda x:x.notna().all())
    g['afrr_qh_failure_reason']=[';'.join(name for name,fail in [('ALPHA_UNCOMPUTABLE',not r.alpha_computable),('ALPHA_OUTSIDE_SIMPLEX',r.alpha_computable and not r.alpha_strict_valid),('REQUIRED_PRICE_MISSING',not r.afrr_price_inputs_valid)] if fail) or 'OK' for r in g.itertuples()]
    g['afrr_order_gate_reason']=np.where(g.afrr_hour_data_valid,'OK',np.where(g.afrr_qh_data_valid,'OTHER_QH_IN_SAME_HOUR_INVALID',g.afrr_qh_failure_reason))
    check('all numeric values finite or null',all(np.isfinite(g[c].dropna()).all() for c in g.select_dtypes(include='number').columns))
    formal=g[g.period_role=='FORMAL'];obs=g[g.period_role=='LOOKAHEAD_ONLY']
    check('formal 58364 QH',len(formal)==58364);check('observation 96 QH',len(obs)==96)
    check('DA full period no gaps',g.da_price_eur_per_mwh.notna().all())
    check('hour mapping four QH',g.groupby('capacity_hour_start_utc').size().eq(4).all())
    save('prices_qh_formal_20250101_20260831.csv',formal)
    save('prices_qh_observation_20260901.csv',obs)
    save('afrr_disabled_hour_details.csv',formal[~formal.afrr_hour_data_valid][['delivery_start_utc','local_time','capacity_hour_start_utc','alpha_up_raw','alpha_down_raw','alpha_sum_raw','afrr_qh_failure_reason','afrr_order_gate_reason']])
    prices=['da_price_eur_per_mwh','fcr_capacity_price_ron_per_mw_h_candidate','afrr_up_capacity_price_ron_per_mw_h_candidate','afrr_down_capacity_price_ron_per_mw_h_candidate','afrr_up_activation_price_ron_per_mwh_candidate','afrr_down_activation_price_ron_per_mwh_candidate','fcr_activation_price_ron_per_mwh_candidate']
    coverage=[];gaps=[]
    for month,group in formal.groupby(formal.local_date.str[:7]):
        for col in prices:
            p=group[col];applicable=group.local_date.ge('2025-06-01') if col.startswith('fcr_capacity') else pd.Series(True,index=group.index)
            if col.startswith('fcr_activation'):applicable[:]=False
            coverage.append(dict(month=month,series=col,expected_qh=len(group),in_scope_qh=int(applicable.sum()),numeric_qh=int(p.notna().sum()),in_scope_missing_qh=int((p.isna()&applicable).sum()),outside_scope_qh=int((~applicable).sum()),zeros=int(p.eq(0).sum()),negative=int(p.lt(0).sum()),minimum=p.min(),maximum=p.max()))
            missing=p.isna()&applicable
            for t in group.index[missing]:
                prefix=col.split('_capacity')[0] if 'capacity' in col else None
                gaps.append(dict(series=col,delivery_start_utc=stamp(t),local_time=group.loc[t,'local_time'],reason=group.loc[t,prefix+'_capacity_status'] if prefix else 'SOURCE_NULL'))
    save('coverage_monthly.csv',pd.DataFrame(coverage));save('price_missing_in_scope.csv',pd.DataFrame(gaps,columns=['series','delivery_start_utc','local_time','reason']))

    # Compare reparsed snapshots with previous audited tables, and recheck DST source.
    previous_checks=[]
    for label,old,new,keys,columns in [('DA',old_da,da,['native_contract_id'],[('price_eur_mwh','da_price_eur_per_mwh')]),('capacity',old_cap,cap,['product','delivery_start_utc'],[('average_accepted_price_LEI_denominator_unknown','average_accepted_price_ron_per_mw_h_candidate'),('demand_mw','demand_mw'),('satisfied_ratio','satisfied_ratio')])]:
        old=old.copy();new=new.copy()
        if 'delivery_start_utc' in keys:
            for f in [old,new]:f['delivery_start_utc']=pd.to_datetime(f.delivery_start_utc,utc=True).map(stamp)
        joined=old.merge(new,on=keys,suffixes=('_old','_new'),validate='one_to_one')
        for a,b in columns:
            aa=a+'_old' if a in new.columns else a;bb=b+'_new' if b in old.columns else b
            equal=np.isclose(joined[aa],joined[bb],equal_nan=True)
            check(label+' original derived comparison '+a,equal.all())
            previous_checks.append(dict(dataset=label,field=a,compared_rows=len(joined),differences=int((~equal).sum())))
    old_energy.index=pd.to_datetime(old_energy.delivery_start_utc,utc=True)
    for a,b in [('aFRR_Up','afrr_up_raw'),('aFRR_Down','afrr_down_raw')]:
        check('energy prior '+a,np.allclose(old_energy[a],energy.loc[old_energy.index,b],equal_nan=True))
    save('prior_snapshot_comparison.csv',pd.DataFrame(previous_checks))
    dst=[]
    for code in ['469_2025','470_2025','158_2025']:
        text,key=raw(by_id['GAP_'+code+'_RECHECK']);dt=json.loads(text)
        for service in dt['tenderServiceList']:
            if service['serviceCode'] not in ['FCR','aFRRUp','aFRRDown']:continue
            rr=service['tenderStatistics']['timeIntervalList'];starts=[r['timeInterval']['from'] for r in rr]
            dst.append(dict(tender_code=code,product=service['serviceCode'],source_key=key,published_hours=len(rr),numeric_price_hours=sum(r.get('averageAcceptedPrice') is not None for r in rr),last_end=rr[-1]['timeInterval']['to'],dst_missing_hour_still_absent=not any(pd.Timestamp(x)==pd.Timestamp('2025-10-26T21:00:00Z') for x in starts) if code!='158_2025' else None))
    dump('dst_gap_recheck.json',dst)
    for s in fresh:
        if s.get('scope')=='metadata':raw(s)
    save('source_registry.csv',pd.DataFrame(USED.values()))
    summary=dict(formal_start_local='2025-01-01T00:00:00+02:00',formal_end_exclusive_local='2026-09-01T00:00:00+03:00',formal_qh=len(formal),formal_days=formal.local_date.nunique(),observation_qh=len(obs),raw_sources=len(USED),
        numeric_qh={c:int(formal[c].notna().sum()) for c in prices},alpha_uncomputable_qh=int((~formal.alpha_computable).sum()),alpha_exceeds_one_qh=int((formal.alpha_computable&formal.alpha_sum_raw.gt(1)).sum()),
        afrr_price_missing_qh=int((~formal.afrr_price_inputs_valid).sum()),afrr_raw_invalid_qh=int((~formal.afrr_qh_data_valid).sum()),afrr_disabled_qh=int((~formal.afrr_hour_data_valid).sum()),afrr_disabled_hours=int(formal.loc[~formal.afrr_hour_data_valid,'capacity_hour_start_utc'].nunique()),
        afrr_enabled_hours=int(formal.loc[formal.afrr_hour_data_valid,'capacity_hour_start_utc'].nunique()),fcr_enabled_hours=int(formal.loc[formal.fcr_hour_data_valid,'capacity_hour_start_utc'].nunique()),
        observation_afrr_enabled_hours=int(obs.loc[obs.afrr_hour_data_valid,'capacity_hour_start_utc'].nunique()),observation_numeric_qh={c:int(obs[c].notna().sum()) for c in prices},exclusions=len(EXCLUDED),checks_passed=len(CHECKS))
    dump('summary.json',summary);dump('validation_checks.json',CHECKS)
    files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='release_manifest.json']
    dump('release_manifest.json',dict(version='RO prices v1 / 20261002',inputs='source_registry.csv',files=files))
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
