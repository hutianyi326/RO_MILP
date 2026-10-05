"""Read-only cross-scenario reconciliation, independent of comparison builder."""
import argparse
import csv
import hashlib
import json
from decimal import Decimal as D
from pathlib import Path

CASH = ('da_eur', 'fcr_capacity_eur', 'afrr_up_capacity_eur',
        'afrr_down_capacity_eur', 'afrr_up_activation_eur', 'afrr_down_activation_eur')
MARKETS = ('DA', 'FCR_cap', 'cap_up', 'cap_down', 'act_up', 'act_down')

def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def validate(root):
    report = root / 'comparison'
    manifest = read(report / 'comparison_manifest.json')
    for name, digest in manifest['files'].items():
        assert sha(report / name) == digest, name
    totals = {}
    checks = 0
    max_money_error = D(0)

    def close(actual, expected, tolerance='0.001'):
        nonlocal checks, max_money_error
        error = abs(D(str(actual)) - D(str(expected)))
        assert error <= D(tolerance), (actual, expected, error)
        checks += 1
        if tolerance == '0.001':
            max_money_error = max(max_money_error, error)

    for percent in (100, 80, 60):
        scenario = f'p{percent}'
        run = root / (scenario + '_run')
        source = rows(run / 'executed_qh.csv')
        assert len(source) == 58364
        sums = {c: sum((D(r[c]) for r in source), D(0)) for c in CASH}
        total = sum(sums.values())
        totals[percent] = sums
        summary = next(r for r in rows(report / 'scenario_summary.csv') if r['scenario'] == scenario)
        close(summary['capacity_income_coefficient'], D(percent)/100, '0')
        close(summary['total_eur'], total)
        close(D(summary['total_kEUR_per_MW'])*100000, total)
        for c in CASH:
            close(summary[c], sums[c])
        cap = sum(sums[c] for c in CASH[1:4])
        close(summary['capacity_cash_eur'], cap)
        close(summary['da_and_activation_cash_eur'], total-cap)
        close(summary['total_efc'], sum((D(r['efc']) for r in source), D(0)), '0.0000001')
        baseline = sum(totals[100].values())
        baseline_cap = sum(totals[100][c] for c in CASH[1:4])
        fixed = baseline + (D(percent)/100-1)*baseline_cap
        close(summary['delta_eur_vs_p100'], total-baseline)
        close(summary['change_pct_vs_p100'], (total/baseline-1)*100, '0.00000001')
        close(summary['p100_trajectory_capacity_repricing_eur'], fixed)
        close(summary['reoptimization_and_rolling_effect_eur'], total-fixed)
        for field in ('da_mw', 'fcr_mw', 'afrr_up_mw', 'afrr_down_mw'):
            close(summary['average_'+field], sum((D(r[field]) for r in source), D(0))/len(source), '0.00000001')
        for field in ('afrr_up_activation_mwh', 'afrr_down_activation_mwh'):
            close(summary[field], sum((D(r[field]) for r in source), D(0)), '0.00001')
        for market, field in zip(MARKETS, CASH):
            row = next(r for r in rows(report/'market_comparison.csv') if r['scenario']==scenario and r['market']==market)
            close(row['cash_eur'], sums[field])
            close(D(row['kEUR_per_MW'])*100000, sums[field])
            close(row['delta_eur_vs_p100'], sums[field]-totals[100][field])
        for name in ('annual', 'monthly', 'rolling_12m', 'hourly'):
            exported = rows(report/(name+'_comparison.csv'))
            selected = [{k:v for k,v in r.items() if k!='scenario'} for r in exported if r['scenario']==scenario]
            original = rows(root/(scenario+'_report')/(name+'.csv'))
            assert len(selected)==len(original)
            for a,b in zip(selected,original):
                assert a.keys()==b.keys()
                for key in a:
                    try:
                        close(a[key], b[key], '0.000000001')
                    except Exception:
                        assert a[key]==b[key], (name,key,a[key],b[key])
        for name in ('validation','presentation_validation'):
            path=root/(scenario+'_'+name+'.json')
            assert read(path)['status']=='PASS'
            manifest_key='full_validation_sha256' if name=='validation' else 'presentation_validation_sha256'
            assert sha(path)==manifest['scenarios'][str(percent)][manifest_key]
    return {'status':'PASS','numeric_comparisons':checks,'max_money_error_eur':str(max_money_error),
            'comparison_manifest_sha256':sha(report/'comparison_manifest.json'),
            'script_sha256':sha(Path(__file__)),
            'note':'Decimal cash/dispatch reconciliation from all three executed QH files; full and presentation checks bound by hashes; joined time tables compared to independently validated individual reports.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=validate(a.root);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
