"""M01-M29 sparse single-window MILP; positive-part projection P01-P07."""
from dataclasses import dataclass
from collections import defaultdict
from datetime import timedelta
from math import floor
from time import perf_counter
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix
from .config import *

@dataclass
class Expr:
    a: dict
    c: float=0.
    def __add__(self, other):
        other=as_expr(other);a=self.a.copy()
        for i,v in other.a.items():
            a[i]=a.get(i,0)+v
            if a[i]==0:del a[i]
        return Expr(a,self.c+other.c)
    __radd__=__add__
    def __neg__(self):return self*-1
    def __sub__(self,o):return self+-as_expr(o)
    def __rsub__(self,o):return as_expr(o)+-self
    def __mul__(self,v):return Expr({i:x*v for i,x in self.a.items() if x*v!=0},self.c*v)
    __rmul__=__mul__
    def __truediv__(self,v):return self*(1/v)
    def value(self,x):return self.c+sum(v*x[i] for i,v in self.a.items())
    def key(self):return (tuple(sorted(self.a.items())),self.c)
def as_expr(v):return v if isinstance(v,Expr) else Expr({},float(v))

class Matrix:
    def __init__(self):
        self.lb=[];self.ub=[];self.kind=[];self.names=[];self.rows=[];self.seen=set()
    def var(self,name,lo,hi,kind='continuous'):
        if lo==hi:return as_expr(lo)
        i=len(self.lb);self.lb.append(lo);self.ub.append(hi);self.kind.append(kind);self.names.append(name)
        return Expr({i:1.})
    def row(self,e,lo=-np.inf,hi=np.inf):
        e=as_expr(e);lo-=e.c;hi-=e.c
        if not e.a:
            if lo>MW_TOL or hi < -MW_TOL:raise ValueError('Infeasible constant constraint')
            return
        k=(tuple(sorted(e.a.items())),lo,hi)
        if k not in self.seen:self.rows.append((e.a,lo,hi));self.seen.add(k)
    def bounds(self,e):
        return (e.c+sum(v*(self.lb[i] if v>0 else self.ub[i]) for i,v in e.a.items()),e.c+sum(v*(self.ub[i] if v>0 else self.lb[i]) for i,v in e.a.items()))
    def solve(self,obj,cfg):
        n=len(self.lb);rr=[];cc=[];vv=[]
        for r,(a,_,_) in enumerate(self.rows):
            for c,v in a.items():rr.append(r);cc.append(c);vv.append(v)
        mat=coo_matrix((vv,(rr,cc)),shape=(len(self.rows),n)).tocsc()
        stats={'variables':n,'rows':len(self.rows),'nnz':len(vv),**{k:self.kind.count(k) for k in ('continuous','integer','binary')}}
        if not n:return np.zeros(0),dict(stats,status=0,message='All decisions fixed; constant constraints checked',raw_gap=0.,bound_eur=obj.c,incumbent_eur=obj.c,objective_gap=0.,nodes=0,solve_seconds=0.)
        c=np.zeros(n)
        for i,v in obj.a.items():c[i]=-v
        constraints=LinearConstraint(mat,np.array([r[1] for r in self.rows]),np.array([r[2] for r in self.rows]))
        t=perf_counter()
        result=milp(c,integrality=np.array([int(k!='continuous') for k in self.kind]),bounds=Bounds(self.lb,self.ub),constraints=constraints,options={'time_limit':cfg.time_limit,'mip_rel_gap':cfg.mip_rel_gap,'presolve':cfg.presolve})
        elapsed=perf_counter()-t
        if result.status not in (0,1) or result.x is None or not np.all(np.isfinite(result.x)):raise ValueError('No acceptable incumbent: '+str(result.message))
        x=result.x.copy()
        for i,k in enumerate(self.kind):
            if k!='continuous':
                if abs(x[i]-round(x[i]))>MW_TOL:raise ValueError('Nonintegral incumbent')
                x[i]=round(x[i])
        if np.max(np.maximum(np.array(self.lb)-x,x-np.array(self.ub)))>MW_TOL:raise ValueError('Incumbent column violation')
        for a,lo,hi in self.rows:
            v=sum(x[i]*coef for i,coef in a.items())
            if v<lo-MW_TOL or v>hi+MW_TOL:raise ValueError('Incumbent row violation')
        inc=obj.value(x);dual=getattr(result,'mip_dual_bound',None)
        bound=-float(dual)+obj.c if finite(dual) else (inc if result.status==0 else None)
        gap=None if bound is None else max(0.,bound-inc)/max(abs(inc),1e-10)
        raw=getattr(result,'mip_gap',None)
        return x,dict(stats,status=int(result.status),message=str(result.message),raw_gap=float(raw) if finite(raw) else None,bound_eur=bound,incumbent_eur=inc,objective_gap=gap,nodes=int(getattr(result,'mip_node_count',0) or 0),solve_seconds=elapsed)

