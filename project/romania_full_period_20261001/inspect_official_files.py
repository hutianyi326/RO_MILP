from pathlib import Path
import json,zipfile
import xlrd
ROOT=Path(__file__).resolve().parents[2];WORK=Path(__file__).resolve().parent
out=[]
for p in (ROOT/'data/raw/RO/full_period/20261001').glob('*/receipt.json'):
    m=json.loads(p.read_text(encoding='utf-8'))
    if not m.get('raw_file') or not m['id'].startswith(('TSO_GENERATION','TSO_INSTALLED')):continue
    path=ROOT/m['raw_file'];body=path.read_bytes();item={'source_id':m['id'],'raw_file':m['raw_file'],'bytes':len(body),'sha256':m['sha256'],'signature':body[:16].hex()}
    if body.startswith(b'PK'):
        z=zipfile.ZipFile(path);item['format']='ZIP despite .rar URL';item['members']=[{'name':s.filename,'bytes':s.file_size,'compressed':s.compress_size} for s in z.infolist()]
    elif body.startswith(bytes.fromhex('d0cf11e0')):
        book=xlrd.open_workbook(file_contents=body);item['format']='OLE XLS despite saved .html';item['datemode']=book.datemode;item['sheets']=[]
        for sheet in book.sheets():
            rows=[{'row':r+1,'cells':[{'column':c+1,'value':sheet.cell_value(r,c),'ctype':sheet.cell_type(r,c)} for c in range(sheet.ncols) if sheet.cell_value(r,c)!='']} for r in range(sheet.nrows)]
            dest=WORK/(m['id']+'__'+str(len(item['sheets']))+'_cells.json');dest.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
            item['sheets'].append({'name':sheet.name,'rows':sheet.nrows,'cols':sheet.ncols,'cells_file':dest.relative_to(ROOT).as_posix(),'first_nonempty_rows':rows[:35],'last_nonempty_rows':rows[-5:]})
    out.append(item)
(WORK/'official_binary_inspection.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
for item in out:
    print(item['source_id'],item['format'],item['bytes'])
    if 'members' in item:print('archive',len(item['members']),'first',item['members'][:12],'last',item['members'][-12:])
    for sheet in item.get('sheets',[]):print(sheet['name'],sheet['rows'],sheet['cols'],sheet['first_nonempty_rows'][:14],sheet['last_nonempty_rows'])
