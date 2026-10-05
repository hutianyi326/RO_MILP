"""Reproduce and resolve the actual exhausted-budget window without changing its state."""
import sys,json,argparse,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from ro_milp.rolling import read_json,verify_chain,code_hash
from ro_milp.inputs import load_eur
from ro_milp.config import Config,parse,canonical
from ro_milp.core import solve_window
from ro_milp.audit import audit_window

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    ident=read_json(a.run/'manifest.json')['identity'];_,state,chain,_=verify_chain(a.run,ident)
    snapshot=canonical(state);data=load_eur(ROOT/'data/processed/RO/prices_eur_v1_20261002');cfg=Config(**ident['config'])
    assert cfg.p_up==cfg.p_down==cfg.p_fcr==.6 and cfg.presolve
    args=(parse(state['next_start']),parse(ident['start']),parse(ident['end']),state['soc_mwh'],{int(y):v for y,v in state['used_efc'].items()},{int(y):v for y,v in ident['budgets'].items()},state['frozen'])
    result=solve_window(data,cfg,*args);replay=audit_window(data,cfg,result,*args)
    assert canonical(state)==snapshot
    assert result['metrics']['presolve_retry'] and [a['status'] for a in result['metrics']['solver_attempts']]==[2,0]
    record={'status':'PASS','code_sha256':code_hash(),'original_last_transaction_sha256':chain,'original_checkpoint_state_sha256':hashlib.sha256(snapshot.encode()).hexdigest(),'frozen_and_start_state_unchanged':True,'economic_budget_unchanged':ident['budgets'],'metrics':result['metrics'],'replay_year_efc':replay['year_efc'],'note':'Same matrix, bounds, integrality, gap, frozen positions and SOC; remaining original time limit, presolve disabled on retry; original audit tolerances unchanged; no daily transaction committed by this diagnostic.'}
    a.output.write_text(canonical(record)+'\n',encoding='utf-8');print(canonical(record))
