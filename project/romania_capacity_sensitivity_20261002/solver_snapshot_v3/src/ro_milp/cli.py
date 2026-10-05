import argparse,json
from pathlib import Path
from .config import Config, midnight, canonical
from .inputs import load_eur
from .rolling import run,posthoc

def main(argv=None):
    parser=argparse.ArgumentParser(description='RO v1.1 EUR-only conditional ex-post MILP')
    sub=parser.add_subparsers(dest='command',required=True)
    default=Path(__file__).resolve().parents[2]/'data/processed/RO/prices_eur_v1_20261002'
    p=sub.add_parser('run');p.add_argument('--data',type=Path,default=default);p.add_argument('--start',default='2025-01-01');p.add_argument('--end',default='2026-09-01',help='Exclusive local date');p.add_argument('--output',type=Path,required=True)
    p.add_argument('--hours',type=int,choices=(2,4),default=2);p.add_argument('--power',type=float,default=100);p.add_argument('--market',choices=('DA','DA+aFRR','DA+FCR','DA+aFRR+FCR'),default='DA+aFRR+FCR')
    for prod in ('up','down','fcr'):p.add_argument('--p-'+prod,type=float,default=1.)
    for prod in ('up','down','fcr'):p.add_argument('--qualification-'+prod,type=float)
    p.add_argument('--fcr-unit-caps',type=float,nargs='+');p.add_argument('--daily-p-file',type=Path);p.add_argument('--budget-file',type=Path);p.add_argument('--time-limit',type=float,default=30.);p.add_argument('--gap',type=float,default=1e-4);p.add_argument('--no-presolve',action='store_true');p.add_argument('--formulation',choices=('compact','reference'),default='compact');p.add_argument('--resume',action='store_true');p.add_argument('--max-windows',type=int)
    p=sub.add_parser('preflight');p.add_argument('--data',type=Path,default=default)
    p=sub.add_parser('posthoc');p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    for prod in ('up','down','fcr'):p.add_argument('--p-'+prod,type=float,required=True)
    a=parser.parse_args(argv)
    try:
        if a.command=='posthoc':result=posthoc(a.source,a.output,a.p_up,a.p_down,a.p_fcr)
        else:
            data=load_eur(a.data)
            if a.command=='preflight':result={'status':'PASS','qh':len(data.quarters),'source_hash':data.source_hash,'afrr_valid_hours':sum(data.hour_a.values()),'fcr_valid_hours':sum(data.hour_f.values()),'budgets':data.budgets(midnight('2025-01-01'),midnight('2026-09-01'))}
            else:
                read=lambda p:json.loads(p.read_text(encoding='utf-8-sig')) if p else None
                cfg=Config(power_mw=a.power,hours=a.hours,market=a.market,p_up=a.p_up,p_down=a.p_down,p_fcr=a.p_fcr,qualification_up_mw=a.qualification_up,qualification_down_mw=a.qualification_down,qualification_fcr_mw=a.qualification_fcr,fcr_unit_caps=tuple(a.fcr_unit_caps or ()),daily_p=read(a.daily_p_file) or {},time_limit=a.time_limit,mip_rel_gap=a.gap,presolve=not a.no_presolve,formulation=a.formulation)
                result=run(data,cfg,midnight(a.start),midnight(a.end),a.output,read(a.budget_file),a.resume,a.max_windows)
        print(canonical(result));return 2 if result.get('status')=='BLOCKED' else 0
    except (ValueError,OSError,KeyError) as exc:
        print(canonical({'status':'ERROR','message':str(exc)}));return 2

if __name__=='__main__':raise SystemExit(main())