def order_specs(data,qs,cfg):
    """Full native orders; gates are the explicitly assumed local D-1 timetable."""
    specs={}
    for q in qs:
        k='DA|'+q.da_id
        if k not in specs:
            group=data.da[q.da_id];valid=all(finite(v.da_price) for v in group)
            specs[k]=dict(key=k,product='DA',start=iso(group[0].start),end=iso(group[-1].end),gate=iso(event(group[0].start,13)),result=iso(event(group[0].start,14)),lower=-cfg.power_mw if valid else 0.,upper=cfg.power_mw if valid else 0.,reason='VALID' if valid else 'DA_DATA_INVALID')
        for prod in PRODUCTS:
            k=prod+'|'+iso(q.hour)
            if k in specs:continue
            group=data.hours[q.hour];valid=data.hour_f[q.hour] if prod=='F' else data.hour_a[q.hour]
            p=cfg.p(q.day,prod);reason='VALID';bound=0.
            if not cfg.enabled(prod):reason='MARKET_DISABLED'
            elif not valid:reason='DATA_INVALID'
            elif p is None:reason='P_MISSING'
            elif p==0:reason='P_ZERO'
            else:
                qty=[getattr(v,{'u':'sys_u','d':'sys_d','F':'sys_f'}[prod]) for v in group]
                if not all(finite(v) and v>0 for v in qty):reason='QUANTITY_INVALID'
                else:
                    bound=floor(min(cfg.power_mw,cfg.qualified(prod),*qty))
                    if prod=='F':bound=min(bound,sum(floor(c) for c in cfg.units))
            specs[k]=dict(key=k,product=prod,start=iso(q.hour),end=iso(q.hour+timedelta(hours=1)),gate=iso(event(q.hour,9)),result=iso(event(q.hour,10)),lower=0.,upper=bound,reason=reason,p=p)
    if any(parse(s['start'])<qs[0].start or parse(s['end'])>qs[-1].end for s in specs.values()):raise ValueError('Window splits native order')
    return specs

def allowances(budgets,used,formal_end,window_end):
    result={};terminal_year=localday(formal_end-timedelta(minutes=15)).year
    if any(int(y) not in budgets for y in used):raise ValueError('Unbudgeted executed year')
    for y,limit in budgets.items():
        u=used.get(y,0.)
        if not finite(u) or u < -EFC_TOL or u>limit+EFC_TOL:raise ValueError('Executed EFC exceeds fixed budget')
        available=max(0.,limit-u);reserve=min(available,1/(2*.92)) if y==terminal_year and window_end<formal_end else 0.
        result[y]=max(0.,available-reserve-1e-6)
    return result

def phases(q,data,cfg):
    if cfg.enabled('u') and data.hour_a[q.hour]:
        u,d=q.alpha
        return [(name,h) for name,h in [('d',.25*d),('u',.25*u),('0',.25*(1-u-d))] if h>0]
    return [('NO_AFRR_OBLIGATION',.25)]

