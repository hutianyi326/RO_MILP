"""Immutable EUR input adapter and market-specific M10-M11 gates."""
from dataclasses import dataclass,asdict
from datetime import timedelta,date
from calendar import isleap
from collections import defaultdict
from pathlib import Path
import csv, hashlib, json, math
from .config import RO, finite, parse, iso, localday, midnight, nextday,hash_object

@dataclass(frozen=True)
class Quarter:
    start: object
    da_id: str
    da_minutes: int
    da_price: float|None
    cap_u: float|None
    cap_d: float|None
    cap_f: float|None
    act_u: float|None
    act_d: float|None
    sys_u: float|None
    sys_d: float|None
    sys_f: float|None
    energy_u: float|None
    energy_d: float|None
    fx_valid: bool=True
    demand_u: float|None=None
    demand_d: float|None=None
    demand_f: float|None=None

    @property
    def end(self):return self.start+timedelta(minutes=15)
    @property
    def hour(self):return self.start.replace(minute=0,second=0,microsecond=0)
    @property
    def day(self):return localday(self.start)
    @property
    def alpha(self):
        if not all(finite(v) for v in (self.sys_u,self.sys_d,self.energy_u,self.energy_d)) or min(self.sys_u,self.sys_d)<=0:return None
        a=(self.energy_u/(.25*self.sys_u),self.energy_d/(.25*self.sys_d))
        if not all(math.isfinite(x) for x in a) or min(a)<0 or sum(a)>1:return None
        return a
    @property
    def a_valid(self):return self.fx_valid and self.alpha is not None and all(finite(x) for x in (self.cap_u,self.cap_d,self.act_u,self.act_d))
    @property
    def f_valid(self):return str(self.day)>='2025-06-01' and self.fx_valid and finite(self.cap_f) and finite(self.sys_f) and self.sys_f>0

class Dataset:
    def __init__(self,quarters,source_hash=None,evidence=None):
        self.quarters=tuple(quarters);self.evidence=evidence or {}
        self.source_hash=source_hash or hash_object([dict(asdict(q),start=iso(q.start)) for q in self.quarters])
        if not self.quarters:raise ValueError('Empty dataset')
        for a,b in zip(self.quarters,self.quarters[1:]):
            if a.end!=b.start:raise ValueError('Duplicate or discontinuous UTC grid')
        self.by_start={q.start:q for q in self.quarters};self.hours=defaultdict(list);self.da=defaultdict(list)
        for q in self.quarters:
            if q.start.tzinfo is None or q.start.utcoffset()!=timedelta(0) or q.start.minute%15 or q.start.second or q.start.microsecond:raise ValueError('Bad UTC QH')
            if q.da_minutes not in (15,60) or not q.da_id:raise ValueError('Invalid DA contract identity')
            self.hours[q.hour].append(q);self.da[q.da_id].append(q)
        if any(len(qs)!=4 or qs[0].start!=h for h,qs in self.hours.items()):raise ValueError('Incomplete capacity hour')
        for k,qs in self.da.items():
            if len(qs)!=qs[0].da_minutes//15 or any(q.da_minutes!=qs[0].da_minutes or q.da_price!=qs[0].da_price for q in qs) or any(a.end!=b.start for a,b in zip(qs,qs[1:])):raise ValueError('Incomplete/inconsistent DA contract '+k)
        self.hour_a={h:all(q.a_valid for q in qs) for h,qs in self.hours.items()}
        self.hour_f={h:all(q.f_valid for q in qs) for h,qs in self.hours.items()}
    def window(self,start,end):
        qs=[];t=start
        while t<end:
            if t not in self.by_start:raise ValueError('Missing lookahead grid '+iso(t))
            qs.append(self.by_start[t]);t+=timedelta(minutes=15)
        return tuple(qs)
    def budgets(self,start,end,override=None):
        # M23 common DA comparison coverage, independent of market switches/H/p.
        result=defaultdict(float);full=defaultdict(float);day=start
        while day<end:
            stop=nextday(day);qs=self.window(day,stop);y=localday(day).year
            result[y]+=600/(366 if isleap(y) else 365)*sum(finite(q.da_price) for q in qs)/len(qs)
            full[y]+=600/(366 if isleap(y) else 365);day=stop
        if override is not None:
            given={int(k):float(v) for k,v in override.items()}
            if set(given)!=set(result) or any(not finite(v) or v<0 or v>full[k]+1e-7 for k,v in given.items()):raise ValueError('Invalid fixed formal-year budgets')
            result=given
        else:result=dict(result)
        y=localday(end).year
        if y not in result:
            qs=self.window(end,nextday(end));result[y]=600/(366 if isleap(y) else 365)*sum(finite(q.da_price) for q in qs)/len(qs)
        return result

