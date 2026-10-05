"""Validate ENTSO-E A03 sample against UI observations and DAMAS supplier records."""
import csv, json, zipfile, hashlib
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import xml.etree.ElementTree as ET
import openpyxl

OUT=Path(__file__).resolve().parent
REPO=OUT.parents[1]
def array(x): return x if isinstance(x,list) else [x]*24
def read_csv(p):
    with p.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def save_csv(name,rows):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def parse(path):
    out=[]
    with zipfile.ZipFile(path) as z:
        for filename in z.namelist():
            root=ET.fromstring(z.read(filename))
            for e in root.iter(): e.tag=e.tag.split('}')[-1]
            assert root.tag=='Balancing_MarketDocument'
            assert root.findtext('area_Domain.mRID')=='10YRO-TEL------P'
            prod={'A51':'aFRR','A52':'FCR'}[root.findtext('process.processType')]
            for ts in root.findall('TimeSeries'):
                assert ts.findtext('curveType')=='A03'
                assert ts.findtext('currency_Unit.name')=='RON'
                direction={'A01':'Up','A02':'Down','A03':'Symmetric'}[ts.findtext('flowDirection.direction')]
                for period in ts.findall('Period'):
                    assert period.findtext('resolution')=='PT60M'
                    assert period.findtext('timeInterval/start')=='2026-08-30T21:00Z'
                    assert period.findtext('timeInterval/end')=='2026-08-31T21:00Z'
                    pts=period.findall('Point')
                    pos=[int(p.findtext('position')) for p in pts]
                    assert pos[0]==1 and pos==sorted(set(pos)) and pos[-1]<=24
                    values=[]
                    for i,p in enumerate(pts):
                        q=p.findtext('quantity'); price=p.findtext('procurement_Price.amount')
                        assert q is not None and price is not None, 'Missing explicit point must not be forward-filled'
                        values.extend([(float(q),float(price))]*((pos[i+1] if i+1<len(pos) else 25)-pos[i]))
                    assert len(values)==24
                    out.append(dict(product=prod,direction=direction,series_id=ts.findtext('mRID'),values=values,
                                    source=str(path.relative_to(OUT)),document_type=root.findtext('type'),
                                    document_mrid=root.findtext('mRID'),revision=root.findtext('revisionNumber')))
    return out

bids=parse(OUT/'sources/20261004T140214Z/bids_FCR.zip')+parse(OUT/'sources/20261004T140214Z/bids_aFRR.zip')
contracts=parse(OUT/'sources/20261004T140636Z/contracted_FCR_v6.zip')+parse(OUT/'sources/20261004T140636Z/contracted_aFRR_v6.zip')
ui=json.loads((OUT/'entsoe_observed_series.json').read_text())
assert len(bids)==21 and len(contracts)==3
for api,screen in zip(bids,ui['bids']):
    assert (api['product'],api['direction'])==(screen['product'],screen['direction'])
    assert api['values']==list(zip(array(screen['volume']),array(screen['price'])))
for api,screen in zip(contracts,ui['contracted']):
    assert (api['product'],api['direction'])==(screen['product'],screen['direction'])
    assert api['values']==list(zip(array(screen['volume']),array(screen['price'])))

processed=read_csv(REPO/'data/processed/RO/prices_eur_v1_20261002/capacity_native_hourly_eur.csv')
processed={(r['product'],r['delivery_start_utc']):r for r in processed if r['local_date']=='2026-08-31'}
sources=REPO/'project/romania_external_benchmark_20261004/sources'
supplier_rows=list(openpyxl.load_workbook(sources/'fcr_purchased_20260831.xlsx',read_only=True,data_only=True).active.values)
suppliers=defaultdict(list)
mapping={'FCR':'FCR','aFRR Up':'aFRRUp','aFRR Down':'aFRRDown'}
for row in supplier_rows[8:]:
    if row[3] in mapping and isinstance(row[8],(int,float)):
        suppliers[(mapping[row[3]],int(row[2])-1)].append(dict(bsp=row[4],bid=row[6],demand=float(row[7]),awarded=float(row[8])))
daily=list(openpyxl.load_workbook(sources/'fcr_results_20260831.xlsx',read_only=True,data_only=True).active.values)
daily_totals={mapping[r[2]]:(r[7],r[8]) for r in daily[8:] if r[2] in mapping and r[3]=='Grand Total'}
fcr_supplier_prices={r[3]:float(r[8]) for r in daily[8:] if r[2]=='FCR' and r[3]!='Grand Total'}
assert sorted(fcr_supplier_prices.values())==[315,345,380]

