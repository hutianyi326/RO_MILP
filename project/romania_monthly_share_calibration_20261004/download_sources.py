"""Read-only official DAMAS downloads, with immutable versioned raw evidence."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
import hashlib, json, re, sys, time, urllib.request

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
OLD=REPO/'project/romania_entsoe_capacity_sample_20261004/supplier_calibration_aug2026'
HTML=REPO/'project/romania_external_benchmark_20261004/sources/fcr_info_sts_20261004.html'
KINDS=('ansContractPurchasedReserves','ansTenderResults')

def discover():
    links={}
    class Parser(HTMLParser):
        def handle_starttag(self,tag,attrs):
            if tag!='a':return
            href=dict(attrs).get('href',''); decoded=unquote(href)
            m=re.search(r'(ansContractPurchasedReserves|ansTenderResults)_[ +]*(\d{2})\.(\d{2})\.(\d{4})',decoded)
            correction=''
            if not m and re.search(r'(ansContractPurchasedReserves|ansTenderResults)_19\.12\.202/',decoded):
                m=re.search(r'(ansContractPurchasedReserves|ansTenderResults)_(\d{2})\.(\d{2})\.(\d{4})',decoded.replace('19.12.202/','19.12.2025/'))
                correction='URL filename truncates year to 202; official surrounding row labels 19.12.2025; workbook date must confirm'
            if not m:return
            d=f'{m[4]}-{m[3]}-{m[2]}'
            if not '2025-01-01'<=d<='2026-08-31':return
            key=(d,m[1]);url=urljoin('https://www.transelectrica.ro',href)
            assert key not in links or links[key]['url']==url
            links[key]=dict(date=d,kind=m[1],url=url,filename_note=correction)
    Parser().feed(HTML.read_text(encoding='utf-8'))
    days=[];d=date(2025,1,1)
    while d<=date(2026,8,31):days.append(str(d));d+=timedelta(days=1)
    assert set(links)=={(d,k) for d in days for k in KINDS}
    (ROOT/'source_inventory.json').write_text(json.dumps(list(links.values()),indent=2),encoding='utf-8')
    return links

def existing():
    found={}
    for base in (OLD,ROOT):
        for manifest in sorted((base/'sources').glob('*/receipts.json')):
            for r in json.loads(manifest.read_text(encoding='utf-8')):
                if r['status']=='ok':found[r['date'],r['kind']]=(manifest.parent/r['file'],r)
    return found

def run():
    links=discover();done=existing()
    pending=[r for key,r in sorted(links.items()) if key not in done]
    print('Required',len(links),'reusing',len(done),'pending',len(pending),flush=True)
    if not pending:return
    dest=ROOT/'sources'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');dest.mkdir(parents=True,exist_ok=False)
    def fetch(r):
        name=f"{r['kind']}_{r['date']}.xlsx";err=''
        for attempt in range(3):
            try:
                request=urllib.request.Request(r['url'],headers={'User-Agent':'Mozilla/5.0'})
                with urllib.request.urlopen(request,timeout=20) as res:data=res.read();ctype=res.headers.get('Content-Type','')
                assert data[:2]==b'PK' or data[:4]==bytes.fromhex('d0cf11e0'),'Not an Excel file'
                (dest/name).write_bytes(data)
                return dict(**r,file=name,status='ok',bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),content_type=ctype,attempts=attempt+1)
            except Exception as exc:
                err=type(exc).__name__+': '+str(exc)[:240]
                if attempt<2:time.sleep(attempt+1)
        return dict(**r,status='error',error_type=err,attempts=3)
    records=[]
    with ThreadPoolExecutor(max_workers=1) as pool:
        futures=[pool.submit(fetch,r) for r in pending]
        consecutive_errors=0
        for f in as_completed(futures):
            record=f.result();records.append(record)
            consecutive_errors=consecutive_errors+1 if record['status']!='ok' else 0
            if consecutive_errors>=3:
                for future in futures:future.cancel()
                print('Paused after three consecutive failed files; rerun later to resume',flush=True)
                break
            if len(records)%10==0:
                (dest/'receipts.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
                print('Retrieved',len(records),'/',len(pending),'failures',sum(x['status']!='ok' for x in records),flush=True)
    (dest/'receipts.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    print('Finished',len(records),'failures',sum(x['status']!='ok' for x in records),flush=True)

if __name__=='__main__':run()
