"""Audited two-local-day planning; append-only atomic daily transaction ledger."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
import csv, hashlib, json, os, uuid, platform
import numpy, scipy
from .config import *
from .core import solve_window
from .audit import audit_window, near, cash_near

def code_hash():
    root=Path(__file__).parent
    return hash_object({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob('*.py'))})

def atomic_json(path,payload,immutable=False):
    """Atomic NTFS/local filesystem publication. Never overwrite committed history."""
    path=Path(path);temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x',encoding='utf-8',newline='\n') as f:
            f.write(canonical(payload)+'\n');f.flush();os.fsync(f.fileno())
        if immutable:os.link(temporary,path);temporary.unlink()
        else:os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()

def read_json(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def _csv(path,rows,fields=None):
    rows=list(rows);fields=fields or list(dict.fromkeys(k for row in rows for k in row))
    temp=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temp.open('x',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
            for row in rows:w.writerow({k:(canonical(v) if isinstance(v,(list,dict)) else v) for k,v in row.items()})
        os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()

def verify_chain(output,identity):
    """Checkpoint is a cache: immutable daily payloads are the source of truth."""
    output=Path(output);manifest=read_json(output/'manifest.json')
    if manifest['identity']!=identity:raise ValueError('Resume input/code/config/budget identity mismatch')
    state=manifest['initial_state'];parent=hash_object(manifest);transactions=[]
    for i,path in enumerate(sorted((output/'windows').glob('*.json'))):
        tx=read_json(path);digest=tx.pop('sha256')
        if hash_object(tx)!=digest or tx['previous_sha256']!=parent or tx['sequence']!=i or tx['start']!=state['next_start'] or path.name!=f'{i:04d}.json':raise ValueError('Corrupt or discontinuous committed ledger')
        if tx['identity_hash']!=hash_object(identity):raise ValueError('Transaction run mismatch')
        next_state=tx['next_state'];next_t=nextday(parse(state['next_start']))
        if next_state['next_start']!=iso(next_t) or not tx['executed_qh']:raise ValueError('Invalid checkpoint transition')
        near(tx['executed_qh'][0]['ein_mwh'],state['soc_mwh'],label='Ledger start SOC')
        near(tx['executed_qh'][-1]['eout_mwh'],next_state['soc_mwh'],label='Ledger end SOC')
        times=[parse(row['delivery_start_utc']) for row in tx['executed_qh']]
        from datetime import timedelta
        if times[0]!=parse(state['next_start']) or times[-1]+timedelta(minutes=15)!=next_t or any(b-a!=timedelta(minutes=15) for a,b in zip(times,times[1:])):raise ValueError('Ledger execution grid')
        totals={int(y):float(v) for y,v in state['used_efc'].items()}
        for row in tx['executed_qh']:
            y=localday(parse(row['delivery_start_utc'])).year;totals[y]=totals.get(y,0)+row['efc']
        if set(map(int,next_state['used_efc']))!=set(totals):raise ValueError('Ledger EFC years')
        for y,v in totals.items():near(v,next_state['used_efc'][str(y)],EFC_TOL,'Ledger EFC')
        ledger={k:v for k,v in state['frozen'].items() if parse(v['end'])>next_t}
        for k,v in tx['new_orders'].items():
            if not parse(state['next_start'])<=parse(v['gate'])<next_t:raise ValueError('Ledger gate interval')
            if k in ledger and ledger[k]!=v:raise ValueError('Ledger conflicting order')
            if parse(v['end'])>next_t:ledger[k]=v
        if ledger!=next_state['frozen']:raise ValueError('Ledger frozen checkpoint mismatch')
        state=next_state;parent=digest;transactions.append(dict(tx,sha256=digest))
    return manifest,state,parent,transactions

def export(output,manifest,state,transactions,failure=None):
    output=Path(output);cfg=manifest['identity']['config'];qh=[];ph=[];orders=[];metrics=[]
    for tx in transactions:
        qh.extend(tx['executed_qh']);ph.extend(tx['executed_phases'])
        orders.extend(dict(sequence=tx['sequence'],**o) for o in tx['new_orders'].values())
        # Include the initial-day explicit zero commitments for a complete native order history.
        orders.extend(dict(sequence=tx['sequence'],**o) for o in tx.get('initial_orders',{}).values())
        metrics.append(dict(sequence=tx['sequence'],start=tx['start'],**tx['metrics']))
    months=defaultdict(lambda:dict.fromkeys(CASH,0.));counts=defaultdict(int)
    for row in qh:
        mo=row['local_date'][:7];counts[mo]+=1
        for k in CASH:months[mo][k]+=row[k]
    monthly=[dict(month=mo,executed_qh=counts[mo],**v,total_eur=sum(v.values()),total_keur_per_mw=sum(v.values())/1000/cfg['power_mw']) for mo,v in sorted(months.items())]
    _csv(output/'executed_qh.csv',qh);_csv(output/'executed_phases.csv',ph);_csv(output/'committed_orders.csv',orders);_csv(output/'window_metrics.csv',metrics);_csv(output/'monthly_cash_eur.csv',monthly)
    efc=[dict(year=y,budget_efc=v,executed_efc=state['used_efc'].get(str(y),0.),lookahead_only=int(y) not in manifest['formal_years']) for y,v in manifest['identity']['budgets'].items()]
    _csv(output/'annual_efc.csv',efc)
    summary=dict(status='BLOCKED' if failure else ('COMPLETE' if state['next_start']==manifest['identity']['end'] else 'PARTIAL'),classification='EX_POST_CONDITIONAL_GROSS_CASH',currency='EUR',windows=len(transactions),executed_qh=len(qh),cash_eur={k:sum(r[k] for r in qh) for k in CASH},total_eur=sum(r['total_eur'] for r in qh),end_soc_mwh=state['soc_mwh'],failure=failure,data_coverage=dict(da_valid_qh=sum(r['da_data_valid'] for r in qh),afrr_valid_qh=sum(r['afrr_hour_data_valid'] for r in qh),fcr_valid_qh=sum(r['fcr_hour_data_valid'] for r in qh),initial_no_prior_qh=sum(r['initial_no_prior_commitment'] for r in qh)),max_variables=max((r['variables'] for r in metrics),default=0),max_binary=max((r['binary'] for r in metrics),default=0))
    summary['capacity_share_mode']=cfg.get('capacity_share_mode','none')
    summary['capacity_share_schedule_sha256']=hash_object(cfg.get('monthly_capacity_shares',{}))
    summary['capacity_share_proxy_months']=[mo for mo,r in cfg.get('monthly_capacity_shares',{}).items() if any(str(r[k]).startswith('proxy') for k in ('fcr_status','afrr_status'))] if cfg.get('capacity_share_mode')=='monthly' else []
    atomic_json(output/'checkpoint.json',state);atomic_json(output/'summary.json',summary)
    text=f"# RO MILP run\n\nStatus: {summary['status']}. Currency: EUR. Executed QH: {len(qh)}. Windows: {len(transactions)}.\n\nConditional ex-post gross cash: {summary['total_eur']:.6f} EUR. This is a perfect-information, proxy-price research result, not executable trading profit or verified settlement. It is not a certified full-horizon theoretical upper bound.\n\nCapacity: assumed hourly orders; capacity cash equals awarded MW times price times duration. Capacity-share mode: {summary['capacity_share_mode']}; monthly demand-share caps constrain awarded MW. No additional capacity income haircut is applied. Proxy assumptions remain identified in the configuration and order ledger. FCR: capacity opportunity value with static energy buffers, no frequency activation cash, losses or extra cycles. Nominal gate/result times and research qualification/unit sizes are assumptions. First-day past-gate orders default to zero. The observation day is planned only; only executed formal rows enter totals.\n\nSee manifest.json for exact scope, input/code/config hashes and budgets; window_metrics.csv for solver incumbent/bound/gap; windows/ for atomic decisions and audits; monthly_cash_eur.csv for six cash components. Limits/timeouts may yield audited feasible incumbents rather than proven optima.\n"
    (output/'report.md').write_text(text,encoding='utf-8')
    return summary

def run(data,cfg,start,end,output,budget_override=None,resume=False,max_windows=None):
    if start>=end or start!=midnight(localday(start)) or end!=midnight(localday(end)):raise ValueError('Run bounds must be increasing Bucharest midnights')
    if max_windows is not None and max_windows<1:raise ValueError('max_windows must be positive')
    if cfg.capacity_share_mode=='monthly' and cfg.market!='DA':
        for month in {str(q.day)[:7] for q in data.window(start,end)}:
            if cfg.monthly_capacity_shares.get(month,{}).get('scope')=='LOOKAHEAD_ONLY':raise ValueError('Share month is LOOKAHEAD_ONLY, not a formal execution month: '+month)
    data.window(start,nextday(end));budgets=data.budgets(start,end,budget_override)
    identity=json.loads(canonical(dict(config=cfg.as_dict(),start=iso(start),end=iso(end),input_sha256=data.source_hash,code_sha256=code_hash(),budgets={str(k):v for k,v in budgets.items()})))
    output=Path(output)
    if resume:manifest,state,parent,transactions=verify_chain(output,identity)
    else:
        output.mkdir(parents=True,exist_ok=False);(output/'windows').mkdir()
        state={'next_start':iso(start),'soc_mwh':cfg.e_min,'used_efc':{str(y):0. for y in budgets},'frozen':{}}
        from datetime import timedelta
        years=sorted({q.day.year for q in data.window(start,end)})
        manifest={'identity':identity,'created_utc':iso(datetime.now(timezone.utc)),'initial_state':state,'formal_years':years,'input_evidence':data.evidence,'runtime':{'python':platform.python_version(),'numpy':numpy.__version__,'scipy':scipy.__version__},'specification':'RO monthly-share 2026-10-04: M01-M32 except retired M26 and capacity income factors; M33; P01-P07; current_model_and_usage 2026-10-04; EUR only'}
        atomic_json(output/'manifest.json',manifest,True);parent=hash_object(manifest);transactions=[]
    done=0;failure=None
    while parse(state['next_start'])<end and (max_windows is None or done<max_windows):
        s=parse(state['next_start']);stop=nextday(s)
        try:
            used={int(k):v for k,v in state['used_efc'].items()}
            result=solve_window(data,cfg,s,start,end,state['soc_mwh'],used,budgets,state['frozen'])
            replay=audit_window(data,cfg,result,s,start,end,state['soc_mwh'],used,budgets,state['frozen'])
            rows=[r for r in replay['qh'] if parse(r['delivery_start_utc'])<stop]
            phases=[r for r in replay['phases'] if parse(r['start'])<stop]
            new={k:v for k,v in result['orders'].items() if s<=parse(v['gate'])<stop}
            ledger={k:v for k,v in state['frozen'].items() if parse(v['end'])>stop}
            for k,v in new.items():
                if k in ledger and ledger[k]!=v:raise ValueError('Atomic commit conflict '+k)
                if parse(v['end'])>stop:ledger[k]=v
            updated=used.copy()
            for row in rows:
                y=localday(parse(row['delivery_start_utc'])).year;updated[y]+=row['efc']
            for y,v in updated.items():
                if v>budgets[y]+EFC_TOL:raise ValueError('Committed EFC exceeds budget')
            after={'next_start':iso(stop),'soc_mwh':rows[-1]['eout_mwh'],'used_efc':{str(k):v for k,v in updated.items()},'frozen':ledger}
            payload=dict(sequence=len(transactions),start=iso(s),previous_sha256=parent,identity_hash=hash_object(identity),executed_qh=rows,executed_phases=phases,new_orders=new,initial_orders={k:v for k,v in result['orders'].items() if v['commitment']=='INITIAL_NO_PRIOR_COMMITMENT'},metrics=result['metrics'],next_state=after)
            digest=hash_object(payload);tx=dict(payload,sha256=digest)
            atomic_json(output/'windows'/f'{len(transactions):04d}.json',tx,True)
            state=after;parent=digest;transactions.append(tx);done+=1
        except (ValueError,RuntimeError,OSError) as exc:
            failure={'window_start':iso(s),'type':type(exc).__name__,'message':str(exc)}
            atomic_json(output/('failure_'+uuid.uuid4().hex+'.json'),failure,True)
            break
    return export(output,manifest,state,transactions,failure)
