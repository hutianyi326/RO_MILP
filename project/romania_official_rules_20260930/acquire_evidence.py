"""Read-only HTTP acquisition of public rule evidence, immutable originals."""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import argparse, hashlib, json, re, shutil, zipfile, io
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
RAW = ROOT / 'data/raw/RO/rules/20260930'

class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.links=[]; self.skip=0; self.anchor=None
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if tag in ('script','style'): self.skip+=1
        if tag=='a': self.anchor=[d.get('href',''), []]
        if tag in ('p','div','br','tr','li','h1','h2','h3','h4'): self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style'): self.skip=max(0,self.skip-1)
        if tag=='a' and self.anchor:
            self.links.append((self.anchor[0], ' '.join(self.anchor[1]))); self.anchor=None
        if tag in ('p','div','tr','li','h1','h2','h3','h4'): self.parts.append('\n')
    def handle_data(self,data):
        if not self.skip:
            self.parts.append(data)
            if self.anchor: self.anchor[1].append(data.strip())

def acquire(row):
    sid,url=row['id'],row['url']; directory=RAW/sid; directory.mkdir(parents=True,exist_ok=True)
    meta_path=directory/'metadata.json'
    if meta_path.exists(): return json.loads(meta_path.read_text(encoding='utf8'))
    timestamp=datetime.now(timezone.utc).isoformat()
    try:
        pending=directory/'download.json'
        if pending.exists():
            info=json.loads(pending.read_text(encoding='utf-8-sig')); data=(directory/info['filename']).read_bytes()
            ctype=info['content_type']; resolved=info['resolved_url']; status=info['status']; timestamp=info['retrieved_utc']
        else:
            with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0 OfficialRulesResearch'}), timeout=40) as response:
                data=response.read(); ctype=response.headers.get('Content-Type',''); resolved=response.url; status=response.status
        resolved=urljoin(url,resolved or url)
        ext='pdf' if data.startswith(b'%PDF') else ('docx' if data.startswith(b'PK') and '.docx' in url.lower() else ('zip' if data.startswith(b'PK') else 'html'))
        path=directory/f'original.{ext}'
        if not path.exists():
            with path.open('xb') as stream: stream.write(data)
        elif path.read_bytes()!=data: raise ValueError('Immutable evidence conflict')
        derived=WORK/'extracted'; derived.mkdir(exist_ok=True)
        if ext=='pdf':
            from pypdf import PdfReader
            reader=PdfReader(path); text='\n\n'.join(f'=== PDF PAGE {i+1} ===\n'+(page.extract_text() or '') for i,page in enumerate(reader.pages)); links=[]
        elif ext in ('docx','zip'):
            sections=[]
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                for name in archive.namelist():
                    content=archive.read(name)
                    if name=='word/document.xml':
                        root=ElementTree.fromstring(content)
                        sections.append('\n'.join(''.join(p.itertext()) for p in root.iter() if p.tag.endswith('}p')))
                    elif name.lower().endswith('.docx'):
                        with zipfile.ZipFile(io.BytesIO(content)) as nested:
                            root=ElementTree.fromstring(nested.read('word/document.xml'))
                            sections.append('=== ARCHIVE MEMBER '+name+' ===\n'+'\n'.join(''.join(p.itertext()) for p in root.iter() if p.tag.endswith('}p')))
                    elif name.lower().endswith('.pdf'):
                        from pypdf import PdfReader
                        reader=PdfReader(io.BytesIO(content))
                        sections.append('=== ARCHIVE MEMBER '+name+' ===\n'+'\n'.join(f'=== PDF PAGE {i+1} ===\n'+(p.extract_text() or '') for i,p in enumerate(reader.pages)))
            text='\n\n'.join(sections); links=[]
        else:
            match=re.search(br'charset=["\s]*([\w-]+)',data[:10000],re.I)
            encoding=match.group(1).decode() if match else 'utf-8'
            source=data.decode(encoding,errors='replace'); parser=Parser(); parser.feed(source)
            text='\n'.join(x.strip() for x in ''.join(parser.parts).splitlines() if x.strip())
            links=[{'text':t,'url':urljoin(resolved,h)} for h,t in parser.links if h]
        (derived/f'{sid}.txt').write_text(text,encoding='utf8')
        (derived/f'{sid}.links.json').write_text(json.dumps(links,ensure_ascii=False,indent=2),encoding='utf8')
        meta={**row,'resolved_url':resolved,'retrieved_utc':timestamp,'access_date':'2026-09-30','status':status,'content_type':ctype,'path':str(path.relative_to(ROOT)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'extracted_characters':len(text)}
        meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
        return meta
    except Exception as e:
        return {**row,'retrieved_utc':timestamp,'error':str(e)}

def main():
    arg=argparse.ArgumentParser(); arg.add_argument('sources'); arg.add_argument('--offline',action='store_true'); options=arg.parse_args()
    rows=json.loads(Path(options.sources).read_text(encoding='utf-8-sig'))
    if options.offline: rows=[r for r in rows if (RAW/r['id']/'download.json').exists() or (RAW/r['id']/'metadata.json').exists()]
    with ThreadPoolExecutor(max_workers=6) as pool: result=list(pool.map(acquire,rows))
    output=WORK/(Path(options.sources).stem+'_receipt.json'); output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    for row in result: print(json.dumps({k:row[k] for k in ('id','status','bytes','extracted_characters','error') if k in row},ensure_ascii=False))

if __name__=='__main__': main()
