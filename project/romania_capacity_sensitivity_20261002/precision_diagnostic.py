"""Isolated continuation before budget exhaustion; never modifies a source ledger."""
import sys,json,warnings
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
import ro_milp.core as core
from ro_milp.rolling import read_json,code_hash
from ro_milp.inputs import load_eur
from ro_milp.config import Config,parse,iso,nextday,localday,canonical
from ro_milp.audit import audit_window

if __name__=='__main__':
    run=ROOT/'outputs/capacity_sensitivity_100mw_200mwh_20261002/v2/p60_run'
    ident=read_json(run/'manifest.json')['identity'];tx=read_json(run/'windows/0320.json');state=tx['next_state']
    cfg=Config(**ident['config']);data=load_eur(ROOT/'data/processed/RO/prices_eur_v1_20261002')
    original=core.milp
    def precise(*args,**kwargs):
        kwargs['options']=dict(kwargs['options'],primal_feasibility_tolerance=1e-9,mip_feasibility_tolerance=1e-9)
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore',message='Unrecognized options detected')
            result=original(*args,**kwargs)
            if result.status==2:
                import numpy as np
                constraint=kwargs['constraints'];bounds=kwargs['bounds']
                np.savez_compressed(ROOT/'outputs/capacity_sensitivity_100mw_200mwh_20261002/failed_matrix.npz',c=args[0],integrality=kwargs['integrality'],lb=bounds.lb,ub=bounds.ub,A=constraint.A.toarray(),rlb=constraint.lb,rub=constraint.ub)
            return result
    # --current tests the production guard/options; default preserves the earlier
    # tight-precision-only experiment for reproducibility against its source snapshot.
    current='--current' in sys.argv
    if not current:core.milp=precise
    records=[];failure=None
    while localday(parse(state['next_start'])).isoformat()<'2026-01-05':
        s=parse(state['next_start']);stop=nextday(s);used={int(k):v for k,v in state['used_efc'].items()};budgets={int(k):v for k,v in ident['budgets'].items()}
        try:
            result=core.solve_window(data,cfg,s,parse(ident['start']),parse(ident['end']),state['soc_mwh'],used,budgets,state['frozen'])
            replay=audit_window(data,cfg,result,s,parse(ident['start']),parse(ident['end']),state['soc_mwh'],used,budgets,state['frozen'])
            rows=[r for r in replay['qh'] if parse(r['delivery_start_utc'])<stop]
            ledger={k:v for k,v in state['frozen'].items() if parse(v['end'])>stop}
            ledger.update({k:v for k,v in result['orders'].items() if s<=parse(v['gate'])<stop and parse(v['end'])>stop})
            for row in rows:used[localday(parse(row['delivery_start_utc'])).year]+=row['efc']
            state=dict(next_start=iso(stop),soc_mwh=rows[-1]['eout_mwh'],used_efc={str(k):v for k,v in used.items()},frozen=ledger)
            records.append(dict(start=iso(s),metrics=result['metrics'],soc=state['soc_mwh'],used_efc=state['used_efc']))
            print(iso(s),used,flush=True)
        except Exception as e:
            failure=dict(start=iso(s),error=str(e));print(failure,flush=True)
            (ROOT/'outputs/capacity_sensitivity_100mw_200mwh_20261002/failed_precision_state.json').write_text(canonical(state),encoding='utf-8')
            break
    output=ROOT/'outputs/capacity_sensitivity_100mw_200mwh_20261002'/('guard_diagnostic.json' if current else 'precision_diagnostic.json')
    output.write_text(canonical(dict(status='PASS' if failure is None else 'FAIL',source_transaction_sha256=tx['sha256'],source_code_sha256=code_hash(),options={'primal_feasibility_tolerance':1e-8 if current else 1e-9,'mip_feasibility_tolerance':1e-8 if current else 1e-9},failure=failure,windows=records))+'\n',encoding='utf-8')
