import sys,json
from pathlib import Path
from dataclasses import replace
r=Path('RO_MILP');sys.path.insert(0,str(r/'src'))
from ro_milp.config import Config,parse
from ro_milp.inputs import load_eur
from ro_milp.core import solve_window
from ro_milp.audit import audit_window
p=r/'outputs/fcr_competition_100mw_200mwh_20261005/run';m=json.loads((p/'manifest.json').read_text(encoding='utf-8'));s=json.loads((p/'windows/0568.json').read_text(encoding='utf-8'))['next_state'];i=m['identity'];cfg=Config(**i['config']);d=load_eur(r/'data/processed/RO/prices_eur_v1_20261002')
print('state',s['soc_mwh'],s['used_efc'],flush=True)
args=(parse(s['next_start']),parse(i['start']),parse(i['end']),s['soc_mwh'],{int(k):v for k,v in s['used_efc'].items()},{int(k):v for k,v in i['budgets'].items()},s['frozen'])
try:
 result=solve_window(d,cfg,*args);a=audit_window(d,cfg,result,*args);print('PASS',result['metrics'],flush=True)
except Exception as e:print(type(e).__name__,str(e),flush=True)
