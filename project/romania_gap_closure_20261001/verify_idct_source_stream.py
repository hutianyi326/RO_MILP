"""Read-only independent reconciliation: declared rowspan traversal against CSV.
Does not import the extraction script; writes only a verification record.
"""
from pathlib import Path
from lxml import html
import csv,hashlib,json
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent;O=R/'countries/RO/gap_closure_20261001';RAW=R/'data/raw/RO/gap_closure/20261001'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
selected={x['id'] for n in ['requests_id_full_period.json','requests_idct60_full_period.json','requests_boundary_fx_id60.json'] for x in json.loads((W/n).read_text(encoding='utf-8')) if x['id'].startswith('IDCT')}
audit={x['source_id']:x for x in csv.DictReader((O/'intraday_file_round_audit.csv').open(encoding='utf-8-sig',newline='')) if x['kind']=='IDCT'}
counts={15:0,60:0};groups_total=0;files=[];zero=[];total=0;loose=0
csvpath=O/'idct_native_publication_occurrences.csv'
with csvpath.open(encoding='utf-8-sig',newline='') as f:
    output=csv.DictReader(f)
    for folder in sorted(RAW.iterdir()):
        rp=folder/'receipt.json'
        if not rp.exists():continue
        m=json.loads(rp.read_text(encoding='utf-8'));sid=m['id']
        if sid not in selected or m['status']!='HTTP_OK_UNPARSED':continue
        d=datetime.strptime(m['body']['ziua_eng'],'%m/%d/%Y')
        tree=html.fromstring((R/m['raw_file']).read_bytes().decode('utf-8'));table=tree.xpath('//table')[1]
        cells=table.xpath('.//th|.//td');cursor=8;n=0;groupno=0;direct=0;digest=hashlib.sha256()
        while cursor<len(cells):
            product_cell=cells[cursor]
            assert product_cell.get('rowspan') is not None,(sid,cursor)
            declared=int(product_cell.get('rowspan'));product=product_cell.text_content().strip();cursor+=1;groupno+=1
            for occurrence in range(1,declared+1):
                triplet=cells[cursor:cursor+3]
                assert len(triplet)==3 and not any(c.get('rowspan') for c in triplet),(sid,cursor)
                typ,price,vol=[c.text_content().strip() for c in triplet]
                row=next(output)
                n+=1;total+=1
                assert (row['source_id'],row['native_product_label'],row['native_type'],row['price_eur_per_mwh_raw'],row['volume_mwh_raw'])==(sid,product,typ,price,vol),(sid,n,'RAW_VALUE')
                assert [int(row[k]) for k in ['native_occurrence','native_group_ordinal','native_group_occurrence','declared_rowspan','native_cell_start_ordinal','native_cell_end_ordinal']]==[n,groupno,occurrence,declared,cursor+1,cursor+3],(sid,n,'LOCATOR')
                assert row['query_date']==d.date().isoformat() and row['source_caption']=='Trades concluded in '+d.strftime('%d/%m/%Y'),(sid,n,'DATE_CAPTION')
                assert row['trade_id']==row['trade_time']==row['publication_time']==row['revision_time']==''
                assert all(row[k]=='False' for k in ['utc_mapping_approved','asof_approved','full_delivery_date_verified','bilateral_turnover_aggregation_approved'])
                assert row['not_valid_for_model']=='True'
                assert float(row['price_eur_per_mwh'])==float(price.replace(',','')) and float(row['volume_mwh'])==float(vol.replace(',',''))
                digest.update(json.dumps([product,typ,price,vol],ensure_ascii=False).encode('utf-8')+b'\n')
                direct+=sum(c.getparent()==table for c in triplet)
                cursor+=3
        a=audit[sid]
        assert cursor==len(cells) and int(a['native_rows'])==n and int(a['sum_declared_rowspans'])==n
        assert int(a['native_product_groups'])==groupno and int(a['native_total_cells'])==len(cells) and int(a['consumed_data_cells'])==len(cells)-8
        assert a['native_numeric_payload_sha256']==digest.hexdigest()
        assert a['full_native_cell_consumption']==a['conclusion_caption_matches_query']=='True'
        minutes=int(m['body']['tip']);counts[minutes]+=n;groups_total+=groupno;loose+=direct
        files.append(dict(source_id=sid,occurrences=n,groups=groupno,raw_cells=len(cells),raw_sha256=m['sha256'],all_csv_fields_and_locators_match=True))
        if n==0:zero.append(sid)
        if len(files)%100==0:print(json.dumps(dict(verified_files=len(files),verified_occurrences=total)),flush=True)
    assert next(output,None) is None,'EXTRA_CSV_ROWS'
obj=dict(checked_utc=datetime.now(timezone.utc).isoformat(),passed=True,method='Independent declared-rowspan cursor traversal, every CSV occurrence and raw token/locator compared; no extraction script import',verified_files=len(files),verified_occurrences=total,occurrences_by_selector=counts,product_groups=groups_total,loose_triplet_cells_verified=loose,no_published_occurrence_source_ids=zero,csv_sha256=sha(csvpath),audit_sha256=sha(O/'intraday_file_round_audit.csv'),files=files,asof_approved=False,model_approved=False)
(W/'idct_source_stream_verification.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in obj.items() if k!='files'},ensure_ascii=False),flush=True)