def solve_window(data,cfg,start,formal_start,formal_end,soc,used,budgets,frozen):
    build=perf_counter();end=nextday(start,2);qs=data.window(start,end)
    specs=order_specs(data,qs,cfg);m=Matrix();orders={};unit_expr={}
    for key,s in specs.items():
        lo,hi=s['lower'],s['upper'];past=parse(s['gate'])<start
        if past:
            old=frozen.get(key)
            if old is None:
                if start!=formal_start:raise ValueError('Missing frozen order '+key)
                amount=0.;s['commitment']='INITIAL_NO_PRIOR_COMMITMENT'
            else:
                for field in ('product','start','end','gate','result'):
                    if old[field]!=s[field]:raise ValueError('Frozen identity conflict '+key)
                amount=old['amount_mw'];s['commitment']='FROZEN'
                if not finite(amount) or amount<lo-MW_TOL or amount>hi+MW_TOL:raise ValueError('Frozen commitment conflicts with input '+key)
                if s['product']=='F':
                    units=old['units_mw']
                    if len(units)!=len(cfg.units) or any(not finite(v) or v<0 or v>floor(cap) or abs(v-round(v))>MW_TOL for v,cap in zip(units,cfg.units)) or abs(sum(units)-amount)>MW_TOL:raise ValueError('Frozen FCR unit conflict')
                    unit_expr[key]=[as_expr(v) for v in units]
            lo=hi=amount
        else:s['commitment']='NEW'
        if s['product']=='F' and cfg.formulation=='reference' and lo!=hi:
            ue=[m.var(key+'|unit'+str(i),0,floor(cap),'integer') for i,cap in enumerate(cfg.units)]
            orders[key]=sum(ue,as_expr(0));m.row(orders[key],lo,hi);unit_expr[key]=ue
        else:orders[key]=m.var(key,lo,hi,'continuous' if s['product']=='DA' else 'integer')
    objective=as_expr(0);energy=as_expr(soc);groups={};path=[];efc=defaultdict(lambda:as_expr(0))
    for q in qs:
        B=orders['DA|'+q.da_id];R={r:orders[r+'|'+iso(q.hour)] for r in PRODUCTS};u,d,F=R['u'],R['d'],R['F']
        m.row(u+F,hi=cfg.power_mw);m.row(d+F,hi=cfg.power_mw)
        m.row(B+u+F,hi=cfg.power_mw);m.row(-B+d+F,hi=cfg.power_mw)
        if finite(q.da_price):objective+=.25*q.da_price*B
        for r,price in [('u',q.cap_u),('d',q.cap_d),('F',q.cap_f)]:
            if R[r].a or R[r].c:
                p=cfg.p(q.day,r)
                if not finite(price) or p is None:raise ValueError('Unknown committed capacity cash')
                objective+=.25*p*price*R[r]
        if q.alpha is not None:
            au,ad=q.alpha
            for r,coef in [('u',au),('d',-ad)]:
                if R[r].a or R[r].c:
                    price=q.act_u if r=='u' else q.act_d
                    if not finite(price):raise ValueError('Unknown committed activation cash')
                    objective+=.25*coef*price*R[r]
        for name,h in phases(q,data,cfg):
            Y=B-d if name=='d' else B+u if name=='u' else B
            key=Y.key()
            if cfg.formulation=='compact' and key in groups:C,D=groups[key]
            else:
                low,high=m.bounds(Y);low=max(-cfg.power_mw,low);high=min(cfg.power_mw,high)
                if low>=0:C,D=as_expr(0),Y
                elif high<=0:C,D=-Y,as_expr(0)
                elif cfg.formulation=='reference':
                    C=m.var('C',0,cfg.power_mw);D=m.var('D',0,cfg.power_mw);z=m.var('z',0,1,'binary')
                    m.row(D-C-Y,0,0);m.row(D-cfg.power_mw*z,hi=0);m.row(C+cfg.power_mw*z,hi=cfg.power_mw)
                else:
                    D=m.var('D+',0,high);z=m.var('z',0,1,'binary');C=D-Y
                    m.row(D-Y,lo=0);m.row(D-high*z,hi=0);m.row(D-Y-low*z,hi=-low)
                if cfg.formulation=='compact':groups[key]=(C,D)
            previous=energy;change=(.92*C-D/.92)*h
            if previous.a or change.a:
                energy=m.var('SOC',cfg.e_min,cfg.e_max);m.row(energy-previous-change,0,0)
            else:energy=previous+change;m.row(energy,cfg.e_min,cfg.e_max)
            for E in (previous,energy):
                if F.a or F.c:
                    m.row(E-F*(.5/.92),lo=cfg.e_min);m.row(E+F*(.5*.92),hi=cfg.e_max)
            amount=(.92*C+D/.92)*h/cfg.efc_denominator;efc[q.day.year]+=amount
            path.append(dict(start=iso(q.start),phase=name,hours=h,Y=Y,C=C,D=D,ein=previous,eout=energy,efc=amount))
        if q.end==formal_end:m.row(energy,cfg.e_min,cfg.e_min)
    limits=allowances(budgets,used,formal_end,end)
    for y,v in efc.items():
        if y not in limits:raise ValueError('Missing year budget')
        m.row(v,hi=limits[y])
    last=[q.da_price for q in qs if q.day==localday(end-timedelta(minutes=15)) and finite(q.da_price)]
    salvage_rate=.92*max(sum(last)/len(last),0.) if last else 0.
    objective+=salvage_rate*(energy-cfg.e_min)
    build_seconds=perf_counter()-build;x,metrics=m.solve(objective,cfg);metrics['build_seconds']=build_seconds
    result_orders={}
    for k,s in specs.items():
        value=orders[k].value(x)
        if s['product']!='DA':
            if abs(value-round(value))>MW_TOL:raise ValueError('Noninteger fixed capacity')
            value=int(round(value))
        record=dict(s,amount_mw=value)
        if s['product']=='F':record['units_mw']=[int(round(v.value(x))) for v in unit_expr[k]] if k in unit_expr else allocate_fcr(value,cfg.units)
        result_orders[k]=record
    solved_path=[{k:(v.value(x) if isinstance(v,Expr) else v) for k,v in row.items()} for row in path]
    return {'orders':result_orders,'path':solved_path,'metrics':metrics,'salvage_rate':salvage_rate,'window_start':iso(start),'window_end':iso(end),'limits':limits}
