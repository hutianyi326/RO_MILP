"""Research-only reproducible sample parsing/QA. No model or revenue simulation."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict, Counter
from xml.etree import ElementTree as ET
import csv, io, json, hashlib, re
from lxml import html

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent
RAW=ROOT/'data/raw/RO/samples/20260930'
OUT=ROOT/'countries/RO/data_samples_20260930'
OUT.mkdir(parents=True,exist_ok=True)
UTC=timezone.utc; CET=ZoneInfo('Europe/Brussels'); RO=ZoneInfo('Europe/Bucharest')
DAYS=['2025-01-15','2025-03-30','2025-09-30','2025-10-01','2025-10-26','2026-03-29','2026-08-31']
errors=[];checks=[];manifest=[];coverage=[];source_anomalies=[]
def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
def csvout(name,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader();writer.writerows(rows)
def check(name,ok,detail=''):
    checks.append(dict(check=name,pass_=bool(ok),detail=detail))
    if not ok:errors.append(name+': '+str(detail))
def iso(t):return t.astimezone(UTC).isoformat().replace('+00:00','Z')
def dt(t):return datetime.fromisoformat(t.replace('Z','+00:00'))
def bounds(day,tz):
    start=datetime.fromisoformat(day).replace(tzinfo=tz)
    return start.astimezone(UTC),(start+timedelta(days=1)).astimezone(UTC)
def norm(a,b):
    a=dt(a) if isinstance(a,str) else a;b=dt(b) if isinstance(b,str) else b
    return dict(delivery_start_utc=iso(a),delivery_end_utc=iso(b),local_time=a.astimezone(RO).isoformat(),utc_offset=a.astimezone(RO).strftime('%z'),duration_hours=(b-a).total_seconds()/3600,publication_time='',revision_time='',quality_flag='EX_POST_SNAPSHOT;NOT_ASOF_APPROVED')

for p in sorted(RAW.glob('*/receipt.json')):
    m=json.loads(p.read_text(encoding='utf-8-sig'));m.update(access_date='2026-09-30',record_count=None,numeric_record_count=None,parse_status='NOT_PARSED',detected_format=None,source_timezone=None,resolution_minutes=None,unit=None,currency=None,publication_time=None,revision=None,actual_time_range=None)
    if m.get('raw_file'):
        data=(ROOT/m['raw_file']).read_bytes();check(m['id']+' hash',hashlib.sha256(data).hexdigest()==m['sha256'])
        if data.startswith(b'%PDF'):m['detected_format']='PDF'
        elif data.lstrip().startswith(b'{'):m['detected_format']='JSON'
        elif data.lstrip().startswith(b'<?xml'):m['detected_format']='XML'
        elif data.startswith(b'"Mcp and Traded Volume'):m['detected_format']='CSV'
        elif data.startswith(b'KEY,FREQ') or b'TIME_PERIOD,OBS_VALUE' in data[:1800]:m['detected_format']='CSV_SDMX'
        else:m['detected_format']='HTML'
    else:m['parse_status']='ACQUISITION_FAILED'
    manifest.append(m)
byid={m['id']:m for m in manifest}
def text(m):return (ROOT/m['raw_file']).read_text(encoding='utf-8-sig',errors='replace')

da=[];daily=[];selected={}
for m in manifest:
    if m['dataset']!='D02' or m.get('detected_format')!='CSV':continue
    day=m['id'][3:13]
    if day in selected:check('no duplicate DA revision selection',False,day);continue
    rows=list(csv.reader(io.StringIO(text(m))));records=[r for r in rows if r and r[0]=='Romania'];base=next((r for r in rows if r and r[0].startswith('ROPEX_DAM_Base')),None)
    m.update(parse_status='PARSED',record_count=len(records),numeric_record_count=len(records),source_timezone='CET/CEST (Europe/Brussels)',resolution_minutes=60 if day<'2025-10-01' else 15,unit='price EUR/MWh; interval quantity MW; summary MWh',currency='EUR',revision='latest export retrieved; historic revision unknown')
    start,end=bounds(day,CET);step=timedelta(minutes=m['resolution_minutes']);expected=int((end-start)/step)
    check(m['id']+' native count',len(records)==expected,dict(expected=expected,actual=len(records)))
    check(m['id']+' consecutive interval IDs',[int(r[1]) for r in records]==list(range(1,expected+1)))
    selected[day]=m['id'];energy=Decimal(0);cash=Decimal(0);prices=Decimal(0);duration=Decimal(str(step.total_seconds()/3600));round_bound=Decimal(0)
    for r in records:
        p,v,buy,sell=map(Decimal,r[2:6]);a=start+(int(r[1])-1)*step
        da.append(dict(source_id=m['id'],raw_file_hash=m['sha256'],source_market_date=day,source_interval=r[1],market='DA',product='PT'+str(m['resolution_minutes'])+'M',direction='market statistic',source_price=r[2],price_eur_mwh=str(p),source_volume_mw=r[3],source_buy_mw=r[4],source_sell_mw=r[5],energy_mwh=str(v*duration),currency='EUR',unit='EUR/MWh; MW; derived MWh',**norm(a,a+step)))
        energy+=v*duration;cash+=p*v*duration;prices+=p
        # Explicit A: nearest rounding to public 0.01 EUR/MWh and 0.1 MW precision.
        round_bound+=duration*(abs(v)*Decimal('.005')+abs(p)*Decimal('.05')+Decimal('.00025'))
        check(m['id']+' max(buy,sell) interval '+r[1],v==max(buy,sell))
    if base:
        if abs(energy-Decimal(base[2]))>Decimal('.0500001'):
            source_anomalies.append(dict(issue='SQ01',source_id=m['id'],field='ROPEX_DAM_Base summary Quantity [MWh]',derived=str(energy),source_value=base[2],ratio=str(Decimal(base[2])/energy),handling='original retained; summary not used as physical MWh; native MW multiplied by duration; monthly control agrees'))
        check(m['id']+' daily base arithmetic price',abs(prices/len(records)-Decimal(base[1]))<=Decimal('.0050001'))
    daily.append(dict(date=day,source_id=m['id'],records=len(records),expected=expected,hours=str(duration*len(records)),energy_mwh=str(energy),cash_eur=str(cash),arithmetic_price_eur_mwh=str(prices/len(records)),cash_rounding_bound_eur=str(round_bound),negative_prices=sum(Decimal(r[2])<0 for r in records),zero_prices=sum(Decimal(r[2])==0 for r in records)))
    m['actual_time_range']=[iso(start),iso(end)]
    coverage.append(dict(dataset='D02',sample=day,product='DA',expected=expected,actual=len(records),numeric=len(records),status='DESCRIPTIVE_AND_EXPOST_PRICE_INPUT_ONLY',source_ids=m['id'],native_timezone='CET/CEST',known_before_decision=False))
csvout('da_native_samples.csv',da);csvout('da_day_checks.csv',daily)

xml=byid.get('DA_XML_2025-10-26')
if xml and xml.get('raw_file'):
    root=ET.fromstring(text(xml));items=root.findall('Detail');sample=[r for r in da if r['source_market_date']=='2025-10-26']
    check('DA CSV/XML same-source cross-format',len(items)==len(sample) and all(int(x.findtext('Interval'))==int(r['source_interval']) and Decimal(x.findtext('Price'))==Decimal(r['source_price']) and Decimal(x.findtext('ClearedEnergy'))==Decimal(r['source_volume_mw']) for x,r in zip(items,sample)))
    xml.update(record_count=len(items),parse_status='PARSED_SAME_SOURCE_CHECK',source_timezone='CET/CEST',unit='ClearedEnergy element has no own unit; matches CSV MW, not treated as MWh',currency='EUR')

control={'2025-01':('1648619.1','244317306.16','139.45','148.20',744),'2025-10':('1465131.7','184597364.34','121.90','125.99',2980),'2026-08':('1188430.5','179564070.67','151.16','151.09',2976)}
monthly=[]
for month,(vol,cash,arith,weighted,count) in control.items():
    rows=[r for r in da if r['source_market_date'].startswith(month)];ds=[d for d in daily if d['date'].startswith(month)]
    energy=sum(Decimal(r['energy_mwh']) for r in rows);value=sum(Decimal(r['price_eur_mwh'])*Decimal(r['energy_mwh']) for r in rows)
    interval_ap=sum(Decimal(r['price_eur_mwh']) for r in rows)/len(rows)
    ap=sum(Decimal(d['arithmetic_price_eur_mwh']) for d in ds)/len(ds);wp=value/energy
    bound=sum(Decimal(d['cash_rounding_bound_eur']) for d in ds)+Decimal('.005')
    check(month+' complete month',len(rows)==count and len(ds)==31)
    check(month+' official volume',abs(energy-Decimal(vol))<=Decimal('.0500001'))
    check(month+' arithmetic monthly mean',abs(ap-Decimal(arith))<=Decimal('.0050001'))
    check(month+' weighted monthly mean',abs(wp-Decimal(weighted))<=Decimal('.0050001'))
    check(month+' cash compatible with displayed precision A',abs(value-Decimal(cash))<=bound)
    monthly.append(dict(month=month,records=len(rows),expected=count,complete_days=len(ds),derived_volume_mwh=str(energy),official_volume_mwh=vol,volume_diff=str(energy-Decimal(vol)),derived_cash_eur=str(value),official_cash_eur=cash,cash_diff=str(value-Decimal(cash)),cash_rounding_bound_A_eur=str(bound),derived_arithmetic_price_mean_of_daily_means=str(ap),derived_mean_over_native_intervals=str(interval_ap),official_arithmetic_price=arith,derived_weighted_price=str(wp),official_weighted_price=weighted,source_id='MONTH_'+month,source_location='PDF p2 / printed p1; Day-Ahead Market; headline means and comparison table',status='PASS_PRECISION_CONSISTENT;daily-mean interpretation I;exact hidden ledger not reproduced'))
csvout('monthly_reconciliation.csv',monthly)

ida=[];ida_qa=[]
for day in DAYS:
    m=byid['IDA_'+day];doc=html.fromstring(text(m));dates=doc.xpath('//input[@name="ziua_eng"]/@value');check(m['id']+' selected date',dates==[datetime.fromisoformat(day).strftime('%m/%d/%Y')])
    tabs=[tb for tb in doc.xpath('//table') if 'ROPEX_IDA' in ' '.join(tb.xpath('.//tr')[0].text_content().split()) and len(tb.xpath('.//tr'))>20]
    for auction,tb in enumerate(tabs,1):
        rr=[]
        for tr in tb.xpath('.//tr'):
            cells=[' '.join(c.text_content().split()) for c in tr.xpath('./td|./th')]
            if cells and cells[0]=='Romania':cells=cells[1:]
            if cells and cells[0].isdigit():rr.append(cells)
        full=int((bounds(day,CET)[1]-bounds(day,CET)[0]).total_seconds()/900)
        def number(value):
            return None if value in ('','-') else Decimal(value)
        numeric=sum(len(r)>1 and number(r[1]) is not None for r in rr)
        volume_numeric=sum(len(r)>2 and number(r[2]) is not None for r in rr)
        valid_pair=sum(len(r)>2 and number(r[1]) is not None and number(r[2]) is not None for r in rr)
        check(m['id']+' auction '+str(auction)+' template rows',len(rr)==full)
        # IDA3 first half is not an offered product. Presence is not valid-price coverage.
        eligible=full if auction<3 else 48
        state='EMPTY_PRICE_VOLUME' if numeric==volume_numeric==0 else 'PARTIAL_PRICE_VOLUME' if valid_pair<eligible else 'COMPLETE_PRICE_VOLUME'
        coverage.append(dict(dataset='D03',sample=day,product='IDA'+str(auction),expected=eligible,actual=len(rr),numeric=numeric,numeric_volume=volume_numeric,valid_price_volume=valid_pair,status=state+';NOT_ASOF_APPROVED;missing not historical zero',source_ids=m['id'],native_timezone='CET/CEST',known_before_decision=False))
        for r in rr:
            values=(r[1:]+['']*4)[:4];price,volume,buy,sell=values;nums=list(map(number,values));offered=not(auction==3 and int(r[0])<=full-48)
            quality=('NOT_OFFERED_FIRST_HALF' if not offered else 'VALID_PRICE_VOLUME' if nums[0] is not None and nums[1] is not None else 'MISSING_PRICE_OR_VOLUME')
            a=bounds(day,CET)[0]+(int(r[0])-1)*timedelta(minutes=15)
            row=dict(source_id=m['id'],raw_file_hash=m['sha256'],date=day,auction=auction,source_interval=r[0],source_price=price,source_volume_mw=volume,source_buy_mw=buy,source_sell_mw=sell,source_values=json.dumps(r[2:]),price_valid=nums[0] is not None,volume_valid=nums[1] is not None,buy_valid=nums[2] is not None,sell_valid=nums[3] is not None,normalized_price_eur_mwh='' if nums[0] is None else str(nums[0]),energy_mwh='' if nums[1] is None else str(nums[1]*Decimal('.25')),price_volume_eur='' if nums[0] is None or nums[1] is None else str(nums[0]*nums[1]*Decimal('.25')),row_status=quality,currency='EUR',**norm(a,a+timedelta(minutes=15)))
            row['quality_flag']=quality+';NOT_ASOF_APPROVED'+''.join(';'+label+'_MISSING' for label,n in zip(['PRICE','VOLUME','BUY','SELL'],nums) if n is None)
            ida.append(row)
        output=[r for r in ida if r['source_id']==m['id'] and r['auction']==auction]
        check(m['id']+' IDA'+str(auction)+' source/output coverage states',sum(r['price_valid'] for r in output)==numeric and sum(r['volume_valid'] for r in output)==volume_numeric and sum(r['row_status']=='VALID_PRICE_VOLUME' for r in output)==valid_pair and (state!='EMPTY_PRICE_VOLUME' or numeric==volume_numeric==0))
        ida_qa.append(dict(source_id=m['id'],auction=auction,eligible=eligible,template=len(rr),price_numeric=numeric,volume_numeric=volume_numeric,valid_pair=valid_pair,status=state))
    output=[r for r in ida if r['source_id']==m['id']];valid=sum(r['price_valid'] for r in output)
    m.update(parse_status='PARSED_PARTIAL_PRICE_VOLUME' if valid else 'PARSED_EMPTY_FIELDS',record_count=len(output),numeric_record_count=valid,numeric_by_auction={str(i):sum(r['price_valid'] for r in output if r['auction']==i) for i in [1,2,3]},source_timezone='CET/CEST',resolution_minutes=15,unit='price EUR/MWh; volume MW; total MWh',currency='EUR')
    check(m['id']+' IDA manifest numeric',m['numeric_record_count']==sum(r['row_status']=='VALID_PRICE_VOLUME' for r in output))
csvout('ida_field_samples.csv',ida)
dump(WORK/'ida_checks.json',ida_qa)
example=next(r for r in ida if r['source_id']=='IDA_2025-10-01' and r['auction']==2 and r['source_interval']=='23')
check('IDA2 2025-10-01 official numeric anchor and field-level missing',example['source_price']=='105.93' and example['source_volume_mw']=='3.2' and example['energy_mwh']=='0.800' and example['price_volume_eur']=='84.74400' and example['source_buy_mw']=='-' and not example['buy_valid'] and example['row_status']=='VALID_PRICE_VOLUME')
check('IDA2 2025-10-01 observed 46 valid intervals',sum(r['price_valid'] for r in ida)==46 and [int(r['source_interval']) for r in ida if r['price_valid']]==list(range(23,38))+list(range(63,94)))

series=[];capacity=[];events=[];contracted=[];jsonqa=[]
accepted_prefixes=['activatedBalancingEnergyOverview_','marginalPricesOverview_','dailyConsumptionOverview_','scheduledExchanges_']
seen_series=set();seen_cap=set()
for m in manifest:
    if m.get('detected_format')!='JSON':continue
    obj=json.loads(text(m))
    if 'metadata' in obj:
        m.update(parse_status='METADATA_ONLY',record_count=1,source_timezone=obj['metadata'].get('timeZone'),revision='unknown; report-level last update is not revision history',metadata_last_update=obj['metadata'].get('lastUpdateTimestamp'));continue
    if m['id'].startswith(tuple(accepted_prefixes)):
        report=next(p[:-1] for p in accepted_prefixes if m['id'].startswith(p));day=m['id'][len(report)+1:len(report)+11];items=obj.get('itemList',[]);tz=CET if report=='scheduledExchanges' else RO
        a,b=bounds(day,tz);keys=[r['timeInterval']['from'] for r in items]
        check(m['id']+' page completeness',len(items)==obj.get('pageInfo',{}).get('total',-1))
        check(m['id']+' UTC unique',len(keys)==len(set(keys)))
        expected=int((b-a).total_seconds()/900);check(m['id']+' QH native count',len(items)==expected)
        check(m['id']+' bounds/sequence',len(items)>0 and dt(items[0]['timeInterval']['from'])==a and dt(items[-1]['timeInterval']['to'])==b and all(dt(r['timeInterval']['from'])==a+i*timedelta(minutes=15) and dt(r['timeInterval']['to'])==a+(i+1)*timedelta(minutes=15) for i,r in enumerate(items)))
        if (report,day) in seen_series:check('duplicate source selection',False,m['id']);continue
        seen_series.add((report,day));counts=Counter()
        for r in items:
            if report=='dailyConsumptionOverview':fields=[('grossForecastConsumption',r.get('grossForecastConsumption'),'MW'),('grossRealizedConsumption',r.get('grossRealizedConsumption'),'MW')]
            elif report=='scheduledExchanges':fields=[(border+'.'+component,value,'MW') for border,vs in r.items() if border in ['huro','rohu','mdro','romd','roua','uaro','bgro','robg','rors','rsro'] for component,value in vs.items()]
            elif report=='activatedBalancingEnergyOverview':fields=[(f,r.get(f),'MWh') for f in ['fcr','aFRR_Up','aFRR_Down','mFRR_Up','mFRR_Down','rr_Up','rr_Down']]
            else:fields=[(f,r.get(f),'LEI; denominator pending report definition') for f in ['aFRR_Up','aFRR_Down','mFRR_Up_Scheduled','mFRR_Down_Scheduled','mFRR_Up_Direct','mFRR_Down_Direct','rr_Up','rr_Down']]
            for field,value,unit in fields:
                counts[field]+=value is not None
                series.append(dict(source_id=m['id'],raw_file_hash=m['sha256'],dataset=m['dataset'],report=report,source_market_date=day,product_direction=field,source_value=value,normalized_value=value,unit=unit,currency='RON' if report=='marginalPricesOverview' else '',source_last_update=r.get('lastUpdate',''),**norm(r['timeInterval']['from'],r['timeInterval']['to'])))
        for field,n in counts.items():coverage.append(dict(dataset=m['dataset'],sample=day,product=field,expected=expected,actual=len(items),numeric=n,status='STRUCTURE_PASS;field nulls retained;ASOF_NOT_APPROVED',source_ids=m['id'],native_timezone='CET/CEST' if tz is CET else 'EET/EEST',known_before_decision=False))
        m.update(parse_status='PARSED',record_count=len(items),numeric_record_count=dict(counts),source_timezone='CET/CEST' if tz is CET else 'EET/EEST',resolution_minutes=15,unit='see dataset field dictionary',actual_time_range=[iso(a),iso(b)],revision='unversioned latest public snapshot')
        jsonqa.append(dict(source_id=m['id'],day=day,report=report,expected=expected,actual=len(items),numeric_counts=dict(counts)))
    elif m['dataset']=='D05' and ('tenderServiceList' in obj or 'itemList' in obj):
        day=m['requested_scope'][:10]
        if m['id'].startswith('CAP_'):day='2026-08-31'
        a,b=bounds(day,RO);items=obj.get('itemList',[obj]);kept=0;outside=0
        if 'pageInfo' in obj:check(m['id']+' tender page complete',len(items)==obj['pageInfo']['total'])
        for tender in items:
            if dt(tender['timeInterval']['from'])!=a or dt(tender['timeInterval']['to'])!=b:outside+=1;continue
            tc=tender['tenderCode']
            if tc in seen_cap:continue
            seen_cap.add(tc);kept+=1
            for name,value in tender.get('activityTimingList',{}).items():events.append(dict(source_id=m['id'],tender=tc,event=name,source_time=value,event_time_utc=value,historical_publication_verified=False,comment='official current event field; archived availability/revisions not proved'))
            for service in tender['tenderServiceList']:
                product=service['serviceCode'];source_rr=service['tenderStatistics']['timeIntervalList'];hours=int((b-a).total_seconds()/3600)
                rr=[r for r in source_rr if dt(r['timeInterval']['from'])>=a and dt(r['timeInterval']['to'])<=b]
                anomaly=len(source_rr)!=hours or len(rr)!=hours
                if anomaly:source_anomalies.append(dict(issue='SQ02',source_id=m['id'],tender=tc,product=product,expected_native_hours=hours,raw_rows=len(source_rr),valid_in_tender_rows=len(rr),outside_rows=len(source_rr)-len(rr),missing_hours=hours-len(rr),handling='outside rows retained in raw only; missing rows not filled; DST capacity series not full approved input'))
                check(tc+' '+product+' hourly continuity',all(dt(r['timeInterval']['from'])==a+i*timedelta(hours=1) and dt(r['timeInterval']['to'])==a+(i+1)*timedelta(hours=1) for i,r in enumerate(rr)))
                for r in rr:capacity.append(dict(source_id=m['id'],raw_file_hash=m['sha256'],date=day,tender=tc,product_direction=product,price_scheme=tender['priceScheme'],demand_mw=r.get('tenderDemand'),satisfied_ratio=r.get('tenderSatisfiedDemand'),source_tender_price=r.get('tenderPrice'),source_average_offered_price=r.get('averageOfferedPrice'),source_average_accepted_price=r.get('averageAcceptedPrice'),source_price_unit='LEI (UI); denominator not inferred',**norm(r['timeInterval']['from'],r['timeInterval']['to'])))
                coverage.append(dict(dataset='D05',sample=day,product=product,expected=hours,actual=len(rr),numeric=sum(r.get('averageAcceptedPrice') is not None for r in rr),status=('SOURCE_DST_ANOMALY;' if anomaly else '')+'DESCRIPTIVE_ONLY;pay-as-bid mean not station price',source_ids=m['id'],native_timezone='EET/EEST',known_before_decision=False))
                contracted.append(dict(tender=tc,product=product,source_id=m['id'],raw_contracted_power=service.get('contractedPower')))
        m.update(parse_status='PARSED_TENDERS_LOCAL_DAY_FILTERED',record_count=len(items),numeric_record_count=kept,source_timezone='EET/EEST',resolution_minutes=60,actual_time_range=[iso(a),iso(b)],unit='MW; ratio; LEI incomplete price dimension',notes=f'kept={kept}; adjacent delivery tenders excluded={outside}; duplicate detail/list sources selected once')
csvout('system_series_samples.csv',series);csvout('capacity_samples.csv',capacity);csvout('tender_event_samples.csv',events);dump(OUT/'contracted_power_sample_structure.json',contracted);dump(WORK/'series_checks.json',jsonqa)
for report in [p[:-1] for p in accepted_prefixes]:
    check(report+' seven designed sample days',all((report,day) in seen_series for day in DAYS))

# Curves: preserve mixed PT15/PT30/PT60 products; do not sum cumulative points.
curve_meta=[];curve_examples=[]
cm=byid.get('CURVES_XML_2026-08-31')
if cm and cm.get('raw_file'):
    cr=ET.fromstring(text(cm));series_xml=cr.findall('AggregatedOrderTimeSeries');total_points=0
    for ts in series_xml:
        tid=ts.find('TimeSeriesIdentification').get('v')
        for side in ['SupplyCurve','DemandCurve']:
            for period in ts.findall(side+'/Period'):
                interval=period.find('TimeInterval').get('v');resolution=period.find('Resolution').get('v');minutes=int(re.search(r'PT(\d+)M',resolution)[1]);a,b=map(dt,interval.split('/'));items=period.findall('Interval');expected=int((b-a).total_seconds()/(60*minutes))
                check('curve '+side+' '+resolution+' positions',[int(x.find('Pos').get('v')) for x in items]==list(range(1,expected+1)))
                n=sum(len(x.findall('Point')) for x in items);total_points+=n
                curve_meta.append(dict(source_id=cm['id'],series_id=tid,side=side,resolution=resolution,intervals=len(items),points=n,source_unit_quantity=ts.find('MeasureUnitQuantity').get('v'),source_price_denom=ts.find('MeasureUnitPrice').get('v'),currency=ts.find('Currency').get('v'),document_creation_time=cr.find('CreationDateTime').get('v'),document_version=cr.find('DocumentVersion').get('v'),publication_time='',quality_flag='AGGREGATED;NO_GENERATING_UNIT_ID;CREATION_IS_NOT_PUBLICATION'))
                for item in items:
                    pos=int(item.find('Pos').get('v'));pts=item.findall('Point');seq=[int(p.find('SeqNr').get('v')) for p in pts]
                    check('curve point sequence '+side+resolution+str(pos),seq==list(range(1,len(seq)+1)))
                    for point in pts:
                        Decimal(point.find('Qty').get('v'));Decimal(point.find('PriceAmount').get('v'))
                    if pos==1:
                        for point in pts[:5]:curve_examples.append(dict(source_id=cm['id'],side=side,product=resolution,pos=pos,seq=point.find('SeqNr').get('v'),source_qty_mw=point.find('Qty').get('v'),source_price_eur_mwh=point.find('PriceAmount').get('v'),**norm(a,a+timedelta(minutes=minutes))))
    cm.update(parse_status='PARSED_CURVE_STRUCTURE_AND_POINTS',record_count=total_points,numeric_record_count=total_points,source_timezone='explicit UTC / CET delivery day',resolution_minutes=[15,30,60],unit='MAW (MW); EUR/MWH; aggregate curve coordinates',currency='EUR',actual_time_range=cr.find('DocumentTimeInterval').get('v').split('/'),revision='DocumentVersion='+cr.find('DocumentVersion').get('v')+'; no archived publication proof')
    pm=byid['CURVES_PDF_2026-08-31']
    from pypdf import PdfReader
    pdf=PdfReader(ROOT/pm['raw_file']);da_curve=[r for r in da if r['source_market_date']=='2026-08-31']
    pdfprices=[re.search(r'Price:\s*([+-]?\d+\.\d+)\s*EUR/MWh',p.extract_text())[1] for p in pdf.pages]
    check('curve PDF 96 DA prices same-source match',len(pdfprices)==96 and all(Decimal(p)==Decimal(r['price_eur_mwh']) for p,r in zip(pdfprices,da_curve)))
    pm.update(parse_status='PARSED_96_CHART_PRICE_LABELS',record_count=96,numeric_record_count=96,source_timezone='CET/CEST',resolution_minutes=15,unit='chart price EUR/MWh; chart quantity MW',currency='EUR')
csvout('curve_structure_samples.csv',curve_meta);csvout('curve_point_examples.csv',curve_examples)

idct=[]
for m in manifest:
    if not m['id'].startswith('IDCT_') or m.get('detected_format')!='HTML':continue
    doc=html.fromstring(text(m));tabs=[tb for tb in doc.xpath('//table') if '15 min Trades' in ' '.join(tb.text_content().split()) and len(tb.xpath('.//tr'))>20]
    if not tabs:continue
    tb=min(tabs,key=lambda x:len(x.xpath('.//tr')));period=''
    for idx,tr in enumerate(tb.xpath('.//tr')):
        cells=[' '.join(c.text_content().split()) for c in tr.xpath('./td')]
        if len(cells)==4 and cells[1] in ('buy','sell'):period=cells[0];cells=cells[1:]
        if len(cells)==3 and cells[0] in ('buy','sell'):
            idct.append(dict(source_id=m['id'],raw_file_hash=m['sha256'],source_trade_date='2026-08-31',source_delivery_label=period,source_side=cells[0],price_eur_mwh=cells[1],volume_mwh=cells[2],trade_time='',source_trade_id='',delivery_start_utc='',quality_flag='DESCRIPTIVE_ONLY;trade timestamp and delivery-day mapping absent'))
    m.update(parse_status='PARSED_TRADES_NO_ASOF_OR_FULL_DELIVERY_DATE',record_count=len(idct),numeric_record_count=len(idct),source_timezone='needs full dated contract interpretation',resolution_minutes=15,unit='EUR/MWh; MWh',currency='EUR')
csvout('idct_trade_samples.csv',idct)

fx=[]
for m in manifest:
    if not m['id'].startswith('FX_') or not m.get('raw_file'):continue
    rr=list(csv.DictReader(io.StringIO(text(m))));check(m['id']+' FX dimensions',all(r['CURRENCY']=='RON' and r['CURRENCY_DENOM']=='EUR' and r['FREQ']=='D' for r in rr))
    for r in rr:fx.append(dict(source_id=m['id'],raw_file_hash=m['sha256'],date=r['TIME_PERIOD'],source_value=r['OBS_VALUE'],unit='RON per 1 EUR',purpose='RESEARCH_DISPLAY_REFERENCE_ONLY',publication_time='',revision_time='',quality_flag='NOT_BNR_SETTLEMENT_RATE;no weekend filling'))
    m.update(parse_status='PARSED_REFERENCE_FX',record_count=len(rr),numeric_record_count=len(rr),unit='RON per EUR',currency='RON/EUR',source_timezone='daily reference date; intraday publication not in sample')
csvout('fx_reference_samples.csv',fx)

alignment=[];da_qh=defaultdict(dict)
for r in da:
    if r['source_market_date'] not in DAYS:continue
    a,b=dt(r['delivery_start_utc']),dt(r['delivery_end_utc'])
    while a<b:da_qh[r['source_market_date']][iso(a)]=r;a+=timedelta(minutes=15)
for day in DAYS:
    load={r['delivery_start_utc'] for r in series if r['source_market_date']==day and r['report']=='dailyConsumptionOverview' and r['product_direction']=='grossRealizedConsumption' and r['source_value'] is not None}
    act={r['delivery_start_utc'] for r in series if r['source_market_date']==day and r['report']=='activatedBalancingEnergyOverview' and r['product_direction']=='aFRR_Up' and r['source_value'] is not None}
    keys=set(da_qh[day]);common=keys & load & act
    expected_common=int((bounds(day,CET)[1]-bounds(day,RO)[0]).total_seconds()/900)-8
    check(day+' UTC intersection is one-hour shorter',len(common)==expected_common,dict(intersection=len(common),expected=expected_common))
    alignment.append(dict(date=day,da_physical_qh=len(keys),load_qh=len(load),activation_afrr_up_qh=len(act),common_utc_qh=len(common),da_native_start_utc=iso(bounds(day,CET)[0]),tso_native_start_utc=iso(bounds(day,RO)[0]),exclusion='one hour at each different-day boundary; adjacent day needed for full local-day join',joint_market_income_allowed=False))
csvout('utc_alignment_checks.csv',alignment)

extremes=[]
for r in da:
    if Decimal(r['price_eur_mwh'])<0 or Decimal(r['price_eur_mwh'])==0:extremes.append(dict(kind='DA_NEGATIVE' if Decimal(r['price_eur_mwh'])<0 else 'DA_ZERO_PRICE',source_id=r['source_id'],time=r['delivery_start_utc'],field='price_eur_mwh',value=r['price_eur_mwh'],unit='EUR/MWh'))
act_pair=defaultdict(dict)
for r in series:
    if r['report']=='activatedBalancingEnergyOverview' and r['product_direction'] in ['aFRR_Up','aFRR_Down']:act_pair[(r['source_id'],r['delivery_start_utc'])][r['product_direction']]=r['source_value']
for (sid,t),vs in act_pair.items():
    if all(vs.get(k) is not None for k in ['aFRR_Up','aFRR_Down']):
        if vs['aFRR_Up']>0 and vs['aFRR_Down']>0:extremes.append(dict(kind='AFRR_BOTH_DIRECTIONS_WITHIN_QH',source_id=sid,time=t,field='aFRR_Up/aFRR_Down',value=str(vs),unit='MWh; not proof of same-instant activation'))
        if vs['aFRR_Up']==0 or vs['aFRR_Down']==0:extremes.append(dict(kind='AFRR_DIRECTION_REAL_ZERO',source_id=sid,time=t,field='aFRR_Up/aFRR_Down',value=str(vs),unit='MWh'))
ar=[r for r in series if r['report']=='activatedBalancingEnergyOverview' and r['product_direction'] in ['aFRR_Up','aFRR_Down'] and r['source_value'] is not None]
if ar:
    r=max(ar,key=lambda r:Decimal(str(r['source_value'])))
    extremes.append(dict(kind='AFRR_MAX_WITHIN_SEVEN_SAMPLED_DAYS_ONLY',source_id=r['source_id'],time=r['delivery_start_utc'],field=r['product_direction'],value=r['source_value'],unit='MWh; selected strong sample, not full-period extreme'))
csvout('observed_events.csv',extremes)
csvout('source_anomalies.csv',source_anomalies)
csvout('coverage_matrix.csv',coverage)
dump(OUT/'raw_manifest.json',manifest)
dump(WORK/'verification.json',dict(status='PASS' if not errors else 'FAIL',errors=errors,source_anomaly_records=len(source_anomalies),checks=len(checks),raw_attempts=len(manifest),downloaded=sum(bool(m.get('raw_file')) for m in manifest),da_days=len(selected),da_native_rows=len(da),capacity_rows=len(capacity),system_field_rows=len(series),idct_rows=len(idct),fx_rows=len(fx),scope='evidence integrity and sample transformations; source defects separately disclosed; not full-period, legal, model, ASOF or revenue approval',detail=checks))
print(json.dumps(dict(errors=errors,checks=len(checks),da_days=len(selected),da_rows=len(da),capacity_rows=len(capacity),system_rows=len(series),idct_rows=len(idct),fx_rows=len(fx)),ensure_ascii=False))
