import json, zipfile, hashlib, xml.etree.ElementTree as ET
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUT=HERE.parents[1]/'outputs/01a0f118-8c45-7e53-9dc7-5c2b28a5ed1c/20260801_02_audit'
FILE=OUT/'RO_100MW_200MWh_20260801_02_MILP审计.xlsx'
p=json.loads((HERE/'payload.json').read_text(encoding='utf-8'))
ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
count=0; maximum=0.
def eq(a,b,tol=1e-6):
    global count,maximum
    assert isinstance(a,(int,float)),(a,b)
    error=abs(a-b);assert error<=tol,(a,b,error)
    maximum=max(maximum,error);count+=1

with zipfile.ZipFile(FILE) as z:
    assert z.testzip() is None
    strings=[''.join(t.itertext()) for t in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',ns)] if 'xl/sharedStrings.xml' in z.namelist() else []
    wb=ET.fromstring(z.read('xl/workbook.xml'))
    names=[r.get('name') for r in wb.findall('m:sheets/m:sheet',ns)]
    assert names==['8月1日审计','8月2日审计','两日求解价格与决策','相位SOC复算','订单与窗口','原始输入与口径']
    sheets=[];formulas=[];panes=[]
    for i in range(1,7):
        root=ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml'));cells={};fs={}
        for c in root.findall('.//m:sheetData/m:row/m:c',ns):
            assert c.get('t')!='e',(names[i-1],c.get('r'),ET.tostring(c))
            v=c.find('m:v',ns)
            if c.get('t')=='s':v=strings[int(v.text)]
            elif c.get('t')=='inlineStr':v=''.join(c.find('m:is',ns).itertext())
            elif c.get('t') in ('str','d'):v=None if v is None else v.text
            else:
                try:v=None if v is None else float(v.text)
                except ValueError:v=v.text
            cells[c.get('r')]=v
            f=c.find('m:f',ns)
            if f is not None:fs[c.get('r')]=f.text
        sheets.append(cells);formulas.append(fs)
        pane=root.find('.//m:pane',ns);panes.append(pane.attrib if pane is not None else {})
    mapping={'I':'ein_mwh','J':'eout_mwh','K':'da_mw','L':'fcr_mw','M':'afrr_up_mw','N':'afrr_down_mw','O':'afrr_up_activation_mwh','P':'afrr_down_activation_mwh','Q':'da_eur','R':'fcr_capacity_eur','S':'afrr_up_capacity_eur','T':'afrr_down_capacity_eur','U':'afrr_up_activation_eur','V':'afrr_down_activation_eur','W':'total_eur','AM':'efc'}
    price_keys=['da_price_eur_per_mwh','fcr_capacity_price_eur_per_mw_h_proxy','afrr_up_capacity_price_eur_per_mw_h_proxy','afrr_down_capacity_price_eur_per_mw_h_proxy','afrr_up_activation_price_eur_per_mwh_proxy','afrr_down_activation_price_eur_per_mwh_proxy']
    for i,item in enumerate(p['plan']):
        r=i+9;s=item['ledger'];raw=p['raw'][item['raw_index']]
        eq(sheets[2][f'A{r}'],p['serials'][item['raw_index']],1e-9)
        for col,key in mapping.items():eq(sheets[2].get(f'{col}{r}'),s[key],1e-5)
        for col,key in zip('BCDEFG',price_keys):
            if raw[key]=='':assert sheets[2][f'{col}{r}']=='缺失'
            else:eq(sheets[2][f'{col}{r}'],float(raw[key]))
        for col in ('Y','AQ'):eq(sheets[2][f'{col}{r}'],0,1e-6)
        for col in 'QRSTUVW':assert f'{col}{r}' in formulas[2]
        assert sheets[2][f'H{r}']=='未模拟'
    for wi in range(2):
        for i in range(96):
            row=p['saved'][wi*96+i];r=i+9;br=wi*192+i+9
            for col,key in mapping.items():
                eq(sheets[wi][f'{col}{r}'],row[key],1e-5)
                eq(sheets[wi][f'{col}{r}'],sheets[2][f'{col}{br}'],1e-9)
            for col,key in zip('BCDEFG',price_keys):
                raw=p['raw'][wi*96+i]
                if raw[key]=='':assert sheets[wi][f'{col}{r}']=='缺失'
                else:eq(sheets[wi][f'{col}{r}'],float(raw[key]))
            assert sheets[wi][f'Z{r}']=='正式执行'
            assert isinstance(sheets[wi][f'BE{r}'],str) and isinstance(sheets[wi][f'BK{r}'],str)
        for col,key in {k:v for k,v in mapping.items() if k in 'QRSTUVW'}.items():eq(sheets[wi][f'{col}106'],p['windows'][wi]['execution_cash'][key])
    eq(sheets[0]['I9'],p['prior_end_soc'])
    eq(sheets[1]['I9'],sheets[0]['J104'])
    eq(sheets[0]['B112'],sum(w['execution_cash']['total_eur'] for w in p['windows']))
    for i,ph in enumerate(p['phases']):
        r=i+9
        for col,key in {'F':'Y','G':'C','H':'D','I':'ein','J':'eout','N':'efc'}.items():eq(sheets[3][f'{col}{r}'],ph[key])
        eq(sheets[3][f'A{r}'],ph['serial_start'],1e-9)
        eq(sheets[3][f'B{r}'],ph['serial_end'],1e-9)
    for wi,w in enumerate(p['windows']):
        r=wi+6
        eq(sheets[4][f'F{r}'],w['metrics']['plan_cash_eur']);eq(sheets[4][f'G{r}'],w['metrics']['salvage_eur']);eq(sheets[4][f'H{r}'],w['metrics']['incumbent_eur']);eq(sheets[4][f'J{r}'],0)
    assert all(v.get('xSplit')=='1' for v in panes)
    assert [v.get('ySplit') for v in panes]==['8','8','8','8','12','8']
result=dict(status='PASS',comparisons=count,maximum_numeric_deviation=maximum,sheets=names,execution_rows=192,planning_rows=384,phase_rows=len(p['phases']),cash_formula_caches_verified=True,price_inputs_verified=True,soc_continuity_verified=True,window_salvage_excluded_from_daily_cash=True,panes=panes,sha256=hashlib.sha256(FILE.read_bytes()).hexdigest(),note='Read-only XLSX/XML check of exported cached values and formulas. Recalculation used Artifact Tool, not native Excel.')
(OUT/'export_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('panes','sheets')},ensure_ascii=False))
