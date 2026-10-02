"""Immutable, bounded, research-only downloads; public official endpoints only."""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen
import argparse, hashlib, json, time

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent
RAW=ROOT/'data/raw/RO/full_period/20261001'

def collect(req):
    attempts=[]
    for attempt in range(1,4):
        folder=RAW/(req['id']+f'__a{attempt}')
        receipt=folder/'receipt.json'
        if receipt.exists():
            old=json.loads(receipt.read_text(encoding='utf-8'))
            attempts.append(old)
            if old['status']=='HTTP_OK_UNPARSED':return old
            continue
        folder.mkdir(parents=True,exist_ok=True)
        meta={**req,'attempt':attempt,'method':'GET','retrieved_utc':datetime.now(timezone.utc).isoformat(),
              'status':'FAILED','publication_time':None,'revision_time':None}
        try:
            with urlopen(Request(req['url'],headers={'User-Agent':'Mozilla/5.0 RomaniaResearchPublicDownload'}),timeout=25) as response:
                body=response.read()
                meta.update(http_status=response.status,resolved_url=response.url,content_type=response.headers.get('Content-Type'))
            ext='pdf' if body.startswith(b'%PDF') else 'xls' if body.startswith(bytes.fromhex('d0cf11e0a1b11ae1')) else 'zip' if body.startswith(b'PK') else 'json' if body.lstrip().startswith(b'{') else 'csv' if body.startswith(b'"Mcp') or body.startswith(b'KEY,') else 'xml' if body.lstrip().startswith(b'<?xml') else 'html'
            raw=folder/f'original.{ext}'
            with raw.open('xb') as f:f.write(body)
            meta.update(status='HTTP_OK_UNPARSED',raw_file=raw.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(body).hexdigest(),bytes=len(body),detected_format=ext)
        except Exception as exc:
            meta['error']=f'{type(exc).__name__}: {exc}'
        with receipt.open('x',encoding='utf-8') as f:json.dump(meta,f,ensure_ascii=False,indent=2)
        attempts.append(meta)
        if meta['status']=='HTTP_OK_UNPARSED':return meta
        if attempt<3:time.sleep(attempt*2)
    return attempts[-1]

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('requests')
    parser.add_argument('--workers',type=int,default=3)
    args=parser.parse_args()
    reqs=json.loads((WORK/args.requests).read_text(encoding='utf-8'))
    done=[]
    with ThreadPoolExecutor(max_workers=min(args.workers,3)) as pool:
        jobs={pool.submit(collect,req):req for req in reqs}
        for future in as_completed(jobs):
            result=future.result();done.append(result)
            if len(done)%10==0 or result['status']=='FAILED' or len(done)==len(reqs):
                print(json.dumps({'complete':len(done),'total':len(reqs),'last_id':result['id'],'last_status':result['status'],'failed':sum(x['status']=='FAILED' for x in done)},ensure_ascii=False),flush=True)
    result_path=WORK/(Path(args.requests).stem+'_results.json')
    if result_path.exists():
        result_path=WORK/(Path(args.requests).stem+'_results_'+datetime.now(timezone.utc).strftime('%H%M%S')+'.json')
    result_path.write_text(json.dumps(sorted(done,key=lambda x:x['id']),ensure_ascii=False,indent=2),encoding='utf-8')
