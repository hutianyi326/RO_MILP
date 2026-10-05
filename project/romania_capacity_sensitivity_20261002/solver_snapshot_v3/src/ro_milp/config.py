from dataclasses import dataclass, field, asdict
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo
from math import ceil, isfinite, floor
import hashlib, json

RO=ZoneInfo('Europe/Bucharest'); UTC=timezone.utc
MW_TOL=1e-6; EFC_TOL=1e-7
PRODUCTS=('u','d','F')
CASH=('da_eur','fcr_capacity_eur','afrr_up_capacity_eur','afrr_down_capacity_eur','afrr_up_activation_eur','afrr_down_activation_eur')

def finite(x):return x is not None and not isinstance(x,bool) and isfinite(float(x))
def iso(t):return t.astimezone(UTC).isoformat().replace('+00:00','Z')
def parse(t):
    d=datetime.fromisoformat(t.replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('Timezone required')
    return d.astimezone(UTC)
def midnight(day):
    if isinstance(day,str):day=date.fromisoformat(day)
    return datetime.combine(day,time(),RO).astimezone(UTC)
def localday(t):return t.astimezone(RO).date()
def nextday(t,n=1):return midnight(localday(t)+timedelta(days=n))
def event(t,hour):return datetime.combine(localday(t)-timedelta(days=1),time(hour),RO).astimezone(UTC)
def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def hash_object(obj):return hashlib.sha256(canonical(obj).encode()).hexdigest()

@dataclass(frozen=True)
class Config:
    power_mw: float=100.
    hours: int=2
    market: str='DA+aFRR+FCR'
    p_up: float=1.
    p_down: float=1.
    p_fcr: float=1.
    daily_p: dict=field(default_factory=dict)
    qualification_up_mw: float|None=None
    qualification_down_mw: float|None=None
    qualification_fcr_mw: float|None=None
    fcr_unit_caps: tuple=()
    time_limit: float=30.
    mip_rel_gap: float=1e-4
    presolve: bool=True
    formulation: str='compact'

    def __post_init__(self):
        if not finite(self.power_mw) or self.power_mw<=0:raise ValueError('power_mw must be positive finite')
        if self.hours not in (2,4):raise ValueError('Only approved 2h/4h configurations')
        if self.market not in ('DA','DA+aFRR','DA+FCR','DA+aFRR+FCR'):raise ValueError('Unsupported markets')
        if self.formulation not in ('compact','reference'):raise ValueError('Unknown formulation')
        for p in (self.p_up,self.p_down,self.p_fcr):
            if not finite(p) or not 0<=p<=1:raise ValueError('Capacity income coefficient outside [0,1]')
        for day,ps in self.daily_p.items():
            date.fromisoformat(day)
            if set(ps)!=set(PRODUCTS):raise ValueError('Daily p needs u,d,F; null explicitly disables new orders')
            if any(p is not None and (not finite(p) or not 0<=p<=1) for p in ps.values()):raise ValueError('Invalid daily p')
        for q in (self.qualification_up_mw,self.qualification_down_mw,self.qualification_fcr_mw):
            if q is not None and (not finite(q) or q<0):raise ValueError('Invalid qualification')
        if not finite(self.time_limit) or self.time_limit<=0 or not finite(self.mip_rel_gap) or self.mip_rel_gap<0:raise ValueError('Invalid solve limits')
        if self.fcr_unit_caps and (any(not finite(v) or v<0 or v>20 for v in self.fcr_unit_caps) or sum(self.fcr_unit_caps)>self.power_mw+1e-9):raise ValueError('Invalid FCR research unit caps')

    @property
    def e_min(self):return .05*self.power_mw*self.hours
    @property
    def e_max(self):return .95*self.power_mw*self.hours
    @property
    def efc_denominator(self):return 2*(self.e_max-self.e_min)
    @property
    def units(self):
        return tuple(self.fcr_unit_caps) or (self.power_mw/ceil(self.power_mw/20),)*ceil(self.power_mw/20)
    def p(self,day,product):
        if self.daily_p:return self.daily_p.get(str(day),{}).get(product)
        return {'u':self.p_up,'d':self.p_down,'F':self.p_fcr}[product]
    def qualified(self,product):
        q={'u':self.qualification_up_mw,'d':self.qualification_down_mw,'F':self.qualification_fcr_mw}[product]
        return self.power_mw if q is None else q
    def enabled(self,product):return ('FCR' if product=='F' else 'aFRR') in self.market
    def as_dict(self):return asdict(self)

def allocate_fcr(total,caps):
    if not finite(total) or total<0 or abs(total-round(total))>MW_TOL:raise ValueError('FCR total must be integer')
    left=int(round(total));result=[]
    for cap in caps:
        v=min(floor(cap),left);result.append(v);left-=v
    if left:raise ValueError('FCR cannot be allocated to research units')
    return result
