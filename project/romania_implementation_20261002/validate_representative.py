"""Reproducible real-data implementation checks, not full-history revenue study."""
import sys,json,argparse
from pathlib import Path
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'src'))
from ro_milp.config import Config,midnight,canonical
from ro_milp.inputs import load_eur
from ro_milp.rolling import run,code_hash,read_json

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    data=load_eur(root/'data/processed/RO/prices_eur_v1_20261002')
    cases=[('january_no_fcr','2025-01-01','2025-01-04',2,1.),('spring_dst','2025-03-29','2025-04-01',2,1.),('fcr_first_prices','2025-06-05','2025-06-09',2,1.),('da_resolution_change','2025-09-30','2025-10-03',2,1.),('autumn_dst_gap','2025-10-25','2025-10-28',2,1.),('cross_year','2025-12-30','2026-01-02',2,1.),('activation_price_gap','2026-08-21','2026-08-24',2,1.),('terminal_and_observation','2026-08-30','2026-09-01',2,1.),('four_hour_p80','2025-06-07','2025-06-10',4,.8)]
    results=[]
    for name,start,end,h,p in cases:
        cfg=Config(hours=h,p_up=p,p_down=p,p_fcr=p,time_limit=30.,mip_rel_gap=1e-4)
        summary=run(data,cfg,midnight(start),midnight(end),args.output/name)
        row=dict(case=name,start=start,end_exclusive=end,hours=h,p=p,**summary);results.append(row)
        print(canonical(row),flush=True)
    report={'classification':'IMPLEMENTATION_REPRESENTATIVE_WINDOWS_ONLY','code_sha256':code_hash(),'data_sha256':data.source_hash,'input_qh':len(data.quarters),'full_period_budgets':data.budgets(midnight('2025-01-01'),midnight('2026-09-01')),'cases':results,'status':'PASS' if all(r['status']=='COMPLETE' for r in results) else 'FAIL'}
    (args.output/'validation.json').write_text(canonical(report)+'\n',encoding='utf-8')
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
