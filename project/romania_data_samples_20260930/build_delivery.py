"""Research delivery metadata and transcribed official table samples; no model."""
from pathlib import Path
import csv,json,hashlib,re
ROOT=Path(__file__).resolve().parents[2];WORK=Path(__file__).resolve().parent;OUT=ROOT/'countries/RO/data_samples_20260930'
def putcsv(name,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
manifest=json.loads((OUT/'raw_manifest.json').read_text(encoding='utf8'))
catalog=[]
for m in manifest:
    sid=m['id'];url=m['url'];title=m['requested_scope'];pub='未标明；样本日期不等于发布日期';loc='公开页面/请求响应，详见raw_file；未下载者无原文';state=m['parse_status']
    institution=('OPCOM' if 'opcom.ro' in url else 'Transelectrica' if 'transelectrica.ro' in url else 'ANRE' if 'anre.ro' in url else 'BNR' if 'bnr.ro' in url else 'ECB' if 'ecb.europa.eu' in url else 'ENTSO-E' if 'entsoe.eu' in url else 'ANM')
    if sid.startswith('DA_') and m.get('raw_file'):title='Mcp and Traded Volume (PZU/DAM) '+sid[3:13];loc='CSV：首行单位，Romania逐区间行，ROPEX_DAM_Base汇总行'
    if sid.startswith('IDA_'):title='Intraday Auctions Results '+sid[4:14];loc='表头ROPEX_IDA1/2/3与Romania区间行；ziua_eng已选日期'
    if sid.startswith('IDCT_'):title='ID Trades: Trades concluded in 2026-08-31 PT15';loc='15 min Trades表：contract label/side/Price €/MWh/Volume MWh'
    if sid.startswith('MONTH_'):title='Monthly Report '+sid[6:13];loc='PDF p2 / printed p1；DAM价量、金额、主体数；报告期不等于发布日期';state='TABLE_TRANSCRIBED_AND_VISUALLY_VERIFIED'
    if m['detected_format']=='JSON':loc=('metadata.timeZone/lastUpdateTimestamp/maxPageSize（非观测）' if m['parse_status']=='METADATA_ONLY' else 'itemList/timeInterval/pageInfo；容量另见tenderServiceList/activityTimingList/priceScheme')
    if sid=='OPCOM_INDICES':title='INDICATORI SPECIFICI PUBLICATI DE OPCOM SA，version14';pub='更新表version14日期2025-09-30；不追认先前所有版本';loc='PDF p1—2 PZU，p5—9 IDCT，p32更新表';state='DEFINITION_PAGES_READ_AND_VISUALLY_VERIFIED'
    if sid=='NEMO_FEES_CURRENT_2026':title='Summary/Procedure regarding tariffs applied by NEMO for short-term electricity markets in 2026';pub='p4引用董事会79/12.12.2025；实际网页发布日及20个月版本链未核';loc='PDF p1管理费，p2分类，p3交易费，p4法律依据/期间修改';state='TABLE_TRANSCRIBED_AND_VISUALLY_VERIFIED'
    if sid=='TSO_ANNUAL_2025':title='RAPORTUL DIRECTORATULUI 2025';pub='2025报告；网页/文件实际发布日期未核';loc='PDF p63—64 / printed p57—58，表12—14及口径脚注';state='TABLE_TRANSCRIBED_AND_VISUALLY_VERIFIED'
    if sid=='ANRE_MONITOR_2025-12':title='Raport monitorizare piata de energie electrica – luna decembrie 2025';pub='报告期2025-12；URL目录2026/03不等于已核发布日期';loc='PDF p8水文图，p13—14商业进出口，p39双价格592区间；不是逐QH原始结算表';state='CONTROL_PAGES_READ'
    if sid=='S005':state='WRONG_CONTENT_REDIRECTED_HOME_HTML_NOT_FX_XML';loc='receipt.resolved_url与原件首页HTML'
    if sid in ['S008','S004','S010','BNR_XML_PAGE_R1','ANM_WEATHER']:state='PORTAL_OR_DISCOVERY_ONLY' if m.get('raw_file') else m['parse_status']
    if 'CURVES_' in sid and m.get('raw_file'):loc='XML：DocumentTimeInterval/CreationDateTime/DocumentVersion，SupplyCurve/DemandCurve/BlockOrder；PDF：96图及价格标签；HTML：选定日期及下载按钮'
    catalog.append(dict(source_id=sid,dataset=m['dataset'],institution=institution,title=title,publication_or_effective_date=pub,url=url,resolved_url=m.get('resolved_url',''),location=loc,access_date='2026-09-30',request_started_utc=m['retrieved_utc'],http_state=m['status'],validation_state=state,raw_file=m.get('raw_file',''),sha256=m.get('sha256',''),bytes=m.get('bytes',''),parser=m['parse_status'],metadata_last_update=m.get('metadata_last_update',''),publication_time=m.get('publication_time'),revision=m.get('revision'),note='request_started_utc来自获取回执的retrieved_utc（请求开始）；不作为市场发布/响应完成时刻'))
putcsv('source_catalog.csv',catalog)
annual=[]
def a(metric,period,value,unit,loc,boundary):annual.append(dict(source_id='TSO_ANNUAL_2025',metric=metric,period_or_asof=period,source_value=value,unit=unit,source_location=loc,boundary=boundary,quality_flag='ANNUAL_OR_SNAPSHOT;NOT_NATIVE_TIMESERIES'))
for year,vals in {'2025':['49.5','11.1','7.4','53.2'],'2024':['50.6','9.6','6.7','53.5'],'2023':['54.4','5.1','8.2','51.3']}.items():
    for k,v in zip(['net domestic generation','import','export','net internal consumption'],vals):a(k,year,v,'TWh','PDF p63 / printed57 table12','consumption includes network losses, pumping and storage consumption; excludes generating station own services')
for year,vals in {'2025':['16.0','10.1','12.2','9.2','0.18','1.8','49.5'],'2024':['16.3','10.0','14.2','8.9','0.03','1.2','50.6'],'2023':['16.5','10.3','18.2','9.5','0.0','0.0','54.4']}.items():
    for k,v in zip(['Termo','Nuclear','Hidro','Regenerabile','Baterii stocare','Prosumatori','Total generation'],vals):a(k,year,v,'TWh','PDF p63 / printed57 table13','rounded official values; 2025 Nov-Dec generation excludes prosumer feed-in; displayed 0.0 not proof of true physical zero')
for year,vals in {'2025':['4897','1413','6688','6369','19368'],'2024':['5476','1413','6633','5088','18610'],'2023':['5447','1413','6643','4708','18210']}.items():
    for k,v in zip(['Termo gross installed','Nuclear gross installed','Hidro gross installed','Regenerabile gross installed','Total gross installed'],vals):a(k,year+' end (2025 corresponds 2026-01-01)',v,'MW','PDF p64 / printed58 table14','commercial operation licensed production; excludes trial-operation units; rounded category totals need not sum exactly')
a('storage installed power','2025-12-05','494','MW','PDF p64 / printed58 storage paragraph/table','30 groups; no MWh energy rating in this table; not 2025-12-31 snapshot')
a('prosumer installed power','2026-01-01','3454','MW','PDF p64 / printed58 prosumers paragraph/table','295476 prosumers; separate statistic not automatically add to licensed production total')
putcsv('annual_structure_samples.csv',annual)
fees=[dict(source_id='NEMO_FEES_CURRENT_2026',fee='administration category A',source_value='26.268',normalized_value='26268',unit='RON/participant/year',location='PDF p1 tariff column',applicability='current 2026-hosted file; category/project/historic monthly eligibility unapproved'),dict(source_id='NEMO_FEES_CURRENT_2026',fee='administration category B',source_value='43.776',normalized_value='43776',unit='RON/participant/year',location='PDF p1 tariff column',applicability='same'),dict(source_id='NEMO_FEES_CURRENT_2026',fee='trading',source_value='0,125',normalized_value='0.125',unit='RON/MWh traded',location='PDF p3 Trading tariff',applicability='buy and sell volumes separately; VAT where applicable not added here; historic periods unapproved')]
putcsv('fee_table_samples.csv',fees)
baseline=json.loads((ROOT/'project/romania_official_rules_20260930/baseline/manifest.json').read_text(encoding='utf-8-sig'))
results=[dict(file='project/'+r['File'],expected_sha256=r['SHA256'].lower(),actual_sha256=hashlib.sha256((ROOT/'project'/r['File']).read_bytes()).hexdigest()) for r in baseline]
assert all(x['expected_sha256']==x['actual_sha256'] for x in results)
(WORK/'baseline_integrity.json').write_text(json.dumps(dict(status='PASS',files=results),ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(dict(source_rows=len(catalog),annual_rows=len(annual),fee_rows=len(fees),baseline='PASS')))
