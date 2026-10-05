"""Independent semantic replay, without using solver rows or SOC equations."""
from collections import defaultdict
from datetime import timedelta
from math import floor
from time import perf_counter
from .config import *

def near(a,b,tol=MW_TOL,label='value'):
    if not finite(a) or not finite(b) or abs(a-b)>tol:raise ValueError(f'Audit {label}: {a} != {b}')
def cash_near(a,b,label):near(a,b,1e-5+1e-9*max(abs(a),abs(b)),label)
def bounded(v,lo,hi,label):
    if not finite(v) or v<lo-MW_TOL or v>hi+MW_TOL:raise ValueError('Audit bound '+label)

def audit_window(data,cfg,result,start,formal_start,formal_end,soc,used,budgets,frozen):
    timer=perf_counter();end=nextday(start,2);qs=data.window(start,end);orders=result['orders']
    expected={'DA|'+q.da_id for q in qs}|{p+'|'+iso(q.hour) for q in qs for p in PRODUCTS}
    if set(orders)!=expected:raise ValueError('Audit incomplete order coverage')
    for key,o in orders.items():
        p=o['product'];t=parse(o['start']);stop=parse(o['end']);v=o['amount_mw'];gate=event(t,13 if p=='DA' else 9)
        if o['key']!=key or parse(o['gate'])!=gate or parse(o['result'])!=event(t,14 if p=='DA' else 10):raise ValueError('Audit order identity/event')
        if p=='DA':
            group=data.da[key[3:]]
            if t!=group[0].start or stop!=group[-1].end:raise ValueError('Audit DA interval')
            valid=all(finite(q.da_price) for q in group);bound=cfg.power_mw if valid else 0.
            bounded(v,-bound,bound,'DA contract')
        else:
            if key!=p+'|'+iso(t) or stop!=t+timedelta(hours=1):raise ValueError('Audit capacity interval')
            near(v,round(v),label='capacity integrality');group=data.hours[t]
            if p=='F':
                valid=all(str(q.day)>='2025-06-01' and q.fx_valid and finite(q.cap_f) and finite(q.sys_f) and q.sys_f>0 for q in group)
            else:
                valid=True
                for q in group:
                    values=(q.sys_u,q.sys_d,q.energy_u,q.energy_d,q.cap_u,q.cap_d,q.act_u,q.act_d)
                    if not q.fx_valid or not all(finite(x) for x in values) or min(q.sys_u,q.sys_d)<=0:valid=False;continue
                    au=q.energy_u*4/q.sys_u;ad=q.energy_d*4/q.sys_d
                    if min(au,ad)<0 or au+ad>1:valid=False
            rate=cfg.p(localday(t),p);valid=valid and cfg.enabled(p) and rate is not None and rate>0
            quantity=[getattr(q,{'u':'sys_u','d':'sys_d','F':'sys_f'}[p]) for q in group]
            bound=floor(min(cfg.power_mw,cfg.qualified(p),*quantity)) if valid else 0
            if p=='F':bound=min(bound,sum(floor(x) for x in cfg.units))
            bounded(v,0,bound,'capacity gate/quantity')
            if p=='F':
                vector=o['units_mw']
                if len(vector)!=len(cfg.units):raise ValueError('Audit FCR vector length')
                for x,cap in zip(vector,cfg.units):near(x,round(x),label='FCR unit integer');bounded(x,0,floor(cap),'FCR unit cap')
                near(sum(vector),v,label='FCR aggregation')
        if gate<start:
            old=frozen.get(key)
            if old is None:
                if start!=formal_start:raise ValueError('Audit missing frozen key')
                near(v,0,label='Initial no-prior commitment')
            else:
                near(v,old['amount_mw'],label='Frozen MW')
                for name in ('key','product','start','end','gate','result'):
                    if old[name]!=o[name]:raise ValueError('Audit frozen identity')
                if p=='F' and old['units_mw']!=o['units_mw']:raise ValueError('Audit frozen FCR vector')
    E=soc;bounded(E,cfg.e_min,cfg.e_max,'starting SOC');rows=[];phase_rows=[];year_efc=defaultdict(float);cash_total=0.;cursor=0
    for q in qs:
        B=orders['DA|'+q.da_id]['amount_mw'];R={p:orders[p+'|'+iso(q.hour)]['amount_mw'] for p in PRODUCTS};u,d,F=R['u'],R['d'],R['F']
        # Reconstruct both capacity gate/result and DA gate/result/delivery states.
        cap_event=event(q.start,9);da_result=event(q.start,14)
        for t in (cap_event,event(q.start,10),event(q.start,13),da_result,q.start):
            base=B if t>=da_result else 0.;ru=u if t>=cap_event else 0.;rd=d if t>=cap_event else 0.;rf=F if t>=cap_event else 0.
            bounded(base,-cfg.power_mw,cfg.power_mw,'event base')
            bounded(base+ru+rf,-cfg.power_mw,cfg.power_mw,'event upward');bounded(base-rd-rf,-cfg.power_mw,cfg.power_mw,'event downward')
        if cfg.enabled('u') and data.hour_a[q.hour]:
            au=q.energy_u/(q.sys_u*.25);ad=q.energy_d/(q.sys_d*.25)
            shape=[('d',.25*ad,B-d),('u',.25*au,B+u),('0',.25*(1-au-ad),B)]
        else:au=ad=None;shape=[('NO_AFRR_OBLIGATION',.25,B)]
        before=E;qe=0.;act_energy={'u':0.,'d':0.}
        for phase,h,Y in shape:
            if h<=0:continue
            C=max(-Y,0.);D=max(Y,0.);oldE=E
            bounded(Y-F,-cfg.power_mw,cfg.power_mw,'phase lower power');bounded(Y+F,-cfg.power_mw,cfg.power_mw,'phase upper power')
            E+=C*h*.92-D*h/.92
            for value in (oldE,E):bounded(value,cfg.e_min+F*.5/.92,cfg.e_max-.92*F*.5,'SOC/FCR buffer')
            efc=(C*h*.92+D*h/.92)/cfg.efc_denominator;qe+=efc
            if phase in ('u','d'):act_energy[phase]+=R[phase]*h
            calc=dict(start=iso(q.start),phase=phase,hours=h,Y=Y,C=C,D=D,ein=oldE,eout=E,efc=efc)
            if cursor>=len(result['path']):raise ValueError('Audit missing solver phase')
            solved=result['path'][cursor];cursor+=1
            if calc['start']!=solved['start'] or phase!=solved['phase']:raise ValueError('Audit phase identity')
            for k in ('hours','Y','C','D','ein','eout','efc'):near(calc[k],solved[k],EFC_TOL if k=='efc' else MW_TOL,'phase '+k)
            phase_rows.append(calc)
        near(sum(h for _,h,_ in shape),.25,label='phase duration')
        if q.end==formal_end:near(E,cfg.e_min,label='formal terminal SOC')
        cash=dict.fromkeys(CASH,0.)
        if B:
            if not finite(q.da_price):raise ValueError('Audit missing DA cash price')
            cash['da_eur']=B*.25*q.da_price
        for p,name,price in [('u','afrr_up_capacity_eur',q.cap_u),('d','afrr_down_capacity_eur',q.cap_d),('F','fcr_capacity_eur',q.cap_f)]:
            if R[p]:
                factor=cfg.p(q.day,p)
                if not finite(price) or factor is None:raise ValueError('Audit unknown capacity income')
                cash[name]=R[p]*.25*factor*price
        for p,price,sign,name in [('u',q.act_u,1,'afrr_up_activation_eur'),('d',q.act_d,-1,'afrr_down_activation_eur')]:
            if act_energy[p]:
                if not finite(price):raise ValueError('Audit unknown activation income')
                cash[name]=sign*price*act_energy[p]
        total=sum(cash.values());cash_total+=total;year_efc[q.day.year]+=qe
        rows.append(dict(delivery_start_utc=iso(q.start),delivery_end_utc=iso(q.end),local_date=str(q.day),da_contract_id=q.da_id,da_mw=B,afrr_up_mw=u,afrr_down_mw=d,fcr_mw=F,ein_mwh=before,eout_mwh=E,efc=qe,afrr_up_activation_mwh=act_energy['u'],afrr_down_activation_mwh=act_energy['d'],da_data_valid=finite(q.da_price),afrr_hour_data_valid=data.hour_a[q.hour],fcr_hour_data_valid=data.hour_f[q.hour],initial_no_prior_commitment=orders['DA|'+q.da_id]['commitment']=='INITIAL_NO_PRIOR_COMMITMENT',**cash,total_eur=total))
    if cursor!=len(result['path']):raise ValueError('Audit extra solver phases')
    terminal_year=localday(formal_end-timedelta(minutes=15)).year
    for y,value in year_efc.items():
        old=used.get(y,0.);limit=budgets[y]
        if not finite(old) or old < -EFC_TOL or old>limit+EFC_TOL:raise ValueError('Audit executed EFC')
        rem=max(0.,limit-old);hold=min(rem,1/(2*.92)) if y==terminal_year and end<formal_end else 0.
        net=max(0.,rem-hold);allowed=net-min(1e-6,net/2)
        if value>allowed+EFC_TOL:raise ValueError('Audit window EFC allowance')
    prices=[q.da_price for q in qs if q.day==localday(end-timedelta(minutes=15)) and finite(q.da_price)]
    rate=.92*max(sum(prices)/len(prices),0.) if prices else 0.
    cash_near(rate,result['salvage_rate'],'salvage rate');salvage=rate*(E-cfg.e_min)
    cash_near(cash_total+salvage,result['metrics']['incumbent_eur'],'objective reconstruction')
    result['metrics'].update(audit_seconds=perf_counter()-timer,audit='PASS',plan_cash_eur=cash_total,salvage_eur=salvage,phase_count=len(phase_rows),qh_count=len(rows))
    return {'qh':rows,'phases':phase_rows,'year_efc':dict(year_efc),'end_soc':E}
