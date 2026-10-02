"""Read-only market research and immutable public-source collection; not a model adapter."""
from pathlib import Path
import importlib.util, json, sys
from urllib.parse import urlencode
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent
RAW=ROOT/'data/raw/RO/afrr_deepresearch/20261002'
BASE='https://newmarkets.transelectrica.ro/usy-durom-publicreportg01/00121002500000000000000000000100/publicReport/'
def dump(name,obj):
    (WORK/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
def save(name,frame): frame.to_csv(WORK/name,index=False,encoding='utf-8-sig')
def collector():
    spec=importlib.util.spec_from_file_location('prior_collector',ROOT/'project/romania_gap_closure_20261001/collect_public.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);mod.RAW=RAW
    return mod.collect
def collect_batch(reqs,filename):
    from concurrent.futures import ThreadPoolExecutor
    dump(filename+'.json',reqs)
    with ThreadPoolExecutor(max_workers=3) as pool: results=list(pool.map(collector(),reqs))
    dump(filename+'_results.json',results)
    print(json.dumps([{'id':r['id'],'status':r['status'],'bytes':r.get('bytes'),'error':r.get('error')} for r in results]),flush=True)
    return results
def initial():
    qs=urlencode({'timeInterval.from':'2025-07-31T21:00:00Z','timeInterval.to':'2025-08-31T21:00:00Z','pageInfo.pageSize':3000,'pageInfo.pageIndex':0})
    reqs=[{'id':route+'_2025-08','url':BASE+route+'?'+qs,'scope':'2025-08 Europe/Bucharest; expected 2976 PT15M rows'} for route in ['marginalPricesOverview','activatedBalancingEnergyOverview']]
    reqs += [{'id':r+'_metadata','url':BASE+'metadata/get?reportCode='+r} for r in ['marginalPricesOverview','activatedBalancingEnergyOverview','tenderStatistics']]
    reqs += [{'id':'DAMAS_PUBLIC_HOME','url':'https://newmarkets.transelectrica.ro/'},{'id':'TSO_STS_INFO','url':'https://www.transelectrica.ro/web/tel/295'},{'id':'TSO_BIDDING_GUIDE','url':'https://www.transelectrica.ro/web/tel/despre-noi1'},{'id':'RO_REG_127','url':'https://legislatie.just.ro/Public/DetaliiDocumentAfis/282874'}]
    collect_batch(reqs,'requests_initial')
def diagnose():
    src=ROOT/'countries/RO/full_period_20261001'
    c=pd.read_csv(src/'capacity_statistics.csv'); a=pd.read_csv(src/'activatedBalancingEnergyOverview.csv')
    a['t']=pd.to_datetime(a.delivery_start_utc,utc=True); a['hour']=a.t.dt.floor('h')
    for prod,direction in [('aFRRUp','up'),('aFRRDown','down')]:
        g=c[c['product']==prod].copy();g['hour']=pd.to_datetime(g.delivery_start_utc,utc=True)
        cols=['hour','demand_mw','satisfied_ratio','source_id','raw_file_hash','tender_code']
        g['capacity_mw']=g.demand_mw*g.satisfied_ratio;cols+=['capacity_mw']
        a=a.merge(g[cols].rename(columns={k:direction+'_'+k for k in cols if k!='hour'}),on='hour',how='left',validate='many_to_one')
        a['energy_'+direction+'_mwh']=pd.to_numeric(a['aFRR_'+('Up' if direction=='up' else 'Down')],errors='coerce')
        a['alpha_'+direction]=a['energy_'+direction+'_mwh']/(a[direction+'_capacity_mw']*.25)
    valid=a.alpha_up.notna()&a.alpha_down.notna()&(a.up_capacity_mw>0)&(a.down_capacity_mw>0)&np.isfinite(a.alpha_up)&np.isfinite(a.alpha_down)
    a['computable']=valid;a['alpha_sum']=a.alpha_up+a.alpha_down
    a['exceeds_one']=valid&(a.alpha_sum>1+1e-9)
    a['excess_fraction']=a.alpha_sum-1;a['equivalent_active_minutes']=15*a.alpha_sum;a['excess_minutes']=15*a.excess_fraction
    a['up_exceeds_one']=valid&(a.alpha_up>1+1e-9);a['down_exceeds_one']=valid&(a.alpha_down>1+1e-9)
    a['month']=a.local_time.str[:7]
    a['missing_reason']=a.apply(lambda r:';'.join(k for k,v in {'UP_ENERGY_NULL':pd.isna(r.energy_up_mwh),'DOWN_ENERGY_NULL':pd.isna(r.energy_down_mwh),'UP_CAPACITY_NULL':pd.isna(r.up_capacity_mw),'DOWN_CAPACITY_NULL':pd.isna(r.down_capacity_mw),'UP_CAPACITY_NONPOSITIVE':r.up_capacity_mw<=0,'DOWN_CAPACITY_NONPOSITIVE':r.down_capacity_mw<=0}.items() if v),axis=1)
    save('activation_diagnostic_all.csv',a.drop(columns=['t','hour']))
    save('activation_uncomputable_50.csv',a[~valid].drop(columns=['t','hour']))
    save('activation_exceeds_one.csv',a[a.exceeds_one].sort_values('alpha_sum',ascending=False).drop(columns=['t','hour']))
    monthly=[]
    for month,g in a.groupby('month'):
        v=g[g.computable];e=v[v.exceeds_one]
        monthly.append({'month':month,'total_qh':len(g),'computable_qh':len(v),'uncomputable_qh':len(g)-len(v),'exceed_qh':len(e),'exceed_pct_computable':100*len(e)/len(v),'max_sum':v.alpha_sum.max(),'mean_excess_exceed':e.excess_fraction.mean(),'up_only_over_one':int((e.up_exceeds_one&~e.down_exceeds_one).sum()),'down_only_over_one':int((~e.up_exceeds_one&e.down_exceeds_one).sum()),'both_individually_at_most_one':int((~e.up_exceeds_one&~e.down_exceeds_one).sum())})
    save('activation_diagnostic_monthly.csv',pd.DataFrame(monthly))
    bad=a[a.exceeds_one]
    bins=[0,.01,.05,.1,.25,.5,1,float('inf')]
    hist=pd.cut(bad.excess_fraction,bins=bins,right=True).value_counts(sort=False)
    summ={'total_qh':len(a),'computable_qh':int(valid.sum()),'uncomputable_qh':int((~valid).sum()),'uncomputable_pct_total':100*(~valid).mean(),'missing_reason_counts':a[~valid].missing_reason.value_counts().to_dict(),'exceed_qh':len(bad),'exceed_pct_computable':100*len(bad)/valid.sum(),'exceed_pct_total':100*len(bad)/len(a),'up_individually_over_one':int(bad.up_exceeds_one.sum()),'down_individually_over_one':int(bad.down_exceeds_one.sum()),'both_individually_at_most_one':int((~bad.up_exceeds_one&~bad.down_exceeds_one).sum()),'alpha_sum_quantiles_exceed':bad.alpha_sum.quantile([0,.25,.5,.75,.9,.95,.99,1]).to_dict(),'excess_fraction_mean':bad.excess_fraction.mean(),'excess_fraction_bins':{str(k):int(v) for k,v in hist.items()},'negative_energy':int(((a.energy_up_mwh<0)|(a.energy_down_mwh<0)).sum()),'duplicate_utc':int(a.delivery_start_utc.duplicated().sum()),'max_examples':bad.nlargest(5,'alpha_sum')[['delivery_start_utc','local_time','energy_up_mwh','energy_down_mwh','up_capacity_mw','down_capacity_mw','alpha_up','alpha_down','alpha_sum']].to_dict('records')}
    dump('activation_diagnostic_summary.json',summ);print(json.dumps(summ,ensure_ascii=False,default=str),flush=True)

def analyze_new():
    import hashlib, io, openpyxl
    checks=[]
    def check(name,ok,detail=None):checks.append({'check':name,'pass':bool(ok),'detail':detail})
    def get(id):
        fs=list(RAW.glob(id+'__a*/receipt.json'))
        receipts=[json.loads(f.read_text()) for f in fs]
        m=next(x for x in receipts if x['status']=='HTTP_OK_UNPARSED')
        content=(ROOT/m['raw_file']).read_bytes();check(id+' sha256',hashlib.sha256(content).hexdigest()==m['sha256'])
        return json.loads(content),m
    def series(id):
        o,m=get(id);df=pd.DataFrame(o['itemList']);df['t']=pd.to_datetime(df.timeInterval.map(lambda x:x['from']),utc=True)
        df['end']=pd.to_datetime(df.timeInterval.map(lambda x:x['to']),utc=True)
        check(id+' pagination',len(df)==o['pageInfo']['total']);check(id+' error map empty',not o.get('uuAppErrorMap'))
        check(id+' no duplicate UTC',not df.t.duplicated().any());check(id+' duration 15min',((df.end-df.t).dt.total_seconds()==900).all())
        df['source_id']=m['id'];df['sha256']=m['sha256'];df['retrieved_utc']=m['retrieved_utc']
        return df,m
    pr,pm=series('marginalPricesOverview_2025-08_NET');en,em=series('activatedBalancingEnergyOverview_2025-08_NET')
    expected=pd.date_range('2025-07-31T21:00:00Z','2025-08-31T21:00:00Z',freq='15min',inclusive='left')
    for name,df in [('prices',pr),('energy',en)]:check(name+' complete August UTC grid',list(df.t)==list(expected))
    joint=pr[['t','end','aFRR_Up','aFRR_Down']].rename(columns={'aFRR_Up':'price_up_ron_per_mwh_candidate','aFRR_Down':'price_down_ron_per_mwh_candidate'}).merge(en[['t','aFRR_Up','aFRR_Down']].rename(columns={'aFRR_Up':'energy_up_mwh','aFRR_Down':'energy_down_mwh'}),on='t',validate='one_to_one')
    joint['local_time']=joint.t.dt.tz_convert('Europe/Bucharest');joint['duration_hours']=.25
    joint['price_source_id']=pm['id'];joint['price_sha256']=pm['sha256'];joint['energy_source_id']=em['id'];joint['energy_sha256']=em['sha256']
    joint['retrieved_utc']=pm['retrieved_utc'];joint['publication_time']=None;joint['revision_time']=None
    joint['not_site_cash']=True;joint['status']='EX_POST_RESEARCH_ONLY;API_PRICE_AGGREGATION_AND_FINALITY_UNCONFIRMED'
    save('afrr_price_energy_sample_202508.csv',joint)
    ss={}
    for d in ['up','down']:
        p=joint['price_'+d+'_ron_per_mwh_candidate'];e=joint['energy_'+d+'_mwh'];active=e>0
        ss[d]={'rows':len(p),'price_numeric':int(p.notna().sum()),'energy_numeric':int(e.notna().sum()),'price_zero':int((p==0).sum()),'price_negative':int((p<0).sum()),'price_min':p.min(),'price_max':p.max(),'active_qh':int(active.sum()),'active_missing_price':int((active&p.isna()).sum()),'zero_energy_nonzero_price':int(((e==0)&(p!=0)&p.notna()).sum()),'active_zero_price':int((active&(p==0)).sum()),'energy_sum_mwh':e.sum(),'price_arithmetic_all':p.mean(),'price_arithmetic_active':p[active].mean(),'price_energy_weighted_proxy':(p*e).sum()/e.sum()}
    old=pd.read_csv(ROOT/'countries/RO/full_period_20261001/activatedBalancingEnergyOverview.csv');old['t']=pd.to_datetime(old.delivery_start_utc,utc=True)
    oldaug=old[old.source_month=='2025-08'].set_index('t')
    for col in ['aFRR_Up','aFRR_Down']:check('August energy unchanged '+col,np.allclose(en.set_index('t')[col],oldaug[col],equal_nan=True))
    day,_=series('PRICE_DAILY_CROSSCHECK_2025-08-15');d=pr.set_index('t').loc[day.t]
    for col in ['aFRR_Up','aFRR_Down']:check('monthly versus daily price '+col,np.allclose(d[col],day[col],equal_nan=True))
    missing=pd.read_csv(WORK/'activation_uncomputable_50.csv');missing['t']=pd.to_datetime(missing.delivery_start_utc,utc=True)
    rechecks=[];allfresh=[]
    for ds in sorted(set(missing.local_time.str[:10])|{'2026-02-15','2025-08-15'}):
        fresh,m=series('ACT_RECHECK_'+ds);allfresh.append(fresh)
        g=missing[missing.local_time.str[:10]==ds]
        for _,r in g.iterrows():
            f=fresh.set_index('t').loc[r.t]
            rechecks.append({'delivery_start_utc':r.delivery_start_utc,'local_time':r.local_time,'old_missing_reason':r.missing_reason,'new_up':f.aFRR_Up,'new_down':f.aFRR_Down,'source_id':m['id'],'sha256':m['sha256'],'recovered_energy':(pd.isna(r.energy_up_mwh) and pd.notna(f.aFRR_Up)) or (pd.isna(r.energy_down_mwh) and pd.notna(f.aFRR_Down))})
    rr=pd.DataFrame(rechecks);save('missing_quarter_recheck.csv',rr)
    check('all 50 missing quarters rechecked',len(rr)==50)
    ss['missing_recheck']={'rows':len(rr),'energy_recovered':int(rr.recovered_energy.sum()),'both_still_null':int((rr.new_up.isna()&rr.new_down.isna()).sum()),'down_only_still_null':int((rr.new_up.notna()&rr.new_down.isna()).sum())}
    allfresh=pd.concat(allfresh).drop_duplicates('t').set_index('t');diag=pd.read_csv(WORK/'activation_diagnostic_all.csv');diag['t']=pd.to_datetime(diag.delivery_start_utc,utc=True)
    checked=diag[diag.t.isin(allfresh.index)];match=allfresh.loc[checked.t]
    for col in ['aFRR_Up','aFRR_Down']:check('all rechecked energy values unchanged '+col,np.allclose(checked[col],match[col],equal_nan=True))
    ss['rechecked_energy_qh']=len(checked)
    cap=[]
    for code in ['469_2025','90_2026','310_2025']:
        o,m=get('TENDER_DETAIL_'+code)
        for s in o['tenderServiceList']:
            if s['serviceCode'] not in ['aFRRUp','aFRRDown']:continue
            rows=s['tenderStatistics']['timeIntervalList']; pp=s['contractedPower'];tot={}
            for provider,v in pp.items():
                for point in v['timeIntervalList']:
                    assert point.get('power') is not None, 'Missing provider MW cannot be replaced by zero'
                    start=point['timeInterval']['from'];tot[start]=tot.get(start,0)+point['power']
            stats_sum=sum(r['tenderDemand']*r['tenderSatisfiedDemand'] for r in rows)
            provider_last=tot.get('2025-10-26T21:00:00.000Z')
            cap.append({'tender_code':code,'product':s['serviceCode'],'stats_rows':len(rows),'source_delivery_from':o['timeInterval']['from'],'source_delivery_to':o['timeInterval']['to'],'stats_last_end':rows[-1]['timeInterval']['to'],'stats_capacity_sum_hourly_mw':stats_sum,'provider_utc_hours':len(tot),'provider_sum_hourly_mw':sum(tot.values()),'provider_missing_hour_mw':provider_last,'source_id':m['id'],'sha256':m['sha256']})
    save('capacity_detail_rechecks.csv',pd.DataFrame(cap));ss['capacity_detail']=cap
    # Excel exports are inspected as published day aggregates, not converted into hourly bid curves.
    excel=[]
    c=pd.read_csv(ROOT/'countries/RO/full_period_20261001/capacity_statistics.csv')
    for receipt in RAW.glob('CAP_XLSX*/receipt.json'):
        m=json.loads(receipt.read_text());f=ROOT/m['raw_file'];wb=openpyxl.load_workbook(io.BytesIO(f.read_bytes()),read_only=True,data_only=True)
        rows=list(wb.worksheets[0].values);header=list(rows[7]);dt=pd.Timestamp(rows[2][1]).strftime('%Y-%m-%d')
        check(m['id']+' no offered MW column','OFFERED_POWER' not in header and 'OFFERED POWER' not in header)
        for i,row in enumerate(rows[8:],9):
            if row[3]!='Grand Total':continue
            prod=row[2].replace(' ','');g=c[(c['product']==prod)&(c.local_time.str[:10]==dt)]
            excel.append({'source_id':m['id'],'sheet':'Sheet 1','row':i,'date':dt,'product':prod,'xlsx_accepted_power_day_aggregate':row[7],'xlsx_average_price':row[8],'api_observed_hours':len(g),'api_demand_sum_hourly_mw':g.demand_mw.sum(),'api_accepted_sum_hourly_mw':(g.demand_mw*g.satisfied_ratio).sum(),'xlsx_minus_api_accepted':row[7]-(g.demand_mw*g.satisfied_ratio).sum(),'interpretation':'DAY_AGGREGATE_NOT_INSTANTANEOUS_MW;NOT_TOTAL_OFFERED_VOLUME'})
        wb.close()
    save('capacity_excel_crosschecks.csv',pd.DataFrame(excel));ss['excel_crosschecks']=excel
    dump('sample_month_summary.json',ss);dump('checks.json',checks)
    print(json.dumps({'month':ss,'checks':len(checks),'failed':[x for x in checks if not x['pass']]},ensure_ascii=False,default=str),flush=True)
if __name__=='__main__':
    {'initial':initial,'diagnose':diagnose,'analyze_new':analyze_new}[sys.argv[1]]()
