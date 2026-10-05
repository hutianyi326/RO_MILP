"""Read-only reconciliation of existing MILP cash with supplied CH index."""
import calendar
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
RUNS = ROOT / 'outputs/capacity_sensitivity_100mw_200mwh_20261002/v3'
SOURCE = Path('C:/Users/Tianyi/Desktop/romanian-storage-index.csv')
PRICE = ROOT / 'data/processed/RO/prices_eur_v1_20261002/prices_eur_qh_20250101_20260831.csv'
def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))
def write(name, rows):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

copy = OUT / 'romanian-storage-index.user-copy.csv'
if copy.exists():
    assert digest(copy) == digest(SOURCE)
else:
    copy.write_bytes(SOURCE.read_bytes())
chrows = read(copy)
ch = {r['Category']: float(r['2h index']) for r in chrows}
assert len(ch) == len(chrows) == 44 and ch['2026-08'] == 178
comparisons = []
hashes = {str(SOURCE): digest(SOURCE), str(PRICE.relative_to(ROOT)): digest(PRICE)}
for scenario in ('p100', 'p80', 'p60'):
    monthly_path = RUNS / f'{scenario}_report/monthly.csv'
    qh_path = RUNS / f'{scenario}_run/executed_qh.csv'
    hashes[str(monthly_path.relative_to(ROOT))] = digest(monthly_path)
    hashes[str(qh_path.relative_to(ROOT))] = digest(qh_path)
    qh = read(qh_path)
    sums = defaultdict(float)
    for r in qh:
        sums[r['local_date'][:7]] += float(r['total_eur'])
    monthly = read(monthly_path)
    assert len(monthly) == 20
    for r in monthly:
        m = r['month']
        assert abs(sums[m] - float(r['total_kEUR']) * 1000) < .01
        days = calendar.monthrange(*map(int, m.split('-')))[1]
        factor = 12 if m < '2026-01' else 365 / days
        annual = float(r['total_kEUR_per_MW']) * factor
        comparisons.append(dict(month=m, scenario=scenario, calendar_days=days,
            ch_annualization_factor=factor, ch_kEUR_per_MW_year=ch[m],
            own_monthly_kEUR_per_MW=float(r['total_kEUR_per_MW']),
            own_annualized_kEUR_per_MW_year=annual, own_to_ch_ratio=annual/ch[m],
            annualized_gap_kEUR_per_MW_year=annual-ch[m],
            note='CH method break January 2026; units aligned, economics not identical'))
write('monthly_comparison.csv', comparisons)

prices = {r['delivery_start_utc']: r for r in read(PRICE) if r['local_date'].startswith('2026-08')}
aug = [r for r in read(RUNS / 'p100_run/executed_qh.csv') if r['local_date'].startswith('2026-08')]
assert len(prices) == len(aug) == 2976
assert len({r['delivery_start_utc'] for r in aug}) == 2976
assert set(prices) == {r['delivery_start_utc'] for r in aug}
components = ['da_eur', 'fcr_capacity_eur', 'afrr_up_capacity_eur', 'afrr_down_capacity_eur', 'afrr_up_activation_eur', 'afrr_down_activation_eur']
cash = {k: sum(float(r[k]) for r in aug) for k in components}
total = sum(float(r['total_eur']) for r in aug)
assert abs(sum(cash.values()) - total) < .0001
write('august_revenue_components.csv', [dict(component=k, EUR_100MW=cash[k],
    monthly_kEUR_per_MW=cash[k]/100000, annualized_kEUR_per_MW_year=cash[k]/100000*365/31,
    share_of_total=cash[k]/total) for k in components])
