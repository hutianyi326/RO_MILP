"""Fetch public ENTSO-E sample; read token in memory, never persist request secrets."""
from pathlib import Path
import re, json, hashlib, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
secret_text = (ROOT / 'data/API_Key.md').read_text(encoding='utf-8-sig')
section = re.search(r'(?is)##\s*entsoe[^\n]*\n(.*?)(?=\n##|\Z)', secret_text).group(1)
tokens = re.findall(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b', section)
assert len(tokens) == 1, 'Expected one ENTSO-E token'
token = tokens[0]
base = 'https://web-api.tp.entsoe.eu/api'
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
dest = OUT / 'sources' / stamp
dest.mkdir(parents=True, exist_ok=False)
receipts = []
queries = [('bids_FCR', {'documentType':'A15','processType':'A52','area_Domain':'10YRO-TEL------P'}),
           ('bids_aFRR', {'documentType':'A15','processType':'A51','area_Domain':'10YRO-TEL------P'}),
           ('contracted_FCR', {'documentType':'A81','businessType':'B95','processType':'A52','type_MarketAgreement.type':'A01','controlArea_Domain':'10YRO-TEL------P'}),
           ('contracted_aFRR', {'documentType':'A81','businessType':'B95','processType':'A51','type_MarketAgreement.type':'A01','controlArea_Domain':'10YRO-TEL------P'})]
for name, params in queries:
    params.update(periodStart='202608302100',periodEnd='202608312100')
    url = base + '?' + urllib.parse.urlencode(dict(params, securityToken=token))
    req = urllib.request.Request(url,headers={'User-Agent':'RO-MILP-research/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            body=response.read(); status=response.status; ctype=response.headers.get('Content-Type','')
    except urllib.error.HTTPError as exc:
        body=exc.read(); status=exc.code; ctype=exc.headers.get('Content-Type','')
    except Exception as exc:
        receipts.append(dict(name=name,status='network_error',error_type=type(exc).__name__,params=params))
        print(name,'network_error',type(exc).__name__)
        continue
    # Defend against error responses reflecting the request URL/token.
    assert token.encode() not in body, 'Reflected credential response not saved'
    suffix='.zip' if body[:2]==b'PK' else '.xml'
    file=dest/(name+suffix); file.write_bytes(body)
    receipts.append(dict(name=name,endpoint=base,params=params,status=status,content_type=ctype,
                         file=file.name,bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
    print(name,status,len(body),ctype)
(dest/'receipts.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
print('Saved',dest)
