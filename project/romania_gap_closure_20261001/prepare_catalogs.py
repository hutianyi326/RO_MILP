from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, quote
import json,re,unicodedata
from datetime import datetime
from lxml import html
import pandas as pd

R=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent;O=R/'countries/RO/gap_closure_20261001'
receipts=[json.loads(p.read_text(encoding='utf-8')) for p in (R/'data/raw/RO/gap_closure/20261001').glob('*/receipt.json')]
def source(i):return next(x for x in receipts if x['id']==i and x.get('raw_file'))
def tree(i):return html.fromstring((R/source(i)['raw_file']).read_bytes().decode('utf-8'))
def plain(s):return ' '.join(s.split())
def ascii(s):return unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()
def safe_url(u):
    s=urlsplit(u.replace('http://transelectrica.ro/','https://www.transelectrica.ro/'))
    return urlunsplit((s.scheme,s.netloc,quote(s.path,safe='/%:+-_.;'),s.query,''))
months={'ianuarie':1,'februarie':2,'martie':3,'aprilie':4,'mai':5,'iunie':6,'iulie':7,'august':8,'septembrie':9,'octombrie':10,'noiembrie':11,'decembrie':12}
catalog=[]
for h in tree('SETTLEMENT_FULL_CATALOG').xpath('//h1'):
    title=plain(h.text_content());kind=next((v for k,v in [('3.1.','UNIQUE'),('3.2','DEFICIT'),('3.3','SURPLUS'),('4. Deze','SYSTEM')] if title.startswith(k)),None)
    if not kind:continue
    for ordinal,tr in enumerate(h.xpath('following::table[1]')[0].xpath('.//tr')):
        cells=tr.xpath('./td|./th')
        if len(cells)<3:continue
        anchors=cells[0].xpath('.//a[@href]')
        if not anchors:continue
        label=plain(cells[0].text_content());q=ascii(label);yr=re.search(r'202[56]',q)
        mon=next((v for k,v in months.items() if k in q),None)
        if not yr or not mon:continue
        canonical=f'{yr.group()}-{mon:02d}'
        if not '2025-01'<=canonical<='2026-08':continue
        vlabel=plain(cells[1].text_content());dlabel=plain(cells[2].text_content());nums=re.findall(r'\d+',dlabel)
        iso=''
        if len(nums)==3:
            try:iso=datetime(int(nums[2]),int(nums[1]),int(nums[0])).date().isoformat()
            except ValueError:pass
        url=urljoin(source('SETTLEMENT_FULL_CATALOG')['url'],anchors[0].get('href'))
        catalog.append(dict(id=f'SET_{kind}_{canonical}_{ordinal}',dataset='D07',kind=kind,month_label=label,catalog_month_I=canonical,
                            version_label=vlabel,completion_date_label=dlabel,completion_date_iso_parse=iso,
                            table_ordinal=ordinal,section=title,url=safe_url(url),catalog_source='SETTLEMENT_FULL_CATALOG',
                            publication_time=None,scope='catalog row; completion is not publication; verify body month/unit/clock and latest version separately'))
pd.DataFrame(catalog).to_csv(O/'settlement_price_version_catalog.csv',index=False,encoding='utf-8-sig')
(W/'settlement_price_catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
# First inspect months with ordinary and both DST structures, before expanding.
samples=[]
for (kind,month),group in pd.DataFrame(catalog).groupby(['kind','catalog_month_I']):
    if month in ['2025-03','2025-10','2026-08']:
        values=group.to_dict('records');values.sort(key=lambda x:x['completion_date_iso_parse'])
        samples.append(values[-1])
(W/'requests_settlement_samples.json').write_text(json.dumps(samples,ensure_ascii=False,indent=2),encoding='utf-8')

links=[];docs=[]
for name in ['TSO_STS_CATALOG','TSO_TARIFF_CATALOG']:
    for a in tree(name).xpath('//a[@href]'):
        t=plain(a.text_content());u=urljoin(source(name)['url'],a.get('href'))
        if '/documents/' not in u:continue
        if name=='TSO_STS_CATALOG' and any(k in ascii(t) for k in ['procedura','contract','2338','2716','13/22']):
            docs.append(dict(id='STS_DOC_'+str(len(docs)+1),dataset='D05-D06',url=safe_url(u),title=t,scope='official capacity procedure/contract/history; no automatic current-to-historical applicability'))
        if name=='TSO_TARIFF_CATALOG' and any(k in t for k in ['2025','2026','01.09.2024','57_2024']):
            docs.append(dict(id='TARIFF_DOC_'+str(len(docs)+1),dataset='D13',url=safe_url(u),title=t,scope='official tariff body; verify unit/value/effective date, catalogue labels may conflict'))
        links.append(dict(catalog=name,title=t,url=safe_url(u)))
docs=list({x['url']:x for x in docs}.values())
(W/'requests_rules_tariffs.json').write_text(json.dumps(docs,ensure_ascii=False,indent=2),encoding='utf-8')
pd.DataFrame(links).to_csv(O/'sts_tariff_catalog_links.csv',index=False,encoding='utf-8-sig')
print('Settlement versions:',len(catalog),'kinds/months:',pd.DataFrame(catalog).groupby('kind').catalog_month_I.nunique().to_dict(),'samples:',len(samples),'rules/tariff docs:',len(docs))
