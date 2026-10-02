"""Bounded public GET downloads for three sample months, no account or credentials."""
from pathlib import Path
from datetime import date, timedelta, datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen, Request
import calendar, json, hashlib
ROOT=Path(__file__).resolve().parents[2]
RAW=ROOT/'data/raw/RO/samples/20260930'
def fetch(day):
    sid='DA_'+day.isoformat(); folder=RAW/sid; folder.mkdir(parents=True,exist_ok=True)
    receipt=folder/'receipt.json'
    if receipt.exists():return sid+' existing'
    res=60 if day<date(2025,10,1) else 15
    url=f'https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv/{day:%d/%m/%Y}/en?resolution={res}'
    meta=dict(id=sid,dataset='D02',url=url,method='GET',parameters=None,requested_scope=f'{day} native PT{res}',retrieved_utc=datetime.now(timezone.utc).isoformat(),status='FAILED',error=None)
    try:
        with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0 RomaniaPublicDataResearch'}),timeout=35) as r:
            data=r.read();meta.update(http_status=r.status,resolved_url=r.url,content_type=r.headers.get('Content-Type'))
        path=folder/'original.csv'
        with path.open('xb') as f:f.write(data)
        meta.update(status='HTTP_OK_UNPARSED',raw_file=path.relative_to(ROOT).as_posix(),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    except Exception as e:meta['error']=str(e)
    receipt.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
    return sid+' '+meta['status']
days=[date(y,m,d) for y,m in [(2025,1),(2025,10),(2026,8)] for d in range(1,calendar.monthrange(y,m)[1]+1)]
with ThreadPoolExecutor(max_workers=3) as pool:
    for result in pool.map(fetch,days):print(result,flush=True)