start=datetime.fromisoformat('2026-08-30T21:00:00+00:00')
bid_rows=[]; comparisons=[]
for i,b in enumerate(bids):
    product=b['product']+(b['direction'] if b['product']=='aFRR' else '')
    for h,(q,p) in enumerate(b['values']):
        t=(start+timedelta(hours=h)).isoformat().replace('+00:00','Z')
        fx=float(processed[product,t]['fx_ron_per_eur'])
        bid_rows.append(dict(local_date='2026-08-31',delivery_start_utc=t,product=product,
            sample_bid_id=i,api_series_id=b['series_id'],offered_volume_of_published_bid_mw=q,
            offered_price_ron_per_mw_h=p,offered_price_eur_per_mw_h=p/fx,fx_ron_per_eur=fx,
            source_file=b['source'],bsp_identity='NOT_PUBLISHED',is_full_market_offer_curve='UNVERIFIED'))
for c in contracts:
    product=c['product']+(c['direction'] if c['product']=='aFRR' else '')
    relevant=[b for b in bids if b['product']==c['product'] and b['direction']==c['direction']]
    for h,(awarded,p) in enumerate(c['values']):
        t=(start+timedelta(hours=h)).isoformat().replace('+00:00','Z')
        supplier=suppliers[product,h]; demand={r['demand'] for r in supplier};assert len(demand)==1
        exact=sum(r['awarded'] for r in supplier)
        assert exact==awarded, (product,h,exact,awarded)
        pr=processed[product,t];fx=float(pr['fx_ron_per_eur'])
        offered=sum(b['values'][h][0] for b in relevant)
        weighted=sum(r['awarded']*fcr_supplier_prices[r['bsp']] for r in supplier)/exact if product=='FCR' else ''
        comparisons.append(dict(local_date='2026-08-31',local_hour=h,delivery_start_utc=t,product=product,
            demand_mw=next(iter(demand)),damas_supplier_awarded_mw=exact,entsoe_contracted_mw=awarded,
            quantity_error_mw=awarded-exact,entsoe_published_offer_sum_mw=offered,
            contracted_to_published_offer_ratio=awarded/offered,
            existing_accepted_proxy_mw=float(pr['accepted_capacity_mw']),
            proxy_error_mw=float(pr['accepted_capacity_mw'])-exact,
            entsoe_average_price_ron_per_mw_h=p,
            existing_average_price_ron_per_mw_h=float(pr['average_accepted_price_eur_per_mw_h_proxy'])*fx,
            entsoe_price_eur_per_mw_h=p/fx,fx_ron_per_eur=fx,fx_fixing_date=pr['fx_fixing_date'],
            fcr_actual_award_weighted_price_ron_per_mw_h=weighted,source_file=c['source']))
assert len(bid_rows)==504 and len(comparisons)==72
assert len({(r['sample_bid_id'],r['delivery_start_utc']) for r in bid_rows})==504
summary={}
for product in ['FCR','aFRRUp','aFRRDown']:
    rows=[r for r in comparisons if r['product']==product]
    assert len(rows)==24
    exact=sum(r['damas_supplier_awarded_mw'] for r in rows)
    assert abs(exact-daily_totals[product][0])<1e-8
    summary[product]=dict(hours=24,bid_series=sum(1 for b in bids if b['product']+(b['direction'] if b['product']=='aFRR' else '')==product),
        mean_contracted_mw=exact/24,mean_published_offer_mw=sum(r['entsoe_published_offer_sum_mw'] for r in rows)/24,
        min_published_offer_mw=min(r['entsoe_published_offer_sum_mw'] for r in rows),max_published_offer_mw=max(r['entsoe_published_offer_sum_mw'] for r in rows),
        ratio_of_summed_contracted_to_published_offers=exact/sum(r['entsoe_published_offer_sum_mw'] for r in rows),
        max_quantity_error_mw=max(abs(r['quantity_error_mw']) for r in rows),
        max_existing_proxy_error_mw=max(abs(r['proxy_error_mw']) for r in rows),
        max_price_difference_ron=max(abs(r['entsoe_average_price_ron_per_mw_h']-r['existing_average_price_ron_per_mw_h']) for r in rows),
        entsoe_time_mean_price_ron=sum(r['entsoe_average_price_ron_per_mw_h'] for r in rows)/24,
        damas_daily_award_weighted_price_ron=daily_totals[product][1])
summary['checks']='PASS: A03 expansion; 504 bid-hours and 72 contracted hours; API exactly matches all UI values; 72/72 volumes equal DAMAS supplier sums; daily supplier totals reconcile; local day/UTC/FX join complete. API prices are themselves rounded to 2 decimals.'
save_csv('entsoe_bid_hourly_20260831.csv',bid_rows)
save_csv('capacity_hourly_comparison_20260831.csv',comparisons)
(OUT/'validation_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
