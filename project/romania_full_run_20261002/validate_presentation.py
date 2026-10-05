"""Independent standard-library CSV/Decimal checks for ES-style RO aggregation."""
import csv,json,hashlib,argparse,math
from pathlib import Path
from collections import defaultdict
from decimal import Decimal
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

FIELDS={'DA':'da_eur','FCR_cap':'fcr_capacity_eur','cap_up':'afrr_up_capacity_eur','cap_down':'afrr_down_capacity_eur','act_up':'afrr_up_activation_eur','act_down':'afrr_down_activation_eur'}
ZERO=Decimal(0);RO=ZoneInfo('Europe/Bucharest')
def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def validate(run,report):
    checks=0;max_error=0.
    def compare(a,b,tol=.001):
        nonlocal checks,max_error
        error=abs(float(a)-float(b));assert math.isfinite(error) and error<=tol,(a,b,error)
        checks+=1;max_error=max(max_error,error)
    source=read_csv(run/'executed_qh.csv');months=defaultdict(lambda:defaultdict(Decimal));years=defaultdict(lambda:defaultdict(Decimal));days=defaultdict(lambda:defaultdict(Decimal));hourcash=defaultdict(lambda:defaultdict(Decimal));hourmeta={};totals=defaultdict(Decimal)
    for row in source:
        utc=datetime.fromisoformat(row['delivery_start_utc'].replace('Z','+00:00'));local=utc.astimezone(RO);day=local.strftime('%Y-%m-%d');month=day[:7];year=day[:4];hour=utc.replace(minute=0);quarter='Q'+str((local.month-1)//3+1)
        assert row['local_date']==day
        hourmeta[hour]=(month,quarter,local.hour)
        for g in (months[month],years[year],days[day]):
            for m,f in FIELDS.items():g[m]+=Decimal(row[f])
            g['efc']+=Decimal(row['efc']);g['count']+=1
            for m,field in [('da','da_data_valid'),('afrr','afrr_hour_data_valid'),('fcr','fcr_hour_data_valid')]:g[m+'_valid']+=row[field]=='True'
        for m,f in FIELDS.items():hourcash[hour][m]+=Decimal(row[f]);totals[m]+=Decimal(row[f])
        hourcash[hour]['count']+=1
    assert len(source)==58364 and len(months)==20 and len(days)==608 and len(hourcash)==14591
    for value in hourcash.values():assert value['count']==4
    for filename,key,groups in [('monthly.csv','month',months),('annual.csv','year',years),('daily.csv','day',days)]:
        exported=read_csv(report/filename);assert len(exported)==len(groups)
        for row in exported:
            data=groups[row[key]];total=sum(data[m] for m in FIELDS)
            for m in FIELDS:
                compare(Decimal(row[m+'_kEUR'])*1000,data[m]);compare(Decimal(row[m+'_kEUR_per_MW'])*100000,data[m])
            compare(Decimal(row['total_kEUR'])*1000,total);compare(Decimal(row['total_kEUR_per_MW'])*100000,total)
            compare(row['efc'],data['efc'],1e-7);assert int(row['executed_qh'])==int(row['total_qh'])==data['count']
            for m in ('da','afrr','fcr'):
                assert int(row[m+'_valid_qh'])==data[m+'_valid'];compare(row[m+'_data_coverage'],data[m+'_valid']/data['count'],1e-10)
    for row in read_csv(report/'market_totals.csv'):
        m=row['market'];compare(Decimal(row['kEUR'])*1000,totals[m]);compare(row['share_pct'],totals[m]/sum(totals.values())*100,1e-8)
    for row in read_csv(report/'monthly_market_shares.csv'):
        data=months[row['month']];total=sum(data[m] for m in FIELDS)
        for m in FIELDS:compare(row[m+'_share_pct'],data[m]/total*100,1e-8)
    for filename,keys in [('hourly.csv',('hour',)),('quarterly_hourly.csv',('quarter','hour')),('monthly_hourly_heatmap.csv',('month','hour'))]:
        groups=defaultdict(lambda:defaultdict(Decimal))
        for h,data in hourcash.items():
            month,quarter,hour=hourmeta[h];meta={'month':month,'quarter':quarter,'hour':str(hour)};key=tuple(meta[k] for k in keys)
            for m in FIELDS:groups[key][m]+=data[m]
            groups[key]['count']+=1
        exported=read_csv(report/filename);assert len(exported)==len(groups)
        for row in exported:
            data=groups[tuple(row[k] for k in keys)];assert int(row['sample_hours'])==data['count']
            for m in FIELDS:compare(row[m+'_kEUR_per_MW'],data[m]/data['count']/100000,1e-10)
            compare(row['total_kEUR_per_MW'],sum(data[m] for m in FIELDS)/data['count']/100000,1e-10)
    rolling=read_csv(report/'rolling_12m.csv');assert len(rolling)==9
    monthkeys=sorted(months)
    for i,row in enumerate(rolling):
        window=monthkeys[i:i+12];assert row['window_start']==window[0] and row['window_end']==window[-1]
        total=sum(months[mo][m] for mo in window for m in FIELDS);compare(Decimal(row['total_kEUR'])*1000,total);compare(Decimal(row['total_kEUR_per_MW'])*100000,total)
        compare(row['efc'],sum(months[mo]['efc'] for mo in window),1e-7)
    manifest=read(report/'report_manifest.json')
    for filename,value in manifest['files'].items():assert sha(report/filename)==value
    assert manifest['run_manifest_sha256']==sha(run/'manifest.json')
    for filename,value in manifest['run_files'].items():assert sha(run/filename)==value
    svgs=list(report.glob('*.svg'));assert len(svgs)==9
    for path in svgs:assert ET.parse(path).getroot().tag.endswith('svg')
    # Clock samples are actual hours, not 608 uniform local clock days.
    autumn=[h for h,meta in hourmeta.items() if h.astimezone(RO).strftime('%Y-%m-%d')=='2025-10-26' and meta[2]==3]
    spring=[h for h,meta in hourmeta.items() if h.astimezone(RO).strftime('%Y-%m-%d')=='2025-03-30' and meta[2]==3]
    assert len(autumn)==2 and len(spring)==0
    return {'status':'PASS','numeric_comparisons':checks,'max_absolute_error_across_mixed_units':max_error,'formal_qh':len(source),'monthly_rows':len(months),'annual_rows':len(years),'daily_rows':len(days),'complete_actual_hours':len(hourcash),'rolling_12m_rows':len(rolling),'svg_count':len(svgs),'dst_repeated_hour_samples':2,'dst_skipped_hour_samples':0,'report_manifest_sha256':sha(report/'report_manifest.json'),'run_manifest_sha256':sha(run/'manifest.json'),'script_sha256':sha(__file__),'note':'Money compares in EUR within 0.001 after report CSV decimal rounding; EFC 1e-7, normalized hourly means 1e-10. SVG well-formedness plus manual visual check; no chart pixel oracle.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=validate(a.run,a.report);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
