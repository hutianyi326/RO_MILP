"""Read-only full-horizon replay from committed orders and immutable market inputs.

Does not use core.solve_window, audit.audit_window or reported cash as its calculation.
The only output is a separate validation record requested by --output.
"""
import sys,json,csv,hashlib,argparse,math
from pathlib import Path
from collections import defaultdict,Counter
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from ro_milp.inputs import load_eur
from ro_milp.config import Config,RO,parse,iso,midnight,nextday,localday,event,canonical,hash_object,CASH
from ro_milp.rolling import code_hash

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def validate(run_dir):
    run_dir=Path(run_dir);manifest=read(run_dir/'manifest.json');identity=manifest['identity'];cfg=Config(**identity['config'])
    assert cfg.power_mw==100 and cfg.hours==2 and cfg.market=='DA+aFRR+FCR'
    assert cfg.capacity_share_mode=='monthly' and {'p_up','p_down','p_fcr','daily_p'}.isdisjoint(identity['config'])
    assert cfg.e_min==10 and cfg.e_max==190
    assert identity['code_sha256']==code_hash()
    data=load_eur(ROOT/'data/processed/RO/prices_eur_v1_20261002');assert identity['input_sha256']==data.source_hash
    S=midnight('2025-01-01');T=midnight('2026-09-01');assert identity['start']==iso(S) and identity['end']==iso(T)
    budget={int(y):v for y,v in identity['budgets'].items()};assert abs(budget[2025]-600)<1e-7 and abs(budget[2026]-600*243/365)<1e-7
    deviations=defaultdict(float);checks=Counter()
    def equal(a,b,kind='physical'):
        a=float(a);b=float(b);assert math.isfinite(a) and math.isfinite(b)
        error=abs(a-b);deviations[kind]=max(deviations[kind],error);checks[kind]+=1
        tol=1e-5+1e-9*max(abs(a),abs(b)) if kind=='cash' else 1e-7 if kind=='efc' else 1e-6
        assert error<=tol,(kind,a,b,error)
    orders={};executed={};phases={};transactions=[];parent=hash_object(manifest);state=manifest['initial_state']
    files=sorted((run_dir/'windows').glob('*.json'));assert len(files)==608
    for i,path in enumerate(files):
        tx=read(path);signature=tx.pop('sha256');assert path.name==f'{i:04d}.json' and tx['sequence']==i
        assert hash_object(tx)==signature and tx['previous_sha256']==parent and tx['identity_hash']==hash_object(identity)
        assert tx['start']==state['next_start'];s=parse(tx['start']);end=nextday(s)
        assert tx['next_state']['next_start']==iso(end) and tx['metrics']['audit']=='PASS'
        assert tx['metrics']['status'] in (0,1)
        for k,o in {**tx['initial_orders'],**tx['new_orders']}.items():
            assert k not in orders and o['key']==k
            if k in tx['initial_orders']:assert i==0 and parse(o['gate'])<S and o['amount_mw']==0
            else:assert s<=parse(o['gate'])<end
            orders[k]=o
        qr=tx['executed_qh'];assert len(qr)==int((end-s).total_seconds()/900)
        for n,row in enumerate(qr):
            key=row['delivery_start_utc'];assert key==iso(s+timedelta(minutes=15*n)) and key not in executed
            assert parse(row['delivery_end_utc'])==parse(key)+timedelta(minutes=15)
            executed[key]=row
        for row in tx['executed_phases']:
            key=(row['start'],row['phase']);assert key not in phases;phases[key]=row
        ledger={k:v for k,v in state['frozen'].items() if parse(v['end'])>end}
        for k,o in tx['new_orders'].items():
            assert k not in ledger
            if parse(o['end'])>end:ledger[k]=o
        assert ledger==tx['next_state']['frozen']
        parent=signature;transactions.append(tx);state=tx['next_state']
    assert state['next_start']==iso(T) and len(executed)==58364 and len(files)==608
    qs=data.window(S,nextday(T));expected={'DA|'+q.da_id for q in qs}|{p+'|'+iso(q.hour) for q in qs for p in ('u','d','F')}
    assert set(orders)==expected
    for k,o in orders.items():
        p=o['product'];s=parse(o['start']);v=o['amount_mw'];gate=event(s,13 if p=='DA' else 9)
        assert o['gate']==iso(gate) and o['result']==iso(event(s,14 if p=='DA' else 10))
        if p=='DA':
            group=data.da[k[3:]];assert o['start']==iso(group[0].start) and o['end']==iso(group[-1].end)
            bound=cfg.power_mw if all(q.da_price is not None for q in group) else 0
            assert -bound-1e-6<=v<=bound+1e-6
        else:
            group=data.hours[s];assert k==p+'|'+iso(s) and parse(o['end'])==s+timedelta(hours=1)
            valid=(data.hour_f[s] if p=='F' else data.hour_a[s])
            qty=[getattr(q,{'u':'sys_u','d':'sys_d','F':'sys_f'}[p]) for q in group]
            bound=math.floor(min(cfg.power_mw,cfg.qualified(p),*qty)) if valid else 0
            limits=[]
            for q in group:
                row=cfg.monthly_capacity_shares.get(str(q.day)[:7])
                coef=None if row is None else row[('fcr' if p=='F' else 'afrr')+'_market_share_cap']
                demand=getattr(q,{'u':'demand_u','d':'demand_d','F':'demand_f'}[p])
                limits.append(0 if coef is None or demand is None or not math.isfinite(demand) or demand<=0 else math.floor(coef*demand+1e-9))
            bound=min(bound,*limits)
            sr=cfg.monthly_capacity_shares.get(str(localday(s))[:7],{})
            prefix='fcr' if p=='F' else 'afrr'
            assert 'p' not in o
            assert o['capacity_share_month']==str(localday(s))[:7]
            assert o['capacity_share_coefficient']==sr.get(prefix+'_market_share_cap')
            assert o['capacity_share_status']==sr.get(prefix+'_status','MISSING')
            assert o['capacity_share_reference_month']==sr.get(prefix+'_reference_month','')
            assert o['capacity_share_scope']==sr.get('scope','')
            assert o['capacity_share_mode']=='monthly'
            if s<T:assert sr.get('scope')!='LOOKAHEAD_ONLY'
            checks['capacity_share_order']+=1
            if p=='F':bound=min(bound,sum(math.floor(x) for x in cfg.units))
            equal(o['upper'],bound)
            equal(v,round(v));assert 0<=v<=bound
            if p=='F':
                assert len(o['units_mw'])==len(cfg.units)
                for x,cap in zip(o['units_mw'],cfg.units):assert x==round(x) and 0<=x<=math.floor(cap)
                equal(sum(o['units_mw']),v)
        checks['native_order']+=1
    E=cfg.e_min;replay=[];all_phases=[];cash_totals=defaultdict(float);efc_year=defaultdict(float)
    for q in qs:
        B=orders['DA|'+q.da_id]['amount_mw'];u=orders['u|'+iso(q.hour)]['amount_mw'];d=orders['d|'+iso(q.hour)]['amount_mw'];F=orders['F|'+iso(q.hour)]['amount_mw']
        assert u+F<=100 and d+F<=100 and B+u+F<=100+1e-6 and -B+d+F<=100+1e-6
        if data.hour_a[q.hour]:
            au=q.energy_u/(q.sys_u*.25);ad=q.energy_d/(q.sys_d*.25)
            shape=[('d',ad*.25,B-d),('u',au*.25,B+u),('0',(1-au-ad)*.25,B)]
        else:au=ad=None;shape=[('NO_AFRR_OBLIGATION',.25,B)]
        before=E;efc=0.;eu=ed=0.
        for name,h,Y in shape:
            if h<=0:continue
            old=E;C=max(-Y,0);D=max(Y,0);E+=C*h*.92-D*h/.92;e=(C*.92+D/.92)*h/360;efc+=e
            if name=='u':eu+=u*h
            if name=='d':ed+=d*h
            assert -100-1e-6<=Y-F and Y+F<=100+1e-6
            for energy in (old,E):assert 10+F*.5/.92-1e-6<=energy<=190-F*.5*.92+1e-6
            calc=dict(start=iso(q.start),phase=name,hours=h,Y=Y,C=C,D=D,ein=old,eout=E,efc=e)
            if q.start<T:
                got=phases[(iso(q.start),name)]
                for field in ('hours','Y','C','D','ein','eout'):equal(calc[field],got[field])
                equal(e,got['efc'],'efc')
                all_phases.append(calc)
        def times(v,price):
            if not v:return 0.
            assert price is not None and math.isfinite(price)
            return v*price
        cash=dict(da_eur=times(B*.25,q.da_price),fcr_capacity_eur=times(F*.25,q.cap_f),afrr_up_capacity_eur=times(u*.25,q.cap_u),afrr_down_capacity_eur=times(d*.25,q.cap_d),afrr_up_activation_eur=times(eu,q.act_u),afrr_down_activation_eur=-times(ed,q.act_d))
        calculated=dict(start=iso(q.start),end=iso(q.end),year=q.day.year,ein=before,eout=E,efc=efc,cash=cash)
        replay.append(calculated)
        if q.end==T:equal(E,10)
        if q.start<T:
            got=executed[iso(q.start)]
            for field,v in [('da_mw',B),('afrr_up_mw',u),('afrr_down_mw',d),('fcr_mw',F),('ein_mwh',before),('eout_mwh',E),('afrr_up_activation_mwh',eu),('afrr_down_activation_mwh',ed)]:equal(v,got[field])
            equal(efc,got['efc'],'efc')
            for field,v in cash.items():equal(v,got[field],'cash');cash_totals[field]+=v
            equal(sum(cash.values()),got['total_eur'],'cash');efc_year[q.day.year]+=efc
            assert got['afrr_hour_data_valid']==data.hour_a[q.hour] and got['fcr_hour_data_valid']==data.hour_f[q.hour]
            assert got['local_date']==str(q.day)
    assert len(all_phases)==len(phases)
    by_time={parse(r['start']):r for r in replay};used={2025:0.,2026:0.};window_residual=[]
    for tx in transactions:
        s=parse(tx['start']);e=nextday(s,2);plan=[by_time[q.start] for q in data.window(s,e)]
        byyear=defaultdict(float)
        for r in plan:byyear[r['year']]+=r['efc']
        for year,value in byyear.items():
            A=max(0.,budget[year]-used[year]);W=min(A,1/(2*.92)) if year==2026 and e<T else 0
            net=max(0.,A-W);limit=net-min(1e-6,net/2);assert value<=limit+1e-7,(tx['sequence'],year,value,limit)
        last=[q.da_price for q in data.window(nextday(s),e) if q.da_price is not None]
        salvage=.92*max(sum(last)/len(last),0)*(plan[-1]['eout']-10)
        pc=sum(sum(r['cash'].values()) for r in plan)
        equal(pc,tx['metrics']['plan_cash_eur'],'cash');equal(salvage,tx['metrics']['salvage_eur'],'cash');equal(pc+salvage,tx['metrics']['incumbent_eur'],'cash')
        for row in tx['executed_qh']:
            r=by_time[parse(row['delivery_start_utc'])];used[r['year']]+=r['efc']
        for year,value in used.items():equal(value,tx['next_state']['used_efc'][str(year)],'efc')
        equal(tx['next_state']['soc_mwh'],by_time[nextday(s)-timedelta(minutes=15)]['eout'])
    summary=read(run_dir/'summary.json');assert summary['status']=='COMPLETE' and summary['windows']==608 and summary['executed_qh']==58364
    for k,v in cash_totals.items():equal(v,summary['cash_eur'][k],'cash')
    equal(sum(cash_totals.values()),summary['total_eur'],'cash')
    for y,v in efc_year.items():assert v<=budget[y]+1e-7;equal(v,state['used_efc'][str(y)],'efc')
    exported=rows(run_dir/'executed_qh.csv');assert len(exported)==len(executed)
    for row in exported:
        original=executed[row['delivery_start_utc']]
        for k in (*CASH,'total_eur'):equal(row[k],original[k],'cash')
        for k in ('da_mw','afrr_up_mw','afrr_down_mw','fcr_mw','ein_mwh','eout_mwh'):equal(row[k],original[k])
        equal(row['efc'],original['efc'],'efc')
    monthly=defaultdict(lambda:defaultdict(float))
    for row in exported:
        for k in CASH:monthly[row['local_date'][:7]][k]+=float(row[k])
    for row in rows(run_dir/'monthly_cash_eur.csv'):
        for k in CASH:equal(row[k],monthly[row['month']][k],'cash')
    return dict(status='PASS',run_manifest_sha256=digest(run_dir/'manifest.json'),last_transaction_sha256=parent,code_sha256=identity['code_sha256'],input_sha256=identity['input_sha256'],windows=608,formal_qh=58364,observation_qh=96,formal_phase_count=len(phases),native_orders_including_observation=len(orders),cash_eur=dict(cash_totals),total_eur=sum(cash_totals.values()),annual_efc=dict(efc_year),budgets=budget,checks=dict(checks),maximum_absolute_deviations=dict(deviations),solver_status_counts=dict(Counter(str(tx['metrics']['status']) for tx in transactions)),max_objective_gap=max(tx['metrics']['objective_gap'] for tx in transactions),capacity_share_mode=cfg.capacity_share_mode,share_schedule_sha256=hash_object(cfg.monthly_capacity_shares),test_scope='Independent monthly share limits/provenance plus full ordered physical/cash replay; all windows planning objective, frozen chain, EFC budget; formal outputs only')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=validate(a.run);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(canonical(report))
