"""Immutable official public snapshots for a price release; no solver implementation."""
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor, as_completed
import importlib.util, json

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
RAW = ROOT / 'data/raw/RO/price_release/20261002'
BASE = 'https://newmarkets.transelectrica.ro/usy-durom-publicreportg01/00121002500000000000000000000100/publicReport/'
RO = ZoneInfo('Europe/Bucharest')

def iso(t): return t.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
def request(route, label, a, b, scope):
    params = {'timeInterval.from': iso(a), 'timeInterval.to': iso(b), 'pageInfo.pageSize': 3000, 'pageInfo.pageIndex': 0}
    return dict(id=route+'_'+label, report=route, url=BASE+route+'?'+urlencode(params), parameters=params,
                publisher='Transelectrica', requested_start_utc=iso(a), requested_end_utc=iso(b), scope=scope)

def main():
    requests=[]
    for y,m in [(y,m) for y in [2025,2026] for m in range(1,13) if (y,m)<=(2026,8)]:
        a=datetime(y,m,1,tzinfo=RO); ny,nm=(y+1,1) if m==12 else (y,m+1)
        b=datetime(ny,nm,1,tzinfo=RO)
        requests.append(request('marginalPricesOverview',f'{y}-{m:02}',a,b,'formal'))
    for route in ['marginalPricesOverview','activatedBalancingEnergyOverview','tenderStatistics']:
        requests.append(request(route,'2026-09-01_OBSERVATION',datetime(2026,9,1,tzinfo=RO),datetime(2026,9,2,tzinfo=RO),'observation_only'))
        requests.append(dict(id=route+'_META',report=route+'_metadata',url=BASE+'metadata/get?reportCode='+route,publisher='Transelectrica',scope='metadata'))
    requests.append(dict(id='DA_2026-09-01_OBSERVATION',report='DA',publisher='OPCOM',source_date='2026-09-01',url='https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv/01/09/2026/en?resolution=15',scope='observation_only'))
    for code in ['469_2025','470_2025','158_2025']:
        requests.append(dict(id='GAP_'+code+'_RECHECK',report='tenderStatisticsDetail',publisher='Transelectrica',url=BASE+'tenderStatisticsDetail?tenderCode='+code,scope='gap_recheck_only'))
    (WORK/'requests.json').write_text(json.dumps(requests,ensure_ascii=False,indent=2),encoding='utf-8')
    spec=importlib.util.spec_from_file_location('collector',ROOT/'project/romania_gap_closure_20261001/collect_public.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);mod.RAW=RAW
    results=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(mod.collect,r):r for r in requests}
        for future in as_completed(jobs):
            result=future.result();results.append(result)
            print(json.dumps(dict(done=len(results),total=len(requests),id=result['id'],status=result['status'],bytes=result.get('bytes'))),flush=True)
    (WORK/'download_results.json').write_text(json.dumps(sorted(results,key=lambda r:r['id']),ensure_ascii=False,indent=2),encoding='utf-8')
    assert all(r['status']=='HTTP_OK_UNPARSED' for r in results), 'Incomplete downloads'

if __name__=='__main__':main()
