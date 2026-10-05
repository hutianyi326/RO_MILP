import json,zipfile,xml.etree.ElementTree as ET,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
OUT=HERE.parents[1]/'outputs/01a0f118-8c45-7e53-9dc7-5c2b28a5ed1c/20250101_audit'
FILE=OUT/'RO_100MW_200MWh_20250101_MILP审计.xlsx'
p=json.loads((HERE/'payload.json').read_text(encoding='utf-8'))
ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(FILE) as z:
    assert z.testzip() is None
    strings=[''.join(t.itertext()) for t in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',ns)] if 'xl/sharedStrings.xml' in z.namelist() else []
    sheets=[];panes=[]
    for i in range(1,6):
        root=ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml'));cells={}
        for c in root.findall('.//m:sheetData/m:row/m:c',ns):
            assert c.get('t')!='e',(i,c.get('r'),ET.tostring(c))
            v=c.find('m:v',ns)
            if c.get('t')=='s':v=strings[int(v.text)]
            elif c.get('t')=='inlineStr':v=''.join(c.find('m:is',ns).itertext())
            elif c.get('t') in ('str','d'):v=None if v is None else v.text
            else:
                try:v=None if v is None else float(v.text)
                except ValueError:v=v.text
            cells[c.get('r')]=v
        sheets.append(cells)
        pane=root.find('.//m:pane',ns);panes.append(pane.attrib if pane is not None else {})
    checks=0;maximum=0.
    def eq(a,b,tol=1e-6):
        global checks,maximum
        assert isinstance(a,(int,float)),(a,b)
        e=abs(a-b);assert e<=tol,(a,b,e);checks+=1;maximum=max(maximum,e)
    mapping={'I':'ein_mwh','J':'eout_mwh','K':'da_mw','L':'fcr_mw','M':'afrr_up_mw','N':'afrr_down_mw','O':'afrr_up_activation_mwh','P':'afrr_down_activation_mwh','Q':'da_eur','R':'fcr_capacity_eur','S':'afrr_up_capacity_eur','T':'afrr_down_capacity_eur','U':'afrr_up_activation_eur','V':'afrr_down_activation_eur','W':'total_eur','AL':'efc'}
    for i,row in enumerate(p['saved']):
        r=i+7
        for col,key in mapping.items():eq(sheets[1].get(f'{col}{r}'),row[key])
        eq(sheets[1][f'A{r}'],p['serials'][i],1e-9)
        if i<96:
            for col,key in mapping.items():eq(sheets[0].get(f'{col}{r}'),row[key])
        else:
            for col,key in mapping.items():eq(sheets[4].get(f'{col}{i-96+7}'),row[key])
            eq(sheets[4][f'A{i-96+7}'],p['serials'][i],1e-9)
            for col in ('B','C','D','E','F','G','H','AA','AB','AE','AF','AQ','AR','AS','AT','AU','AV'):
                assert sheets[4][f'{col}{i-96+7}']==sheets[1][f'{col}{r}'],(i,col)
        assert sheets[1][f'C{r}']=='缺失' and sheets[1][f'H{r}']=='未模拟'
    for i,row in enumerate(p['phases']):
        r=i+7
        for col,key in {'F':'Y','G':'C','H':'D','I':'ein','J':'eout','N':'efc'}.items():eq(sheets[2][f'{col}{r}'],row[key])
        eq(sheets[2][f'A{r}'],row['serial_start'],1e-9)
    eq(sheets[0]['W104'],0)
    for col,key in mapping.items():
        if col in ('O','P','Q','R','S','T','U','V','W'):
            eq(sheets[4][f'{col}104'],sum(row[key] for row in p['saved'][96:]))
    eq(sheets[4]['I7'],sheets[0]['J102'])
    eq(sheets[4]['J102'],p['saved'][-1]['eout_mwh'])
    eq(sheets[1]['W200'],p['metrics']['plan_cash_eur'])
    assert sheets[1]['G7']==0,'Valid zero price was lost'
    assert all(v.get('xSplit')=='1' for v in panes)
    assert [v.get('ySplit') for v in panes]==['6','6','6','8','6']
    # Compare the original four sheets by decoded values, formulas and style IDs.
    def contents(book,idx):
        ss=[''.join(t.itertext()) for t in ET.fromstring(book.read('xl/sharedStrings.xml')).findall('m:si',ns)]
        root=ET.fromstring(book.read(f'xl/worksheets/sheet{idx}.xml'))
        for c in root.findall('.//m:c',ns):
            if c.get('t')=='s':c.find('m:v',ns).text=ss[int(c.find('m:v',ns).text)]
        dxfs=ET.fromstring(book.read('xl/styles.xml')).find('m:dxfs',ns)
        for rule in root.findall('.//m:cfRule',ns):
            if 'dxfId' in rule.attrib:rule.set('dxfId',ET.tostring(dxfs[int(rule.get('dxfId'))]).decode())
        return ET.tostring(root)
    with zipfile.ZipFile(HERE/'before_jan2.xlsx.backup') as old:
        for idx in range(1,5):assert contents(old,idx)==contents(z,idx),f'Unexpected original sheet change: {idx}'
result={'status':'PASS','checks':checks,'maximum_numeric_deviation':maximum,'sheets':5,'original_four_sheets_preserved':True,'day2_cash_eur':sheets[4]['W104'],'cash_formulas_cached':True,'zero_vs_missing_preserved':True,'freeze_panes':panes,'file_sha256':hashlib.sha256(FILE.read_bytes()).hexdigest(),'note':'Standard-library read-only XLSX/XML verification of exported cached values, dates, formulas errors and panes. Recalculated with Artifact Tool; native Excel application not launched.'}
(OUT/'export_validation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
