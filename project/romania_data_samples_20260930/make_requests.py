from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
import json
W=Path(__file__).resolve().parent
DAYS=['2025-01-15','2025-03-30','2025-09-30','2025-10-01','2025-10-26','2026-03-29','2026-08-31']
BASE='https://newmarkets.transelectrica.ro/usy-durom-publicreportg01/00121002500000000000000000000100/publicReport/'
def daily(report,dataset):
    out=[]
    for day in DAYS:
        t=datetime.fromisoformat(day).replace(tzinfo=ZoneInfo('Europe/Bucharest'));u=t+timedelta(days=1)
        q=urlencode({'timeInterval.from':t.astimezone(ZoneInfo('UTC')).isoformat().replace('+00:00','Z'),'timeInterval.to':u.astimezone(ZoneInfo('UTC')).isoformat().replace('+00:00','Z'),'pageInfo.pageSize':3000})
        out.append(dict(id=report+'_'+day,dataset=dataset,url=BASE+report+'?'+q,scope=day+' native local day; public page backing route; unversioned snapshot'))
    out.append(dict(id=report+'_META',dataset=dataset,url=BASE+'metadata/get?reportCode='+report,scope='public report metadata; lastUpdateTimestamp not per-record publication'))
    return out
r=daily('marginalPricesOverview','D06')+daily('dailyConsumptionOverview','D08-D16')
r.append(dict(id='tenderStatistics_2026-03-29_R1',dataset='D05',url=daily('tenderStatistics','D05')[5]['url'],scope='2026-03-29 retry; previous failure retained'))
W.joinpath('requests_prices_load.json').write_text(json.dumps(r,indent=2),encoding='utf8')
