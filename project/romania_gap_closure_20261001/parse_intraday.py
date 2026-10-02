"""Extract all OPCOM native cells, without inferring trade/as-of identity.
IDCT continuation td elements outside tr must be included; rowspan is a control.
"""
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from lxml import html
import csv,hashlib,json
R=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent
O=R/'countries/RO/gap_closure_20261001';RAW=R/'data/raw/RO/gap_closure/20261001'
def num(s):
    try:return float(s.replace(',','')) if s.strip() else None
    except ValueError:return None
def write(name,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row)) or ['no_rows']
    with (O/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def expected(d):
    a=datetime.combine(d,datetime.min.time(),ZoneInfo('Europe/Brussels'))
    b=datetime.combine(d+timedelta(days=1),datetime.min.time(),ZoneInfo('Europe/Brussels'))
    return int((b.timestamp()-a.timestamp())/900)
selected={x['id']:x for x in json.loads((W/'requests_id_full_period.json').read_text(encoding='utf-8'))}
selected.update({x['id']:x for x in json.loads((W/'requests_boundary_fx_id60.json').read_text(encoding='utf-8')) if x['id'].startswith('IDCT60_')})
selected.update({x['id']:x for x in json.loads((W/'requests_idct60_full_period.json').read_text(encoding='utf-8'))})
base_fields=['source_id','query_date','source_caption','returned_form_date','form_date_matches_query','raw_sha256','retrieved_utc','publication_time','revision_time','utc_mapping_approved','asof_approved']
trade_fields=base_fields+['native_row','native_occurrence','native_group_ordinal','native_group_occurrence','declared_rowspan','native_cell_start_ordinal','native_cell_end_ordinal','native_source_line','native_product_label','native_type','price_eur_per_mwh_raw','volume_mwh_raw','price_eur_per_mwh','volume_mwh','trade_time','trade_id','full_delivery_date_verified','bilateral_turnover_aggregation_approved','not_valid_for_model']
ida=[];audit=[];groups=[];errs=[];totals={15:0,60:0}
with (O/'idct_native_publication_occurrences.csv').open('w',encoding='utf-8-sig',newline='') as output:
    writer=csv.DictWriter(output,fieldnames=trade_fields);writer.writeheader()
    for folder in sorted(RAW.iterdir()):
        rp=folder/'receipt.json'
        if not rp.exists():continue
        m=json.loads(rp.read_text(encoding='utf-8'));sid=m['id']
        if sid not in selected or m['status']!='HTTP_OK_UNPARSED':continue
        d=datetime.strptime(m['body']['ziua_eng'],'%m/%d/%Y').date()
        tree=html.fromstring((R/m['raw_file']).read_bytes().decode('utf-8'));ts=tree.xpath('//table')
        vals=tree.xpath('//input[@name="ziua_eng"]/@value');date_ok=vals==[d.strftime('%m/%d/%Y')]
        captions=[c.text_content().strip() for c in tree.xpath('//caption') if 'Trades concluded in' in c.text_content()]
        caption='Trading for' if sid.startswith('IDA_') else (captions[0] if len(captions)==1 else None)
        base=dict(source_id=sid,query_date=d.isoformat(),source_caption=caption,returned_form_date=vals[0] if vals else None,form_date_matches_query=date_ok,raw_sha256=m['sha256'],retrieved_utc=m['retrieved_utc'],publication_time=None,revision_time=None,utc_mapping_approved=False,asof_approved=False)
        if not date_ok:errs.append(dict(source_id=sid,error='FORM_DATE_MISMATCH',values=vals))
        if sid.startswith('IDA_'):
            if len(ts)!=7:errs.append(dict(source_id=sid,error='TABLE_COUNT',actual=len(ts)));continue
            for roundno,table in enumerate(ts[4:],1):
                n=0;numeric=0;blank=0;dash=0;footer=[];native=[]
                headers=[c.text_content().strip() for c in table.xpath('.//tr')[0].xpath('./th|./td')]
                assert 'EUR/MWh' in str(headers) and 'Traded Volume [MW]' in headers
                for rowno,tr in enumerate(table.xpath('.//tr')[1:],2):
                    cells=[c.text_content().strip() for c in tr.xpath('./th|./td')];native.append(cells)
                    offset=1 if roundno==1 else 0
                    if len(cells)<offset+5 or not cells[offset].isdigit():footer.append(cells);continue
                    iv=int(cells[offset]);tokens=cells[offset+1:offset+5];ns=[num(x) for x in tokens]
                    state='NUMERIC_PAIR' if ns[0] is not None and ns[1] is not None else 'BLANK_CELLS' if all(x=='' for x in tokens) else 'DASH_CELLS' if all(x=='-' for x in tokens) else 'MIXED'
                    n+=1;numeric+=state=='NUMERIC_PAIR';blank+=state=='BLANK_CELLS';dash+=state=='DASH_CELLS'
                    ida.append({**base,'round':roundno,'table_index':roundno+3,'native_row':rowno,'native_interval':iv,'price_eur_per_mwh_raw':tokens[0],'traded_volume_mw_raw':tokens[1],'buy_volume_mw_raw':tokens[2],'sell_volume_mw_raw':tokens[3],'price_eur_per_mwh':ns[0],'traded_volume_mw':ns[1],'buy_volume_mw':ns[2],'sell_volume_mw':ns[3],'published_cell_state':state,'not_valid_for_model':True})
                audit.append({**base,'kind':'IDA','round':roundno,'product_minutes':15,'native_rows':n,'numeric_price_volume_pairs':numeric,'blank_rows':blank,'dash_rows':dash,'expected_qh_A_brussels_date':expected(d),'native_count_matches_A':n==expected(d),'native_numeric_payload_sha256':hashlib.sha256(json.dumps(native).encode()).hexdigest(),'headers':json.dumps(headers),'footer':json.dumps(footer,ensure_ascii=False)})
        else:
            if len(ts)!=2:errs.append(dict(source_id=sid,error='TABLE_COUNT',actual=len(ts)));continue
            table=ts[1];trs=table.xpath('.//tr')
            hs=[[c.text_content().strip() for c in t.xpath('./th|./td')] for t in trs[:2]]
            assert hs[1][-1]=='MWh' and hs[1][-2]=='€/MWh'
            minutes=int(m['body']['tip']);expected_header='Hourly/Block Trades' if minutes==60 else '15 min Trades'
            assert hs[0][0]==expected_header,(sid,hs)
            caption_ok=captions==['Trades concluded in '+d.strftime('%d/%m/%Y')]
            if not caption_ok:errs.append(dict(source_id=sid,error='CONCLUSION_CAPTION_DATE_MISMATCH',captions=captions))
            cells=table.xpath('.//th|.//td')  # includes td siblings outside tr
            assert len(cells)>=8 and sum(len(x) for x in hs)==8
            starts=[i for i,c in enumerate(cells) if i>=8 and c.get('rowspan') is not None]
            assert (not starts and len(cells)==8) or starts[0]==8,sid
            tr_indices={t:i+1 for i,t in enumerate(trs)}
            n=0;numeric=0;consumed=0;declared_total=0;digest=hashlib.sha256()
            for groupno,start in enumerate(starts,1):
                end=starts[groupno] if groupno<len(starts) else len(cells)
                product=cells[start].text_content().strip();declared=int(cells[start].get('rowspan'))
                data_cells=end-start-1
                assert declared>0 and data_cells%3==0,(sid,groupno,data_cells)
                actual=data_cells//3
                assert actual==declared,(sid,groupno,declared,actual)
                groups.append(dict(source_id=sid,query_date=d.isoformat(),product_minutes=minutes,native_group_ordinal=groupno,native_product_label=product,native_group_cell_start_ordinal=start+1,native_group_cell_end_ordinal=end,declared_rowspan=declared,raw_data_cell_count=data_cells,raw_triplet_count=actual,extracted_occurrences=actual,rowspan_matches_raw_and_extracted=True))
                declared_total+=declared;consumed+=end-start
                for group_occurrence,k in enumerate(range(start+1,end,3),1):
                    typ,price,vol=[c.text_content().strip() for c in cells[k:k+3]]
                    assert typ in ['buy','sell'],(sid,groupno,typ)
                    pr,vo=num(price),num(vol);n+=1;numeric+=pr is not None and vo is not None
                    digest.update(json.dumps([product,typ,price,vol],ensure_ascii=False).encode('utf-8')+b'\n')
                    writer.writerow({**base,'native_row':tr_indices.get(cells[k].getparent()),'native_occurrence':n,'native_group_ordinal':groupno,'native_group_occurrence':group_occurrence,'declared_rowspan':declared,'native_cell_start_ordinal':k+1,'native_cell_end_ordinal':k+3,'native_source_line':cells[k].sourceline,'native_product_label':product,'native_type':typ,'price_eur_per_mwh_raw':price,'volume_mwh_raw':vol,'price_eur_per_mwh':pr,'volume_mwh':vo,'trade_time':None,'trade_id':None,'full_delivery_date_verified':False,'bilateral_turnover_aggregation_approved':False,'not_valid_for_model':True})
            assert consumed==len(cells)-8 and n==declared_total,sid
            totals[minutes]+=n
            audit.append({**base,'kind':'IDCT','round':None,'product_minutes':minutes,'native_rows':n,'numeric_price_volume_pairs':numeric,'blank_rows':None,'dash_rows':None,'expected_qh_A_brussels_date':None,'native_count_matches_A':None,'native_numeric_payload_sha256':digest.hexdigest(),'headers':json.dumps(hs),'footer':None,'conclusion_caption_matches_query':caption_ok,'native_total_cells':len(cells),'native_header_cells':8,'native_data_cells':len(cells)-8,'consumed_data_cells':consumed,'native_product_groups':len(starts),'sum_declared_rowspans':declared_total,'full_native_cell_consumption':consumed==len(cells)-8,'direct_table_cell_count':sum(c.getparent()==table for c in cells[8:]),'no_published_occurrences':n==0})
        if len(audit)%100==0:print(json.dumps(dict(audit_records=len(audit),idct_occurrences=sum(totals.values()))),flush=True)
write('ida_native_publication.csv',ida);write('idct_native_group_audit.csv',groups);write('intraday_file_round_audit.csv',audit)
summary=dict(ida_dates=len({x['query_date'] for x in audit if x['kind']=='IDA'}),idct15_dates=len({x['query_date'] for x in audit if x['kind']=='IDCT' and x['product_minutes']==15}),idct60_dates=len({x['query_date'] for x in audit if x['kind']=='IDCT' and x['product_minutes']==60}),ida_rows=len(ida),ida_numeric_pairs=sum(x['published_cell_state']=='NUMERIC_PAIR' for x in ida),idct_occurrences=sum(totals.values()),idct15_occurrences=totals[15],idct60_occurrences=totals[60],idct_product_groups=len(groups),errors=errs,model_approved=False,asof_approved=False,complete_intraday_market_coverage=False,identity_policy='source cell occurrence, no deduplication; no trade_id/trade_time provided',query_date_semantics='IDCT raw caption states Trades concluded in; full delivery date remains unverified',extraction_control='complete cell stream including loose td; independent rowspan and consumption controls')
(O/'intraday_analysis_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False),flush=True)

