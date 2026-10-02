"""Read immutable XLS members in official ZIP; provisional clock assumptions explicit."""
from pathlib import Path
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import xlrd,zipfile,json,hashlib,csv,math,re,sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent;OUT=ROOT/'countries/RO/full_period_20261001'
ro=ZoneInfo('Europe/Bucharest');utc=timezone.utc
receipts=[json.loads(p.read_text(encoding='utf-8')) for p in (ROOT/'data/raw/RO/full_period/20261001').glob('*/receipt.json')]
m=next(m for m in receipts if m['id']=='TSO_GENERATION_ARCHIVE' and m.get('raw_file'))
z=zipfile.ZipFile(ROOT/m['raw_file']);rows=[];members=[];issues=[];days=[];excluded=[]
fields={'Consum':'consumption','Productie':'production','Carbune':'coal','Hidrocarb.':'hydrocarbons','Ape':'hydro','Nucleara':'nuclear','Sold':'balance','Eoliana':'wind','Foto':'solar','Biocomb.':'bio','Stocare':'storage','frecventa':'frequency'}
for name in z.namelist():
    if not re.match(r'202[56]/.*\.xls$',name,re.I):continue
    b=z.read(name);book=xlrd.open_workbook(file_contents=b);monthdates=[];n=0
    for s in book.sheets():
        if s.nrows<3:continue
        datecells=[s.cell_value(0,c) for c in range(s.ncols) if s.cell_type(0,c)==3]
        if len(datecells)!=1:continue
        date=xlrd.xldate_as_datetime(datecells[0],book.datemode).date()
        if not (datetime(2025,1,1).date()<=date<=datetime(2026,8,31).date()):
            issues.append({'issue':'SCADA_HEADER_DATE_OUTSIDE_PERIOD','date':str(date),'member':name,'sheet':s.name,'handling':'source header retained; no filename-based correction; intended 2026-07-17 remains missing'})
            for rr in range(s.nrows):
                excluded.append({'source_id':m['id'],'member':name,'member_sha256':hashlib.sha256(b).hexdigest(),'sheet':s.name,'row':rr+1,'source_header_date':str(date),'source_values_json':json.dumps(s.row_values(rr),ensure_ascii=False)})
            continue
        monthdates.append(str(date));start=datetime.combine(date,datetime.min.time(),ro);end=start+timedelta(days=1)
        elapsed=(end.astimezone(utc)-start.astimezone(utc)).total_seconds()/3600
        hmap={c:fields.get(str(s.cell_value(1,c)).strip(),str(s.cell_value(1,c)).strip()) for c in range(1,s.ncols)}
        hourrows=[]
        for r in range(2,s.nrows):
            label=str(s.cell_value(r,0)).strip()
            if not re.fullmatch(r'\d{1,2}(?:\s+bis)?',label):continue
            h=int(label.split()[0])
            if not 1<=h<=25:continue
            v={field:s.cell_value(r,c) if s.cell_type(r,c)==2 else None for c,field in hmap.items()}
            hourrows.append((r,h,label,v))
        usable_day=elapsed==24 and [h for _,h,_,_ in hourrows]==list(range(1,25))
        if not usable_day:issues.append({'issue':'SCADA_DST_OR_LABEL_UNRESOLVED','date':str(date),'member':name,'sheet':s.name,'native_hour_labels':[x[2] for x in hourrows],'expected_elapsed_hours':elapsed,'handling':'preserve native; exclude whole day from provisional UTC analyses'})
        days.append({'date':str(date),'member':name,'sheet':s.name,'rows':len(hourrows),'elapsed_hours':elapsed,'provisional_clock_usable':usable_day})
        for r,h,label,v in hourrows:
            native_valid=all(isinstance(v.get(k),(int,float)) and math.isfinite(v[k]) for k in ['consumption','wind','solar','production']) and v['consumption']>0
            valid=usable_day and native_valid
            t=(start+timedelta(hours=h-1)).astimezone(utc) if usable_day else None
            residual=v['consumption']-v['wind']-v['solar'] if native_valid else None
            balance_difference=v['consumption']-v['production']-v['balance'] if all(isinstance(v.get(k),(int,float)) for k in ['consumption','production','balance']) else None
            tech=[v.get(k) for k in ['coal','hydrocarbons','hydro','nuclear','wind','solar','bio','storage']]
            techdiff=v['production']-sum(tech) if isinstance(v.get('production'),(int,float)) and all(isinstance(a,(int,float)) for a in tech) else None
            rows.append({'source_id':m['id'],'archive_sha256':m['sha256'],'member':name,'member_sha256':hashlib.sha256(b).hexdigest(),'sheet':s.name,'row':r+1,'source_local_date':str(date),'source_hour_label':label,'delivery_start_utc_provisional':t.isoformat().replace('+00:00','Z') if t else '',
              'clock_assumption_A':'Bucharest local hour-ending label 01=00:00-01:00; not official verified; exclude DST days','duration_hours_assumed':1 if usable_day else None,
              **{k+'_mw' if k!='frequency' else 'frequency_source_unit_unconfirmed':v for k,v in v.items()},'scada_residual_consumption_minus_wind_solar_mw':residual,'balance_identity_difference_mw':balance_difference,'generation_sum_including_storage_difference_mw':techdiff,'native_values_usable':native_valid,'descriptive_usable_under_clock_A':valid,'not_gross_national_load':True,'not_model_approved':True})
            n+=1
    if monthdates:members.append({'member':name,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'source_id':m['id'],'first_date':min(monthdates),'last_date':max(monthdates),'days':len(monthdates),'native_rows':n,'datemode':book.datemode})
def write(name,items):
    if not items:return
    keys=list(dict.fromkeys(k for row in items for k in row))
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(items)
write('scada_native_hourly.csv',rows);write('scada_archive_members.csv',members);write('scada_day_coverage.csv',days);write('scada_clock_issues.csv',issues);write('scada_excluded_date_records.csv',excluded)
installed=[]
mi=next(m for m in receipts if m['id']=='TSO_INSTALLED_2026_0' and m.get('raw_file'));book=xlrd.open_workbook(file_contents=(ROOT/mi['raw_file']).read_bytes())
for s in book.sheets():
    text=[str(s.cell_value(r,c)) for r in range(min(8,s.nrows)) for c in range(s.ncols) if s.cell_type(r,c)==1]
    for r in range(s.nrows):
        for c in range(s.ncols):
            if s.cell_type(r,c)!=0:installed.append({'source_id':mi['id'],'source_hash':mi['sha256'],'sheet':s.name,'row':r+1,'column':c+1,'value':s.cell_value(r,c),'ctype':s.cell_type(r,c),'header_context':' | '.join(text)})
write('installed_2026_source_cells.csv',installed)
summary={'members':len(members),'dates':len(days),'rows':len(rows),'dst_or_label_days':len(issues),'native_valid_rows':sum(r['native_values_usable'] for r in rows),'usable_rows_under_A':sum(r['descriptive_usable_under_clock_A'] for r in rows),'identity_max_abs_mw':max(abs(r['balance_identity_difference_mw']) for r in rows if r['balance_identity_difference_mw'] is not None),'tech_including_storage_max_abs_difference':max(abs(r['generation_sum_including_storage_difference_mw']) for r in rows if r['generation_sum_including_storage_difference_mw'] is not None)}
(OUT/'scada_parse_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False))