system = [float(prices[r['delivery_start_utc']]['fcr_accepted_capacity_mw']) for r in aug]
site = [float(r['fcr_mw']) for r in aug]
assert all(s <= q+1e-5 for s,q in zip(site, system))
weighted_price = cash['fcr_capacity_eur'] / (sum(site)*.25)
fcr_price_recomputed = sum(float(r['fcr_mw']) * .25 * float(prices[r['delivery_start_utc']]['fcr_capacity_price_eur_per_mw_h_proxy']) for r in aug)
assert abs(cash['fcr_capacity_eur'] - fcr_price_recomputed) < .0001
days = defaultdict(float)
for r in aug: days[r['local_date']] += float(r['efc'])
summary = dict(date='2026-10-04', local_timezone='Europe/Bucharest', qh_rows=2976,
    ch_august=178, own_august_month_EUR=total, own_august_annualized=total/100000*365/31,
    own_rolling_12m_kEUR_per_MW=sum(float(r['total_kEUR_per_MW']) for r in read(RUNS/'p100_report/monthly.csv') if r['month']>='2025-09'),
    fcr_cash_EUR=cash['fcr_capacity_eur'], fcr_share=cash['fcr_capacity_eur']/total,
    fcr_average_site_MW=sum(site)/len(site), fcr_system_mean_MW=sum(system)/len(system),
    fcr_system_min_MW=min(system), fcr_system_max_MW=max(system),
    fcr_ratio_of_site_to_system_MWh=sum(site)/sum(system),
    fcr_share_of_hours_site_at_least_half_system=sum(s>=q*.5 for s,q in zip(site,system))/len(site),
    fcr_dispatch_weighted_EUR_per_MW_h=weighted_price,
    fcr_price_input_mean_EUR_per_MW_h=sum(float(r['fcr_capacity_price_eur_per_mw_h_proxy']) for r in prices.values())/len(prices),
    non_fcr_accounting_residual_annualized=(total-cash['fcr_capacity_eur'])/100000*365/31,
    note='Accounting residual is not a no-FCR re-optimization and not a causal attribution',
    august_efc=sum(days.values()), august_days_efc_over_1point5=sum(v>1.5+1e-6 for v in days.values()),
    august_max_daily_efc=max(days.values()),
    checks='PASS: 44 CH months unique; 60 scenario-month totals reconcile with QH cash within EUR0.01; August 2976 unique price/QH rows; six cash legs reconcile; FCR capacity cash recomputed from EUR inputs; source copy SHA256 equal',
    input_hashes=hashes)
(OUT/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='input_hashes'}, ensure_ascii=False, indent=2))

# Diagnostic chart: harmonized annualization, not harmonized economic assumptions.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(11,5.4), layout='constrained')
for scenario,color,label in [('p100','#1e3a5f','MILP capacity cash 100%'),('p80','#517d9b','MILP capacity cash 80%'),('p60','#8aa9b8','MILP capacity cash 60%')]:
    rr=[r for r in comparisons if r['scenario']==scenario]
    ax.plot(range(20), [r['own_annualized_kEUR_per_MW_year'] for r in rr],color=color,label=label,lw=2)
ax.plot(range(20),[ch[r['month']] for r in rr],color='#d77628',marker='o',ms=4,label='Clean Horizon 2h',lw=2)
ax.axvline(11.5,color='#888888',linestyle='--',lw=1)
ax.text(11.7,ax.get_ylim()[1]*.96,'CH methodology change',va='top',fontsize=9)
ax.set_xticks(range(0,20,2),[r['month'] for r in rr][::2],rotation=35,ha='right')
ax.set_ylabel('Annualized gross revenue (kEUR/MW/year)')
ax.set_title('Romania BESS revenue comparison | 2025-01 to 2026-08',loc='left',fontweight='bold')
ax.spines[['top','right']].set_visible(False)
ax.grid(axis='y',alpha=.2);ax.legend(loc='upper left',frameon=False,fontsize=9)
fig.supxlabel('Before 2026: monthly x 12; from 2026: monthly / calendar days x 365. Economic assumptions differ.',fontsize=9)
fig.savefig(OUT/'monthly_benchmark.png',dpi=180)
plt.close(fig)
