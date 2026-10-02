"""Native matrix extraction. No official UTC mapping or publication time inferred."""
from pathlib import Path
from datetime import datetime,date,timedelta
from zoneinfo import ZoneInfo
import csv,json,re,hashlib
import pdfplumber
ROOT=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent;OUT=ROOT/'countries/RO/gap_closure_20261001'
catalog=json.loads((W/'settlement_price_catalog.json').read_text(encoding='utf8'))
def number(s):
    if not s:return None
    s=s.replace(' ','').replace('\u2212','-')
    if not re.fullmatch(r'-?\d[\d,]*\.\d+',s):raise ValueError(f'not unambiguous decimal: {s}')
    return float(s.replace(',',''))
def physical_slots(d):
    z=ZoneInfo('Europe/Bucharest');a=datetime.combine(d,datetime.min.time(),z);b=a+timedelta(days=1)
    return int((b.timestamp()-a.timestamp())/900)
def parse(req,path):
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages)!=1:raise ValueError('unexpected page count')
        p=pdf.pages[0];words=p.extract_words(x_tolerance=.8,y_tolerance=.4);text=p.extract_text()
        anchor=next(x for x in words if x['text'].startswith('Interval/Data'))
        header_chars=sorted([x for x in p.chars if abs(x['top']-anchor['top'])<2],key=lambda x:x['x0'])
        header_text=''.join(x['text'] for x in header_chars)
        cols=[]
        for match in re.finditer(r'\d{2}\.\d{2}\.\d{4}',header_text):
            ch=header_chars[match.start():match.end()]
            cols.append({'text':match.group(),'x0':ch[0]['x0'],'x1':ch[-1]['x1']})
        rows=sorted([x for x in words if re.fullmatch('INT\\d{3}',x['text'])],key=lambda x:x['top'])
        assert 90<=len(rows)<=100 and len(cols) in (28,29,30,31),(len(rows),len(cols))
        assert [x['text'] for x in rows]==[f'INT{i:03d}' for i in range(1,len(rows)+1)]
        centers=[(x['x0']+x['x1'])/2 for x in cols];yc=[(x['top']+x['bottom'])/2 for x in rows]
        cells={};unassigned=[]
        for x in words:
            if not re.fullmatch(r'-?\d[\d,]*\.\d+',x['text']):continue
            cx=(x['x0']+x['x1'])/2;cy=(x['top']+x['bottom'])/2
            if cy<yc[0]-3 or cy>yc[-1]+3:continue
            j=min(range(len(centers)),key=lambda i:abs(centers[i]-cx));i=min(range(len(yc)),key=lambda k:abs(yc[k]-cy))
            if abs(centers[j]-cx)>18 or abs(yc[i]-cy)>max(.8,(yc[-1]-yc[0])/(len(yc)-1)*.4):unassigned.append(x['text']);continue
            if (i,j) in cells:raise ValueError('duplicate cell')
            cells[i,j]=x['text']
        assert not unassigned,unassigned[:5]
        table=p.extract_table();checks=0;cross_disagreements=[]
        if table:
            assert len(table)==len(rows)+1,(len(table),len(rows))
            for i,row in enumerate(table[1:]):
                assert row[0]==rows[i]['text']
                for j,v in enumerate(row[1:]):
                    if number(v)!=number(cells.get((i,j),'')):
                        cross_disagreements.append({'interval':i+1,'column':j+1,'rectangle_value':v,'coordinate_value':cells.get((i,j),''),'status':'UNRESOLVED_EXCLUDED_FROM_DERIVED_VALUES'})
                    checks+=1
        unit='MWh' if req['kind']=='SYSTEM' else 'lei/MWh'
        assert unit in text
        dates=[datetime.strptime(x['text'],'%d.%m.%Y').date() for x in cols]
        body_months=sorted({x.strftime('%Y-%m') for x in dates})
        out=[]
        for j,d in enumerate(dates):
            for i,row in enumerate(rows):
                raw=cells.get((i,j),'');outside=i+1>physical_slots(d)
                out.append({'source_id':req['id'],'kind':req['kind'],'catalog_month_I':req['catalog_month_I'],'body_date':d.isoformat(),'interval_label':row['text'],'interval_ordinal':i+1,'value_native':number(raw),'raw_value':raw,'unit':unit,'cell_status':'NUMERIC' if raw else 'BLANK','physical_day_slots_A':physical_slots(d),'outside_physical_day_A':outside,'utc':None,'clock_status':'SOURCE_ORDINAL_ONLY_UTC_UNCONFIRMED','completion_date_label':req['completion_date_label'],'version_label':req['version_label'],'publication_time':None,'page':1,'column_ordinal':j+1})
        title=' '.join(x['text'] for x in words if 70<x['top']<100)
        disagreement_keys={(x['interval'],x['column']) for x in cross_disagreements}
        for x in out:
            if (x['interval_ordinal'],x['column_ordinal']) in disagreement_keys:
                x['cell_status']='UNRESOLVED_EXTRACTOR_DISAGREEMENT';x['value_native']=None
        meta={**req,'raw_file':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'body_months':body_months,'body_month_match':body_months==[req['catalog_month_I']],'title_native':title,'rows':len(rows),'columns':len(cols),'numeric':len(cells),'blank':len(rows)*len(cols)-len(cells),'rect_grid_cross_checks':checks,'cross_disagreements':cross_disagreements,'system_title_conflict':req['kind']=='SYSTEM' and '2024' in title,'unit':unit}
        return out,meta
allrows=[];meta=[];errors=[]
for req in catalog:
    receipts=list((ROOT/'data/raw/RO/gap_closure/20261001').glob(req['id']+'__a*/receipt.json'))
    ok=[json.loads(p.read_text(encoding='utf8')) for p in receipts if json.loads(p.read_text(encoding='utf8'))['status']=='HTTP_OK_UNPARSED']
    if not ok:
        aliases=list((ROOT/'data/raw/RO/gap_closure/20261001').glob(req['id']+'_HOST_REPAIR_I__a*/receipt.json'))
        ok=[json.loads(p.read_text(encoding='utf8')) for p in aliases if json.loads(p.read_text(encoding='utf8'))['status']=='HTTP_OK_UNPARSED']
    if not ok:errors.append({'id':req['id'],'error':'no successful raw body'});continue
    try:
        r,m=parse(req,ROOT/ok[0]['raw_file']);allrows+=r;meta.append(m)
    except Exception as e:errors.append({'id':req['id'],'error':repr(e)})
with (OUT/'settlement_native_all_versions.csv').open('w',encoding='utf8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(allrows[0]));w.writeheader();w.writerows(allrows)
(W/'settlement_parsing_manifest.json').write_text(json.dumps({'files':meta,'errors':errors},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'parsed':len(meta),'errors':len(errors),'cells':len(allrows),'rect_grid_cross_checks':sum(x['rect_grid_cross_checks'] for x in meta)}))
print(json.dumps(errors[:15],ensure_ascii=False))
