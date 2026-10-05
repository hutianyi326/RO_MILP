"""P08-P10: reproducible synthetic full-three-phase matrix and objective comparison."""
import sys,json,argparse
from pathlib import Path
from dataclasses import replace
root=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(root/'src'),str(root/'tests')]
from test_model import fixture,first_solve
from ro_milp.config import Config,canonical
from ro_milp.rolling import code_hash

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    cases=[]
    for minutes in (60,15):
        data=fixture(minutes=minutes);cfg=Config(time_limit=30,mip_rel_gap=1e-8)
        compact,_=first_solve(data,cfg);reference,_=first_solve(data,replace(cfg,formulation='reference'))
        lhs=compact['metrics'];rhs=reference['metrics'];difference=abs(lhs['incumbent_eur']-rhs['incumbent_eur'])
        if lhs['status']!=0 or rhs['status']!=0 or difference>1e-3:raise ValueError('Performance equivalence not established')
        cases.append(dict(da_minutes=minutes,compact=lhs,reference=rhs,objective_difference_eur=difference))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    result={'status':'PASS','code_sha256':code_hash(),'classification':'SYNTHETIC_FULL_THREE_PHASE_EQUIVALENCE_NOT_REAL_MARKET_REVENUE','cases':cases}
    a.output.write_text(canonical(result)+'\n',encoding='utf-8');print(canonical(result))
