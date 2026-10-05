import copy, csv, json, tempfile, unittest
from pathlib import Path
from dataclasses import replace
from ro_milp.config import Config, midnight, nextday, iso, hash_object
from ro_milp.inputs import Dataset, load_eur
from ro_milp.core import order_specs
from ro_milp.audit import audit_window
from ro_milp.rolling import run
from ro_milp.shares import load_share_schedule, DEFAULT_SHARE_FILE
from test_model import fixture, first_solve


def demand_fixture(day='2026-08-01',days=4):
    return Dataset([replace(q,demand_u=175.,demand_d=175.,demand_f=128.,sys_f=112.) for q in fixture(day,days).quarters])


class CapacityShareTests(unittest.TestCase):
    def test_frozen_constant_cancellation_dust_only(self):
        from ro_milp.core import Matrix
        m=Matrix();x=m.var('x',0,1)
        m.row(x+0.06168930776583192,hi=0.06168930776578421)
        self.assertEqual(m.rows[-1][2],0.)
        m.row(x+0.1,hi=0.1-1e-8)
        self.assertLess(m.rows[-1][2],-1e-9)

    def test_default_schedule_exact_research_values_and_observation(self):
        cfg=Config();self.assertEqual(cfg.capacity_share_mode,'monthly')
        source=DEFAULT_SHARE_FILE.parents[1]/'project/romania_monthly_share_calibration_20261004/monthly_recommended_share_caps.csv'
        with source.open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                actual=cfg.monthly_capacity_shares[row['month']]
                for prefix in ('afrr',):
                    self.assertEqual(actual[prefix+'_market_share_cap'],float(row[prefix+'_market_share_cap']))
                    self.assertEqual(actual[prefix+'_status'],row[prefix+'_status'])
        for row in cfg.monthly_capacity_shares.values():
            self.assertEqual(row['fcr_market_share_cap'],100/(450+100))
            self.assertEqual(row['fcr_status'],'user_fixed_competition_450_plus_100_20261005')
            self.assertEqual(row['fcr_reference_month'],'')
        obs=cfg.monthly_capacity_shares['2026-09']
        self.assertEqual(obs['scope'],'LOOKAHEAD_ONLY')
        self.assertEqual(obs['afrr_reference_month'],'2026-08')
        self.assertEqual(obs['afrr_market_share_cap'],24/175)

    def test_demand_not_procured_quantity(self):
        d=demand_fixture();cfg=Config();specs=order_specs(d,d.quarters,cfg)
        for s in specs.values():
            if s['product']=='DA':continue
            self.assertEqual(s['upper'],23 if s['product']=='F' else 24)
        # Retain existing system-award/qualification/physical caps as well.
        small=Dataset([replace(q,sys_f=7.9) for q in d.quarters])
        self.assertEqual(next(s['upper'] for s in order_specs(small,small.quarters,cfg).values() if s['product']=='F'),7)

    def test_fixed_competition_share_scales_demand_and_keeps_data_gate(self):
        for demand, expected in ((128.,23),(150.,27)):
            d=Dataset([replace(q,demand_f=demand) for q in demand_fixture().quarters])
            ss=order_specs(d,d.quarters,Config())
            f=next(s for s in ss.values() if s['product']=='F')
            self.assertAlmostEqual(f['share_limit_mw'],demand*100/550)
            self.assertEqual(f['upper'],expected)
        d=Dataset([replace(q,cap_f=None) for q in demand_fixture('2025-01-01').quarters])
        fs=[s for s in order_specs(d,d.quarters,Config()).values() if s['product']=='F']
        self.assertTrue(all(s['upper']==0 and s['reason']=='DATA_INVALID' for s in fs))

    def test_calendar_month_is_bucharest_not_utc_and_integer_floor(self):
        d=demand_fixture('2025-01-31');d=Dataset([replace(q,demand_u=200.,demand_d=200.) for q in d.quarters])
        specs=order_specs(d,d.quarters,Config())
        jan=specs['u|'+iso(midnight('2025-01-31'))];feb=specs['u|'+iso(midnight('2025-02-01'))]
        self.assertEqual(jan['upper'],52);self.assertEqual(feb['upper'],40)
        self.assertEqual(feb['capacity_share_month'],'2025-02')
        d=demand_fixture('2026-04-01');specs=order_specs(d,d.quarters,Config())
        self.assertEqual(specs['u|'+iso(d.quarters[0].hour)]['upper'],25)
        self.assertTrue(specs['u|'+iso(d.quarters[0].hour)]['capacity_share_status'].startswith('proxy'))

    def test_missing_or_invalid_demand_closes_full_order_only(self):
        for value in (None,0.,-1.,float('nan')):
            d=demand_fixture();rows=list(d.quarters);rows[1]=replace(rows[1],demand_f=value)
            # Explicit source hash permits a deliberately nonfinite corruption fixture.
            d=Dataset(rows,source_hash='corrupt-demand-test');ss=order_specs(d,d.quarters[:4],Config())
            f=ss['F|'+iso(rows[0].hour)]
            self.assertEqual(f['upper'],0);self.assertEqual(f['reason'],'DEMAND_INVALID')
            self.assertEqual(ss['u|'+iso(rows[0].hour)]['upper'],24)

    def test_missing_month_closes_without_forward_filling(self):
        d=demand_fixture();ss=order_specs(d,d.quarters,Config(monthly_capacity_shares={}))
        self.assertTrue(all(s['upper']==0 and s['reason']=='SHARE_MONTH_MISSING' for s in ss.values() if s['product']!='DA'))
        self.assertTrue(any(s['upper']==100 for s in ss.values() if s['product']=='DA'))

    def test_loader_rejects_duplicate_nonfinite_and_invalid_schedule(self):
        original=DEFAULT_SHARE_FILE.read_text(encoding='utf-8-sig').splitlines()
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'shares.csv';f.write_text('\n'.join(original+[original[1]]),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Duplicate share month'):load_share_schedule(f)
        for value in (-.1,1.1,float('nan'),float('inf'),True):
            schedule=load_share_schedule();schedule['2026-08']['fcr_market_share_cap']=value
            with self.assertRaisesRegex(ValueError,'outside'):Config(monthly_capacity_shares=schedule)
        schedule=load_share_schedule();schedule['2026-8']=schedule.pop('2026-08')
        with self.assertRaisesRegex(ValueError,'Invalid monthly'):Config(monthly_capacity_shares=schedule)

    def test_solve_audit_bounds_cash_and_no_variable_growth(self):
        d=Dataset([replace(q,cap_f=1000.,cap_u=500.,cap_d=500.) for q in demand_fixture().quarters])
        cfg=Config(time_limit=20,mip_rel_gap=1e-8)
        r,a=first_solve(d,cfg);old,_=first_solve(d,replace(cfg,capacity_share_mode='none'))
        self.assertTrue(all(q['fcr_mw']<=23 and q['afrr_up_mw']<=24 and q['afrr_down_mw']<=24 for q in a['qh']))
        self.assertEqual(max(q['fcr_mw'] for q in a['qh']),23)
        self.assertLessEqual(r['metrics']['variables'],old['metrics']['variables'])
        self.assertLessEqual(r['metrics']['binary'],old['metrics']['binary'])
        for q in a['qh']:
            self.assertAlmostEqual(q['fcr_capacity_eur'],q['fcr_mw']*.25*1000)
            self.assertAlmostEqual(q['afrr_up_capacity_eur'],q['afrr_up_mw']*.25*500)
            self.assertAlmostEqual(q['afrr_down_capacity_eur'],q['afrr_down_mw']*.25*500)
        ref,_=first_solve(d,replace(cfg,formulation='reference'))
        self.assertAlmostEqual(r['metrics']['incumbent_eur'],ref['metrics']['incumbent_eur'],places=3)
        bad=copy.deepcopy(r);key=next(k for k,o in bad['orders'].items() if o['product']=='F' and o['commitment']=='NEW')
        wrong_meta=copy.deepcopy(r);wrong_meta['orders'][key]['capacity_share_status']='misstated_provenance'
        start=d.quarters[0].start
        with self.assertRaisesRegex(ValueError,'Audit share provenance'):audit_window(d,cfg,wrong_meta,start,start,nextday(start,3),cfg.e_min,{}, {2026:600},{})
        bad['orders'][key]['amount_mw']=24
        s=d.quarters[0].start
        with self.assertRaisesRegex(ValueError,'Audit bound capacity'):audit_window(d,cfg,bad,s,s,nextday(s,3),cfg.e_min,{}, {2026:600},{})

    def test_month_boundary_resume_and_share_edit_rejected(self):
        d=demand_fixture('2026-07-31');cfg=Config(power_mw=20,market='DA+aFRR',time_limit=10);start=d.quarters[0].start
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run'
            self.assertEqual(run(d,cfg,start,nextday(start,2),out,max_windows=1)['status'],'PARTIAL')
            changed=copy.deepcopy(cfg.monthly_capacity_shares);changed['2026-08']['afrr_market_share_cap']=.01
            with self.assertRaisesRegex(ValueError,'identity mismatch'):run(d,replace(cfg,monthly_capacity_shares=changed),start,nextday(start,2),out,resume=True)
            self.assertEqual(run(d,cfg,start,nextday(start,2),out,resume=True)['status'],'COMPLETE')

    def test_observation_month_cannot_be_formal_execution(self):
        d=demand_fixture('2026-09-01');start=d.quarters[0].start
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'LOOKAHEAD_ONLY'):run(d,Config(),start,nextday(start,2),Path(tmp)/'run')


if __name__=='__main__':unittest.main()
