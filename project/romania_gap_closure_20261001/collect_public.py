"""Immutable, bounded, research-only downloads; public official endpoints only."""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen, build_opener, HTTPCookieProcessor
from urllib.parse import urlencode, quote
from http.cookiejar import CookieJar
import re, threading
import argparse, hashlib, json, time

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent
RAW=ROOT/'data/raw/RO/gap_closure/20261001'
SESSION=threading.local()

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
            headers={'User-Agent':'Mozilla/5.0 RomaniaResearchPublicDownload'}
            request_url=quote(req['url'],safe=':/?&=+%#')
            if req.get('body'):
                if not hasattr(SESSION,'forms'):SESSION.forms={}
                cached=SESSION.forms.get(request_url)
                if cached:
                    opener,form_body,form_path=cached
                else:
                    opener=build_opener(HTTPCookieProcessor(CookieJar()))
                    with opener.open(Request(request_url,headers=headers),timeout=25) as form:
                        form_body=form.read()
                    form_path=folder/'form_original.html'
                    with form_path.open('xb') as f:f.write(form_body)
                    SESSION.forms[request_url]=(opener,form_body,form_path)
                meta.update(form_file=form_path.relative_to(ROOT).as_posix(),form_sha256=hashlib.sha256(form_body).hexdigest(),anonymous_session_reused=bool(cached))
                fields=dict(req['body']);match=re.search(rb'name="_token"\s+value="([^"]+)"',form_body)
                if match:fields['_token']=match.group(1).decode('ascii')
                headers.update({'Content-Type':'application/x-www-form-urlencoded','Referer':req['url']})
                request=Request(request_url,data=urlencode(fields).encode('utf-8'),headers=headers,method='POST')
                response_context=opener.open(request,timeout=25);meta.update(method='POST',public_anonymous_csrf_used=bool(match))
            else:
                response_context=urlopen(Request(request_url,headers=headers),timeout=25)
            with response_context as response:
                body=response.read()
                meta.update(http_status=response.status,resolved_url=response.url,content_type=response.headers.get('Content-Type'))
            ext='pdf' if body.startswith(b'%PDF') else 'xls' if body.startswith(bytes.fromhex('d0cf11e0a1b11ae1')) else 'zip' if body.startswith(b'PK') else 'json' if body.lstrip().startswith(b'{') else 'csv' if body.startswith(b'"Mcp') or body.startswith(b'KEY,') else 'xml' if body.lstrip().startswith(b'<?xml') else 'html'
            raw=folder/f'original.{ext}'
            with raw.open('xb') as f:f.write(body)
            meta.update(status='HTTP_OK_UNPARSED',raw_file=raw.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(body).hexdigest(),bytes=len(body),detected_format=ext)
        except Exception as exc:
            meta['error']=f'{type(exc).__name__}: {exc}'
            if req.get('body') and hasattr(SESSION,'forms'):SESSION.forms.pop(request_url,None)
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
