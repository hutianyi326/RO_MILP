from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
import json
ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent
RO=ZoneInfo('Europe/Bucharest');CET=ZoneInfo('Europe/Brussels')
BASE='https://newmarkets.transelectrica.ro/usy-durom-publicreportg01/00121002500000000000000000000100/publicReport/'
samples=json.loads((ROOT/'countries/RO/data_samples_20260930/raw_manifest.json').read_text(encoding='utf-8-sig'))
if isinstance(samples,dict):samples=samples.get('sources',samples.get('files',[]))
selected={}
for m in samples:
    if m.get('dataset')=='D02' and m.get('detected_format')=='CSV' and m.get('parse_status')=='PARSED':
        selected[m['id'][3:13]]=m
reuse=[];da=[]
day=date(2024,12,31)
while day<=date(2026,8,31):
    key=day.isoformat()
    if key in selected:reuse.append(selected[key])
    else:
        resolution=60 if day<date(2025,10,1) else 15
        da.append(dict(id='DA_'+key,dataset='D02',publisher='OPCOM',title='Mcp and Traded Volume native CSV',url=f'https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv/{day:%d/%m/%Y}/en?resolution={resolution}',source_date=key,resolution_minutes=resolution,source_timezone='Europe/Brussels',scope='observation boundary' if day.year==2024 else 'full-period research native market date'))
    day+=timedelta(days=1)
requests=[]
for year,month in [(y,m) for y in [2025,2026] for m in range(1,13) if (y,m)<=(2026,8)]:
    next_year,next_month=(year+1,1) if month==12 else (year,month+1)
    key=f'{year}-{month:02}'
    for report,dataset,tz in [('dailyConsumptionOverview','D08-D16',RO),('activatedBalancingEnergyOverview','D06',RO),('scheduledExchanges','D11',CET),('tenderStatistics','D05',RO)]:
        a=datetime(year,month,1,tzinfo=tz).astimezone(timezone.utc)
        b=datetime(next_year,next_month,1,tzinfo=tz).astimezone(timezone.utc)
        params={'timeInterval.from':a.isoformat().replace('+00:00','Z'),'timeInterval.to':b.isoformat().replace('+00:00','Z'),'pageInfo.pageSize':3000,'pageInfo.pageIndex':0}
        requests.append(dict(id=report+'_'+key,dataset=dataset,publisher='Transelectrica / DAMAS II',title=report,report=report,url=BASE+report+'?'+urlencode(params),parameters=params,month=key,source_timezone=tz.key,requested_start_utc=params['timeInterval.from'],requested_end_utc=params['timeInterval.to'],scope='native monthly public report; unversioned ex-post snapshot'))
for filename,data in [('requests_da.json',da),('requests_system.json',requests),('reused_samples.json',reuse),('requests_pilot.json',[da[1],requests[0],requests[1],requests[2],requests[3]])]:
    p=WORK/filename
    if p.exists():raise RuntimeError('Request list exists: '+filename)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'DA_new':len(da),'DA_reuse':len(reuse),'monthly_system':len(requests)},ensure_ascii=False))