def _num(row,key):
    value=row.get(key,'')
    if value=='':return None
    value=float(value)
    if not math.isfinite(value):raise ValueError('Nonfinite input '+key)
    return value

def valid_fx(fixing_day,delivery_day,rate,source_key):
    try:
        fixing=date.fromisoformat(fixing_day);delivery=date.fromisoformat(delivery_day)
    except (ValueError,TypeError):return False
    return (str(fixing)==fixing_day and str(delivery)==delivery_day and fixing<delivery
            and finite(rate) and rate>0 and bool(source_key))

def load_eur(directory):
    directory=Path(directory);repo=directory.parents[3]
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    hashes={};price_files=('prices_eur_qh_20250101_20260831.csv','prices_eur_observation_20260901.csv')
    required=price_files+('capacity_native_hourly_eur.csv',)
    for item in manifest['files']:
        path=(repo/item['path']).resolve()
        if not path.is_relative_to(directory.resolve()):raise ValueError('Manifest file escapes release directory')
        if path in hashes:raise ValueError('Duplicate manifest path '+str(path))
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=item['sha256']:raise ValueError('Input hash mismatch '+str(path))
        hashes[path]=digest
    if any((directory/name).resolve() not in hashes for name in required):raise ValueError('Required consumed CSV missing from manifest')
    consumed={name:hashes[(directory/name).resolve()] for name in required}
    demand={}
    with (directory/'capacity_native_hourly_eur.csv').open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            t=parse(row['delivery_start_utc']);key=(t,row['product'])
            if row['product'] not in ('FCR','aFRRUp','aFRRDown') or key in demand:raise ValueError('Invalid/duplicate demand identity')
            if t.minute or t.second or t.microsecond or parse(row['delivery_end_utc'])!=t+timedelta(hours=1) or row['local_date']!=str(localday(t)):raise ValueError('Demand time mapping mismatch')
            demand[key]=_num(row,'demand_mw')
    qs=[];raw=[]
    for name in price_files:
        with (directory/name).open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                if row['price_currency']!='EUR' or any('_price_ron_' in k for k in row):raise ValueError('Only EUR price inputs accepted')
                t=parse(row['delivery_start_utc'])
                if parse(row['delivery_end_utc'])!=t+timedelta(minutes=15) or row['local_date']!=str(localday(t)) or parse(row['local_time'])!=t or float(row['duration_hours'])!=.25:raise ValueError('Time mapping mismatch')
                fx=_num(row,'fx_ron_per_eur');fxvalid=valid_fx(row['fx_fixing_date'],row['local_date'],fx,row['fx_source_key'])
                n=lambda k:_num(row,k)
                h=t.replace(minute=0,second=0,microsecond=0)
                qs.append(Quarter(t,row['da_contract_id'],int(row['da_native_resolution_minutes']),n('da_price_eur_per_mwh'),n('afrr_up_capacity_price_eur_per_mw_h_proxy'),n('afrr_down_capacity_price_eur_per_mw_h_proxy'),n('fcr_capacity_price_eur_per_mw_h_proxy'),n('afrr_up_activation_price_eur_per_mwh_proxy'),n('afrr_down_activation_price_eur_per_mwh_proxy'),n('afrr_up_accepted_capacity_mw'),n('afrr_down_accepted_capacity_mw'),n('fcr_accepted_capacity_mw'),n('afrr_up_system_activation_energy_mwh'),n('afrr_down_system_activation_energy_mwh'),fxvalid,demand.get((h,'aFRRUp')),demand.get((h,'aFRRDown')),demand.get((h,'FCR'))))
                raw.append(row)
    manifest_hash=hashlib.sha256((directory/'manifest.json').read_bytes()).hexdigest()
    data=Dataset(qs,hash_object({'manifest':manifest_hash,'consumed_csv':consumed}),{'release_directory':str(directory.resolve()),'manifest':manifest,'manifest_sha256':manifest_hash,'consumed_csv_sha256':consumed,'currency':'EUR','mode':'EX_POST_CONDITIONAL'})
    for q,row in zip(qs,raw):
        for key,expected in [('afrr_qh_data_valid',q.a_valid),('afrr_hour_data_valid',data.hour_a[q.hour]),('fcr_qh_data_valid',q.f_valid),('fcr_hour_data_valid',data.hour_f[q.hour]),('da_contract_data_valid',finite(q.da_price))]:
            if row[key] not in ('True','False') or (row[key]=='True')!=expected:raise ValueError('Recomputed gate mismatch '+key+' '+iso(q.start))
    return data
