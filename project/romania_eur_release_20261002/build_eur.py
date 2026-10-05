"""EUR-only market price export, with explicit Bucharest delivery-day FX mapping."""
from pathlib import Path
from xml.etree import ElementTree as ET
from decimal import Decimal
import hashlib, json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]; WORK=Path(__file__).resolve().parent
SRC=ROOT/'data/processed/RO/prices_v1_20261002'
OUT=ROOT/'data/processed/RO/prices_eur_v1_20261002'
CHECKS=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(name,ok,detail=''):
    CHECKS.append(dict(check=name,passed=bool(ok),detail=detail))
    if not ok:raise AssertionError(name+': '+str(detail))
def save(name,df):df.to_csv(OUT/name,index=False,encoding='utf-8-sig')
def dump(name,data): (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding='utf-8')

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    before={p.name:sha(p) for p in SRC.iterdir() if p.is_file()}
    manifest=json.loads((SRC/'release_manifest.json').read_text())
    for f in manifest['files']:check('source release hash '+f['path'],sha(ROOT/f['path'])==f['sha256'])
    registry=pd.read_csv(SRC/'source_registry.csv').fillna('')
    fx=[]
    for row in registry[registry.publisher.eq('BNR')].itertuples():
        p=ROOT/row.raw_file;check('BNR raw SHA '+row.source_key,sha(p)==row.sha256)
        for cube in ET.fromstring(p.read_bytes()).iter():
            if cube.tag.split('}')[-1]!='Cube' or 'date' not in cube.attrib:continue
            for rate in cube:
                if rate.attrib.get('currency')=='EUR':
                    check('BNR EUR multiplier '+cube.attrib['date'],int(rate.attrib.get('multiplier','1'))==1)
                    fx.append(dict(fx_fixing_date=cube.attrib['date'],fx_ron_per_eur=float(rate.text),fx_source_key=row.source_key,fx_decimal=rate.text))
    fx=pd.DataFrame(fx).sort_values('fx_fixing_date')
    check('BNR dates unique',not fx.fx_fixing_date.duplicated().any());check('BNR rate positive',fx.fx_ron_per_eur.gt(0).all())
    days=pd.date_range('2025-01-01','2026-09-01',freq='D').strftime('%Y-%m-%d')
    pos=np.searchsorted(fx.fx_fixing_date.to_numpy(),days,side='left')-1
    check('prior fixing available all 609 days',(pos>=0).all())
    daily=fx.iloc[pos].reset_index(drop=True);daily.insert(0,'delivery_date_bucharest',days)
    daily['period_role']=np.where(daily.delivery_date_bucharest<'2026-09-01','FORMAL','LOOKAHEAD_ONLY')
    daily['fx_age_calendar_days']=(pd.to_datetime(daily.delivery_date_bucharest)-pd.to_datetime(daily.fx_fixing_date)).dt.days
    daily['fx_policy']='LATEST_BNR_REFERENCE_DATE_STRICTLY_BEFORE_BUCHAREST_DELIVERY_DATE'
    check('fixing strictly before delivery day',(daily.fx_fixing_date<daily.delivery_date_bucharest).all())
    save('fx_by_bucharest_delivery_day.csv',daily.drop(columns='fx_decimal'))
    daymap=daily.set_index('delivery_date_bucharest')
    def localfx(df):
        t=pd.to_datetime(df.delivery_start_utc,utc=True)
        day=t.dt.tz_convert('Europe/Bucharest').dt.strftime('%Y-%m-%d')
        df=df.copy();df['local_date']=day
        for c in ['fx_fixing_date','fx_ron_per_eur','fx_source_key']:df[c]=day.map(daymap[c])
        check('all rows FX matched '+str(len(df)),df.fx_ron_per_eur.notna().all())
        return df
    summaries=[];allg=[]
    for oldname,newname,expected in [('prices_qh_formal_20250101_20260831.csv','prices_eur_qh_20250101_20260831.csv',58364),('prices_qh_observation_20260901.csv','prices_eur_observation_20260901.csv',96)]:
        old=pd.read_csv(SRC/oldname);g=localfx(old)
        check(newname+' unchanged local day',g.local_date.equals(old.local_date))
        for c in ['fx_fixing_date','fx_source_key']:check(newname+' prior mapping '+c,g[c].equals(old[c]))
        check(newname+' prior FX values',np.array_equal(g.fx_ron_per_eur,old.fx_ron_per_eur))
        mappings=[(c,c.replace('_ron_','_eur_').replace('_candidate','_proxy')) for c in old if '_price_ron_' in c]
        for src,dst in mappings:
            g[dst]=old[src]/g.fx_ron_per_eur
            check(newname+' prior EUR '+dst,np.allclose(g[dst],old[dst],rtol=1e-13,atol=1e-12,equal_nan=True))
            check(newname+' null preservation '+dst,g[dst].isna().equals(old[src].isna()))
            valid=old[src].notna()
            check(newname+' sign preservation '+dst,np.array_equal(np.sign(g.loc[valid,dst]),np.sign(old.loc[valid,src])))
            check(newname+' reverse FX '+dst,np.allclose(g.loc[valid,dst]*g.loc[valid,'fx_ron_per_eur'],old.loc[valid,src],rtol=1e-13,atol=1e-9))
            # Independent decimal calculation from the original BNR XML string.
            rates=g.local_date.map(daymap.fx_decimal)
            error=max((abs(Decimal(str(v))/Decimal(r)-Decimal(str(z))) for v,r,z in zip(old.loc[valid,src],rates[valid],g.loc[valid,dst])),default=Decimal(0))
            check(newname+' Decimal cross-check '+dst,error<Decimal('1e-8'),str(error))
        g=g.drop(columns=[c for c in g if '_price_ron_' in c]);g['price_currency']='EUR'
        check(newname+' no RON monetary price',not any('_price_ron_' in c for c in g))
        check(newname+' DA untouched',np.array_equal(g.da_price_eur_per_mwh,old.da_price_eur_per_mwh))
        unchanged=[c for c in old if not ('_price_ron_' in c or '_price_eur_' in c or c.startswith('fx_') or c=='local_date')]
        check(newname+' all physical flags source fields unchanged',g[unchanged].equals(old[unchanged]))
        check(newname+' row count',len(g)==expected);check(newname+' unique UTC',not g.delivery_start_utc.duplicated().any())
        save(newname,g);allg.append(g)
        for c in g:
            if '_price_eur_' in c:
                s=g[c];summaries.append(dict(file=newname,field=c,currency='EUR',unit='EUR/(MW*h)' if '_capacity_' in c else 'EUR/MWh',rows=len(g),numeric=int(s.notna().sum()),missing=int(s.isna().sum()),zero=int(s.eq(0).sum()),negative=int(s.lt(0).sum()),minimum=s.min(),maximum=s.max()))
    joined=pd.concat(allg,ignore_index=True)
    expected=pd.date_range('2024-12-31T22:00:00Z','2026-09-01T21:00:00Z',freq='15min',inclusive='left')
    check('formal plus observation contiguous UTC',pd.DatetimeIndex(pd.to_datetime(joined.delivery_start_utc,utc=True)).equals(expected))
    for d,n in [('2025-03-30',92),('2025-10-26',100),('2026-03-29',92)]:check('DST '+d,int(joined.local_date.eq(d).sum())==n)

    # Preserve original contract resolution while exporting only EUR prices.
    da=pd.read_csv(SRC/'da_native_contracts.csv').drop(columns='source_price')
    da['price_currency']='EUR';save('da_native_eur.csv',da)
    cap=localfx(pd.read_csv(SRC/'capacity_native_hourly.csv'))
    capcols={'average_accepted_price_ron_per_mw_h_candidate':'average_accepted_price_eur_per_mw_h_proxy','average_offered_price_raw':'average_offered_price_eur_per_mw_h_proxy','tender_price_raw':'tender_price_eur_per_mw_h_proxy'}
    for src,dst in capcols.items():cap[dst]=cap[src]/cap.fx_ron_per_eur
    cap=cap.drop(columns=list(capcols));cap['price_currency']='EUR'
    cap['unit_status']='CAPACITY_DENOMINATOR_MODEL_ASSUMPTION'
    save('capacity_native_hourly_eur.csv',cap)
    act=localfx(pd.read_csv(SRC/'activation_price_native_qh.csv'))
    for prefix in ['fcr','afrr_up','afrr_down']:act[prefix+'_activation_price_eur_per_mwh_proxy']=act[prefix+'_raw']/act.fx_ron_per_eur
    act=act.drop(columns=['fcr_raw','afrr_up_raw','afrr_down_raw']);act['price_currency']='EUR';act['unit_status']='API_ENERGY_PRICE_DENOMINATOR_MODEL_ASSUMPTION'
    save('activation_native_qh_eur.csv',act)
    # Match native EUR to the main grid without changing the capacity time factor.
    for product,prefix in [('FCR','fcr'),('aFRRUp','afrr_up'),('aFRRDown','afrr_down')]:
        indexed=cap[cap['product']==product].set_index('delivery_start_utc')
        got=joined.capacity_hour_start_utc.map(indexed.average_accepted_price_eur_per_mw_h_proxy)
        check('native capacity EUR equals QH '+product,np.allclose(got,joined[prefix+'_capacity_price_eur_per_mw_h_proxy'],equal_nan=True))
    check('activation native EUR equals QH',all(np.allclose(act[p+'_activation_price_eur_per_mwh_proxy'],joined[p+'_activation_price_eur_per_mwh_proxy'],equal_nan=True) for p in ['fcr','afrr_up','afrr_down']))
    save('currency_conversion_summary.csv',pd.DataFrame(summaries))
    save('source_registry.csv',registry)
    coverage=pd.read_csv(SRC/'coverage_monthly.csv')
    coverage.series=coverage.series.str.replace('_ron_','_eur_',regex=False).str.replace('_candidate','_proxy',regex=False)
    # Recompute min/max from converted series, never convert an aggregate with one FX value.
    formal=allg[0]
    for i,r in coverage.iterrows():
        values=formal.loc[formal.local_date.str.startswith(r['month']),r.series]
        coverage.loc[i,'minimum']=values.min();coverage.loc[i,'maximum']=values.max()
    save('coverage_monthly_eur.csv',coverage)
    gaps=pd.read_csv(SRC/'price_missing_in_scope.csv');gaps.series=gaps.series.str.replace('_ron_','_eur_',regex=False).str.replace('_candidate','_proxy',regex=False)
    save('price_missing_in_scope_eur.csv',gaps)
    check('source release immutable',before=={p.name:sha(p) for p in SRC.iterdir() if p.is_file()})
    dump('validation.json',dict(check_count=len(CHECKS),failed=sum(not c['passed'] for c in CHECKS),checks=CHECKS))
    dump('build_summary.json',dict(formal_qh=58364,observation_qh=96,delivery_days=len(daily),currency='EUR',fx_policy=daily.fx_policy.iloc[0],first_delivery_day=daily.iloc[0].to_dict(),last_delivery_day=daily.iloc[-1].to_dict(),source_version=SRC.relative_to(ROOT).as_posix(),source_manifest_sha256=sha(SRC/'release_manifest.json'),validation='PASS',independent_agent_review='NOT_REQUESTED_FOR_THIS_CONVERSION',unit_finality='API_DENOMINATORS_REMAIN_MODEL_ASSUMPTIONS'))
    dump('manifest.json',dict(version='RO EUR prices v1 20261002',files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='manifest.json']))
    print(json.dumps(dict(output=str(OUT),checks=len(CHECKS),formal_qh=58364,observation_qh=96,days=len(daily)),ensure_ascii=False))

if __name__=='__main__':main()
