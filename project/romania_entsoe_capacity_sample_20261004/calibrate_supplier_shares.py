"""August 2026 supplier-share calibration from immutable official workbooks."""
import csv, json, re, hashlib, urllib.request, shutil, sys
from pathlib import Path
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from datetime import datetime, timezone
import numpy as np
import openpyxl

OUT=Path(__file__).resolve().parent/'supplier_calibration_aug2026'
OUT.mkdir(exist_ok=True)
SAMPLE=OUT.parent
REPO=SAMPLE.parents[1]
OLD=REPO/'project/romania_external_benchmark_20261004/sources'
def csvread(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def csvsave(name,rows):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def download():
    links=[]
    class Parser(HTMLParser):
        def handle_starttag(self,tag,attrs):
            if tag=='a':
                h=dict(attrs).get('href','')
                m=re.search(r'(ansContractPurchasedReserves|ansTenderResults)_(\d{2})\.08\.2026\.xlsx',h)
                if m:links.append((m.group(1),m.group(2),h))
    Parser().feed((OLD/'fcr_info_sts_20261004.html').read_text(encoding='utf-8'))
    links=list(dict.fromkeys(links));assert len(links)==62
    dest=OUT/'sources'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    dest.mkdir(parents=True,exist_ok=False)
    def fetch(item):
        kind,day,href=item;url='https://www.transelectrica.ro'+href
        name=f'{kind}_{day}.08.2026.xlsx';file=dest/name
        try:
            if day=='31':
                origin=OLD/('fcr_purchased_20260831.xlsx' if kind=='ansContractPurchasedReserves' else 'fcr_results_20260831.xlsx')
                shutil.copyfile(origin,file);data=file.read_bytes();method='reuse_prior_official_download'
            else:
                with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=30) as r:data=r.read()
                assert data[:2]==b'PK';file.write_bytes(data);method='download'
            return dict(date=f'2026-08-{day}',kind=kind,url=url,file=name,status='ok',bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),method=method)
        except Exception as exc:return dict(date=f'2026-08-{day}',kind=kind,url=url,status='error',error_type=type(exc).__name__)
    records=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(fetch,x) for x in links]):
            r=future.result();records.append(r)
            if len(records)%10==0:print('Retrieved',len(records),'of',len(links),flush=True)
    (dest/'receipts.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    print('Download results',sum(r['status']=='ok' for r in records),'/',len(records),flush=True)

def analyze():
    files={}
    for manifest in sorted((OUT/'sources').glob('*/receipts.json')):
        for r in json.loads(manifest.read_text()):
            if r['status']=='ok':files[r['date'],r['kind']]=(manifest.parent/r['file'],r)
    assert len(files)==62
    prodmap={'FCR':'FCR','aFRR Up':'aFRRUp','aFRR Down':'aFRRDown'}
    daily_bid={};daily_totals={};daily_supplier=defaultdict(float);daily_demand={};inferred=[]
    workbooks={}
    for (date,kind),(path,receipt) in sorted(files.items()):
        assert hashlib.sha256(path.read_bytes()).hexdigest()==receipt['sha256']
        rows=list(openpyxl.load_workbook(path,read_only=True,data_only=True).active.values)
        assert rows[7][0]=='DATE'
        workbooks[date,kind]=rows
        if kind!='ansTenderResults':continue
        for r in rows[8:]:
            if r[2] not in prodmap:continue
            assert r[0].strftime('%Y-%m-%d')==date
            p=prodmap[r[2]]
            if r[3]=='Grand Total':
                daily_totals[date,p]=float(r[7])
            else:
                key=(date,p,r[3],r[4],r[5]);assert key not in daily_bid
                if (date,p) in daily_demand:assert daily_demand[date,p]==float(r[6])
                daily_demand[date,p]=float(r[6])
                assert r[7] is None or (isinstance(r[7],(int,float)) and r[7]>=0)
                daily_bid[key]=None if r[7] is None else float(r[7])
    assert len(daily_totals)==93
    # Zero inference allowed only when numeric bids exhaust the published product total.
    for (d,p),total in daily_totals.items():
        vals=[v for k,v in daily_bid.items() if k[:2]==(d,p) and v is not None]
        assert abs(sum(vals)-total)<1e-8,(d,p,'Daily bid reconciliation')
    for key,value in daily_bid.items():
        if value is None:
            inferred.append(dict(date=key[0],product=key[1],bsp=key[2],tender=key[3],bid=key[4],reason='Blank daily bid; other numeric bids exactly exhaust nonnegative product total; inferred zero'))
            daily_bid[key]=0.0
        daily_supplier[key[:3]]+=daily_bid[key]
    bids=defaultdict(dict);demands=defaultdict(set);missing=[];hourly_zero_count=0
    for (d,kind),rows in workbooks.items():
        if kind!='ansContractPurchasedReserves':continue
        assert rows[7][2]=='INTERVAL'
        for r in rows[8:]:
            if r[3] not in prodmap:continue
            assert r[0].strftime('%Y-%m-%d')==d
            p=prodmap[r[3]];h=int(r[2])-1;key=(d,p,r[4],r[5],r[6])
            assert 0<=h<24 and h not in bids[key] and key in daily_bid
            v=r[8]
            assert v is None or (isinstance(v,(int,float)) and v>=0)
            bids[key][h]=None if v is None else float(v)
            demands[d,h,p].add(float(r[7]))
    assert set(bids)==set(daily_bid)
    group=defaultdict(list);bid_mismatches=[]
    for key,values in bids.items():
        assert len(values)==24
        known=[v for v in values.values() if v is not None]
        if abs(sum(known)-daily_bid[key])>1e-8:
            bid_mismatches.append(dict(date=key[0],product=key[1],bsp=key[2],tender=key[3],bid=key[4],hourly_numeric_sum=sum(known),daily_bid_total=daily_bid[key],blank_hours=24-len(known)))
        d,p,b,_,_=key
        for h,v in values.items():group[d,h,p,b].append(v)
    # BID numbers differ between the two report layouts; only BSP totals are joined.
    supplier_checks=0
    for (d,p,b),daily_q in daily_supplier.items():
        vals=[v for h in range(24) for v in group[d,h,p,b]]
        known_sum=sum(v for v in vals if v is not None)
        assert abs(known_sum-daily_q)<1e-8,((d,p,b),'Hourly numeric supplier sum vs daily total')
        supplier_checks+=1
        # Nonnegative hourly allocations: zero residual proves blank entries add zero.
        blanks=sum(v is None for v in vals)
        if blanks:
            missing.append(dict(date=d,product=p,bsp=b,blank_bid_hour_cells=blanks,daily_awarded_mw_hours=daily_q,known_hourly_sum=known_sum,inferred_residual_mw_hours=0))
            hourly_zero_count+=blanks
            for h in range(24):group[d,h,p,b]=[0.0 if v is None else v for v in group[d,h,p,b]]
    assert len(demands)==2232
    for (d,p),v in daily_demand.items():
        assert all(len(demands[d,h,p])==1 for h in range(24))
        assert abs(sum(next(iter(demands[d,h,p])) for h in range(24))-v)<1e-8
    qs={k:sum(v) if all(x is not None for x in v) else None for k,v in group.items()}
    hourly=[];market=[];totals={}
    for (d,h,p),dset in sorted(demands.items()):
        demand=next(iter(dset));sub={k[3]:v for k,v in qs.items() if k[:3]==(d,h,p)}
        complete=all(v is not None for v in sub.values());total=sum(sub.values()) if complete else None
        totals[d,h,p]=total
        for b,q in sub.items():
            hourly.append(dict(date=d,hour=h,product=p,bsp=b,awarded_mw=q if q is not None else '',demand_mw=demand,
                system_awarded_mw=total if total is not None else '',share_of_demand=q/demand if q is not None else '',
                share_of_awards=q/total if complete and total else '',quantity_complete=q is not None))
        positive=[q for q in sub.values() if q is not None and q>0]
        market.append(dict(date=d,hour=h,product=p,demand_mw=demand,system_awarded_mw=total if complete else '',
            quantity_complete=complete,active_suppliers=len(positive) if complete else '',
            hhi_awards=sum((q/total)**2 for q in positive)*10000 if complete and total else '',
            top1_share_of_demand=max(positive)/demand if complete and positive else '',
            unfilled_demand_mw=max(0,demand-total) if complete else ''))
    ds=[]
    for (d,p,b),q in sorted(daily_supplier.items()):
        ds.append(dict(date=d,product=p,bsp=b,awarded_mw_hours=q,mean_awarded_mw=q/24,demand_mw_hours=daily_demand[d,p],
            system_awarded_mw_hours=daily_totals[d,p],share_of_demand=q/daily_demand[d,p],share_of_awards=q/daily_totals[d,p]))
    summary=[]
    for p,b in sorted({(r['product'],r['bsp']) for r in ds}):
        rs=[r for r in ds if r['product']==p and r['bsp']==b]
        hrs=[r for r in hourly if r['product']==p and r['bsp']==b and r['quantity_complete']]
        q=np.array([r['awarded_mw_hours'] for r in rs]);shares=np.array([r['share_of_demand'] for r in rs]);hs=np.array([r['share_of_demand'] for r in hrs])
        summary.append(dict(product=p,bsp=b,reported_days=len(rs),positive_days=int(sum(q>0)),valid_hourly_points=len(hrs),
            mean_awarded_mw_reported_days=float(q.mean()/24),capacity_mw_hours=float(q.sum()),
            share_of_full_month_demand=float(q.sum()/sum(v for (d,pp),v in daily_demand.items() if pp==p)),
            share_of_full_month_awards=float(q.sum()/sum(v for (d,pp),v in daily_totals.items() if pp==p)),
            daily_share_p50=float(np.quantile(shares,.5)),daily_share_p90=float(np.quantile(shares,.9)),
            hourly_share_p50=float(np.quantile(hs,.5)),hourly_share_p90=float(np.quantile(hs,.9)),
            note='Monthly numerator from daily results; absent supplier-days not assumed zero; hourly quantiles omit unresolved missing hours'))
    for name,rows in [('supplier_hourly_shares.csv',hourly),('supplier_daily_shares.csv',ds),('supplier_month_summary.csv',summary),('market_hourly_concentration.csv',market),('hourly_blank_zero_inferences.csv',missing),('cross_report_bid_number_mismatches.csv',bid_mismatches),('daily_blank_zero_inferences.csv',inferred)]:
        csvsave(name,rows)
    comp=csvread(SAMPLE/'capacity_hourly_comparison_20260831.csv')
    assert len(comp)==72 and all(totals[r['local_date'],int(r['local_hour']),r['product']]==float(r['entsoe_contracted_mw']) for r in comp)
    result={}
    for p in prodmap.values():
        ms=[r for r in market if r['product']==p];valid=[r for r in ms if r['quantity_complete']];ss=[r for r in summary if r['product']==p]
        result[p]=dict(hours=len(ms),valid_complete_market_hours=len(valid),suppliers=len(ss),demand_values=sorted({r['demand_mw'] for r in ms}),
            mean_awarded_mw=sum(v for (d,pp),v in daily_totals.items() if pp==p)/744,
            mean_active_suppliers_valid_hours=float(np.mean([r['active_suppliers'] for r in valid])),
            mean_hhi_valid_hours=float(np.mean([r['hhi_awards'] for r in valid])),suppliers_summary=ss)
    # Explicit research choices, not market rules or inferred project win probabilities.
    fcr_peer=next(r for r in summary if r['product']=='FCR' and r['bsp']=='PETROM (30XROPETROM----4)')
    afrr_refs={}
    for p in ('aFRRUp','aFRRDown'):
        peers=[r for r in summary if r['product']==p and r['reported_days']==31 and r['positive_days']>0]
        afrr_refs[p]=dict(n=len(peers),share=float(np.median([r['hourly_share_p90'] for r in peers])))
    sf=fcr_peer['hourly_share_p90'];sa=min(v['share'] for v in afrr_refs.values())
    candidates=[dict(parameter='fcr_market_share_cap',value=sf,reference_demand_mw=128,cap_mw=sf*128,
        basis='PETROM hourly share P90; non-leading full-month incumbent peer selected as modeling assumption'),
        dict(parameter='afrr_market_share_cap',value=sa,reference_demand_mw=175,cap_mw=sa*175,
        basis='Minimum of directional medians of supplier hourly share P90; full-month reported positive-award suppliers only')]
    csvsave('proposed_share_parameters.csv',candidates)
    executed=csvread(REPO/'outputs/capacity_sensitivity_100mw_200mwh_20261002/v3/p100_run/executed_qh.csv')
    aug=[r for r in executed if r['local_date'].startswith('2026-08-')];assert len(aug)==2976
    diagnostic=[]
    for p,col,demand,cap in [('FCR','fcr_mw',128,sf*128),('aFRRUp','afrr_up_mw',175,sa*175),('aFRRDown','afrr_down_mw',175,sa*175)]:
        a=np.array([float(r[col]) for r in aug]);ex=a>cap+1e-8
        diagnostic.append(dict(product=p,old_mean_awarded_mw=float(a.mean()),old_max_mw=float(a.max()),
            old_mean_share_of_demand=float(a.mean()/demand),proposed_cap_mw=cap,
            old_schedule_exceeds_cap_hours=float(ex.sum()*.25),exceed_fraction=float(ex.mean()),
            mean_excess_mw=float(np.maximum(a-cap,0).mean()),note='Schedule diagnostic only; not reoptimized revenue or a feasible clipped dispatch'))
    csvsave('old_schedule_cap_diagnostic_aug2026.csv',diagnostic)
    result['proposed_parameters']=candidates
    result['afrr_directional_reference']=afrr_refs
    result['checks']=dict(file_hashes=62,daily_product_totals_reconciled=93,supplier_days_reconciled=supplier_checks,cross_report_bid_number_mismatches=len(bid_mismatches),
        market_hours=2232,unresolved_missing_supplier_hours=0,hourly_zero_inference_supplier_days=len(missing),inferred_daily_zero_bid_blocks=len(inferred),
        inferred_hourly_zero_cells_from_supplier_residual=hourly_zero_count,entsoe_aug31_quantity_matches=72,milp_rerun=False)
    (OUT/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({p:({k:v for k,v in r.items() if k!='suppliers_summary'} if isinstance(r,dict) else r) for p,r in result.items()},ensure_ascii=True,indent=2))

if __name__=='__main__':
    if '--download' in sys.argv:download()
    else:analyze()
