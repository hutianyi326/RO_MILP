import unittest, tempfile, json, copy,hashlib
from unittest.mock import patch
from pathlib import Path
from datetime import timedelta
from dataclasses import replace
from ro_milp.config import *
from ro_milp.inputs import Dataset,Quarter,load_eur,valid_fx
from ro_milp.core import solve_window,Matrix,as_expr,order_specs
from ro_milp.audit import audit_window
from ro_milp.rolling import run,posthoc,read_json,verify_chain

def fixture(day='2025-06-07',days=4,minutes=60,negative=False):
    s=midnight(day);e=nextday(s,days);rows=[];t=s
    while t<e:
        h=t.astimezone(RO).hour;dt=t if minutes==15 else t.replace(minute=0)
        price=(-70 if h<7 else 110 if 17<=h<22 else 25)+((t.minute/15)*4 if minutes==15 else 0)
        if negative:price=-100
        rows.append(Quarter(t,iso(dt),minutes,float(price),8.,7.,4.,90.,-15.,100.,100.,100.,2.5,1.25))
        t+=timedelta(minutes=15)
    return Dataset(rows)

def first_solve(data,cfg,days=3,budget=600):
    s=data.quarters[0].start;end=nextday(s,days);budgets={q.day.year:budget for q in data.quarters}
    result=solve_window(data,cfg,s,s,end,cfg.e_min,{},budgets,{})
    replay=audit_window(data,cfg,result,s,s,end,cfg.e_min,{},budgets,{})
    return result,replay

class ModelTests(unittest.TestCase):
    def test_full_three_phase_counts_and_compact_reference_equivalence(self):
        for minutes,upper in ((60,528),(15,1032)):
            d=fixture(minutes=minutes);c=Config(time_limit=15,mip_rel_gap=1e-8)
            r,a=first_solve(d,c);rr,aa=first_solve(d,replace(c,formulation='reference'))
            self.assertEqual(r['metrics']['status'],0);self.assertEqual(rr['metrics']['status'],0)
            self.assertAlmostEqual(r['metrics']['incumbent_eur'],rr['metrics']['incumbent_eur'],places=3)
            self.assertEqual(r['metrics']['variables'],upper)
            self.assertLess(r['metrics']['variables'],rr['metrics']['variables'])
            self.assertTrue(all(row['total_eur']==0 for row in a['qh'][:96]))
            self.assertTrue(all(row['ein_mwh']==c.e_min for row in a['qh'][:96]))

    def test_market_switches_and_two_four_hours(self):
        for market in ('DA','DA+aFRR','DA+FCR','DA+aFRR+FCR'):
            for hours in (2,4):
                cfg=Config(power_mw=20,hours=hours,market=market,time_limit=10);r,a=first_solve(fixture(),cfg)
                self.assertEqual(r['metrics']['audit'],'PASS')
                if 'FCR' not in market:self.assertTrue(all(q['fcr_mw']==0 for q in a['qh']))
                if 'aFRR' not in market:self.assertTrue(all(q['afrr_up_mw']==q['afrr_down_mw']==0 for q in a['qh']))

    def test_strict_invalid_whole_hour_other_markets_continue(self):
        d=fixture();rows=list(d.quarters);j=100
        rows[j]=replace(rows[j],energy_u=25.,energy_d=.00000001)
        data=Dataset(rows);r,a=first_solve(data,Config())
        bad=[q for q in a['qh'] if parse(q['delivery_start_utc']).replace(minute=0)==rows[j].hour]
        self.assertEqual(len(bad),4);self.assertTrue(all(q['afrr_up_mw']==q['afrr_down_mw']==0 for q in bad))
        self.assertTrue(all(q['fcr_hour_data_valid'] and q['da_data_valid'] for q in bad))
        self.assertEqual(sum(p['start'] in {q['delivery_start_utc'] for q in bad} for p in a['phases']),4)

    def test_missing_prices_and_zero_duration(self):
        d=fixture();rows=list(d.quarters)
        rows[100]=replace(rows[100],act_u=None)
        for i in range(104,108):rows[i]=replace(rows[i],energy_u=0.,energy_d=0.,cap_f=None)
        data=Dataset(rows);r,a=first_solve(data,Config())
        for i in (100,101,102,103):self.assertEqual(a['qh'][i]['afrr_up_mw'],0)
        self.assertEqual(sum(p['start']==iso(rows[104].start) for p in a['phases']),1)
        self.assertEqual(a['qh'][104]['fcr_mw'],0)

    def test_dst_sizes_and_counts(self):
        for day,count in [('2025-03-29',188),('2025-10-25',196)]:
            d=fixture(day=day);cfg=Config(market='DA',power_mw=20);r,a=first_solve(d,cfg)
            self.assertEqual(len(a['qh']),count)
            self.assertEqual(len(set(q['delivery_start_utc'] for q in a['qh'])),count)

    def test_formal_terminal_fcr_zero_and_signed_activation(self):
        d=fixture();cfg=Config();r,a=first_solve(d,cfg,days=2)
        self.assertAlmostEqual(a['end_soc'],cfg.e_min,places=6)
        self.assertTrue(all(row['fcr_mw']==0 for row in a['qh'][-4:]))
        self.assertGreater(sum(row['afrr_down_activation_eur'] for row in a['qh']),0)

    def test_zero_p_and_daily_missing(self):
        d=fixture();cfg=Config(p_up=0,p_down=0,p_fcr=0);r,a=first_solve(d,cfg)
        self.assertTrue(all(row['afrr_up_mw']==row['afrr_down_mw']==row['fcr_mw']==0 for row in a['qh']))
        r,a=first_solve(d,Config(daily_p={'2025-06-07':dict(u=1,d=1,F=1)}))
        self.assertTrue(all(row['afrr_up_mw']==row['afrr_down_mw']==row['fcr_mw']==0 for row in a['qh'][96:]))

    def test_fcr_fractional_unit_floor(self):
        self.assertEqual(allocate_fcr(2,(1.6,1.6)),[1,1])
        with self.assertRaises(ValueError):allocate_fcr(3,(1.6,1.6))
        d=fixture();r,a=first_solve(d,Config(power_mw=3.2,fcr_unit_caps=(1.6,1.6)))
        self.assertTrue(all(q['fcr_mw']<=2 for q in a['qh']))

    def test_negative_price_no_simultaneous_charge_discharge(self):
        # Original one-period counterexample: fixed endpoint cannot earn money by dissipating energy.
        for form in ('compact','reference'):
            m=Matrix();Y=m.var('net',-100,100);D=m.var('D',0,100);z=m.var('z',0,1,'binary')
            if form=='compact':
                C=D-Y;m.row(D-Y,lo=0);m.row(D-100*z,hi=0);m.row(D-Y+100*z,hi=100)
            else:
                C=m.var('C',0,100);m.row(D-C-Y,0,0);m.row(D-100*z,hi=0);m.row(C+100*z,hi=100)
            m.row(.92*C-D/.92,0,0)
            x,stats=m.solve(-25*Y,Config(formulation=form));self.assertAlmostEqual(Y.value(x),0,places=6)
            self.assertAlmostEqual(stats['incumbent_eur'],0,places=5)

    def test_frozen_conflict_missing_and_audit_tamper(self):
        d=fixture();cfg=Config();s=d.quarters[0].start;r,a=first_solve(d,cfg)
        ledger={k:v for k,v in r['orders'].items() if parse(v['start'])>=nextday(s)}
        with self.assertRaisesRegex(ValueError,'Missing frozen'):solve_window(d,cfg,nextday(s),s,nextday(s,3),a['qh'][95]['eout_mwh'],{}, {2025:600},{})
        key=next(k for k,v in ledger.items() if v['product']=='u');ledger[key]=dict(ledger[key],amount_mw=101)
        with self.assertRaisesRegex(ValueError,'Frozen commitment'):solve_window(d,cfg,nextday(s),s,nextday(s,3),cfg.e_min,{}, {2025:600},ledger)
        bad=copy.deepcopy(r);bad['path'][0]['eout']+=.01
        with self.assertRaisesRegex(ValueError,'Audit'):audit_window(d,cfg,bad,s,s,nextday(s,3),cfg.e_min,{}, {2025:600},{})

    def test_year_boundary_budget_and_resume_atomic_posthoc(self):
        d=fixture(day='2025-12-30',days=5);cfg=Config(power_mw=20,market='DA+aFRR+FCR',time_limit=10)
        s=d.quarters[0].start;e=nextday(s,3)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run';first=run(d,cfg,s,e,out,max_windows=1)
            self.assertEqual(first['status'],'PARTIAL');before=(out/'windows/0000.json').read_bytes()
            final=run(d,cfg,s,e,out,resume=True);self.assertEqual(final['status'],'COMPLETE',final)
            self.assertEqual(final['executed_qh'],288);self.assertEqual(before,(out/'windows/0000.json').read_bytes())
            self.assertAlmostEqual(final['end_soc_mwh'],cfg.e_min,places=6)
            direct=run(d,cfg,s,e,Path(tmp)/'direct');self.assertAlmostEqual(direct['total_eur'],final['total_eur'],places=4)
            pc=posthoc(out,Path(tmp)/'post',.8,.6,0.)
            for key in ('da_eur','afrr_up_activation_eur','afrr_down_activation_eur'):self.assertAlmostEqual(pc['cash_eur'][key],final['cash_eur'][key],places=6)
            self.assertAlmostEqual(pc['cash_eur']['afrr_up_capacity_eur'],final['cash_eur']['afrr_up_capacity_eur']*.8,places=6)
            with self.assertRaisesRegex(ValueError,'identity mismatch'):run(d,replace(cfg,p_up=.8),s,e,out,resume=True)
            tx=read_json(out/'windows/0000.json');tx['next_state']['soc_mwh']+=1;(out/'windows/0000.json').write_text(canonical(tx),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Corrupt'):run(d,cfg,s,e,out,resume=True)

    def test_all_constant_zero_qualification_and_zero_budget(self):
        d=fixture();cfg=Config(power_mw=10,market='DA');s=d.quarters[0].start
        r=solve_window(d,cfg,s,s,nextday(s,2),cfg.e_min,{}, {2025:0.},{})
        a=audit_window(d,cfg,r,s,s,nextday(s,2),cfg.e_min,{}, {2025:0.},{})
        self.assertAlmostEqual(sum(row['efc'] for row in a['qh']),0,places=7)

    def test_atomic_publish_failure_does_not_advance(self):
        from ro_milp.rolling import atomic_json
        d=fixture();cfg=Config(power_mw=10,market='DA');s=d.quarters[0].start
        def fail_window(path,payload,immutable=False):
            if Path(path).parent.name=='windows':raise OSError('Injected publication failure')
            return atomic_json(path,payload,immutable)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run'
            with patch('ro_milp.rolling.atomic_json',side_effect=fail_window):summary=run(d,cfg,s,nextday(s,2),out)
            self.assertEqual(summary['status'],'BLOCKED');self.assertEqual(summary['windows'],0);self.assertEqual(summary['executed_qh'],0)
            self.assertFalse(list((out/'windows').glob('*.json')))
            restored=run(d,cfg,s,nextday(s,2),out,resume=True);self.assertEqual(restored['status'],'COMPLETE')

    def test_input_hash_required_unique_and_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);release=root/'data/processed/RO/release';release.mkdir(parents=True)
            names=['prices_eur_qh_20250101_20260831.csv','prices_eur_observation_20260901.csv']
            for name in names:(release/name).write_text('stub\n',encoding='utf-8')
            entries=[dict(path=str((release/name).relative_to(root)),sha256=hashlib.sha256((release/name).read_bytes()).hexdigest()) for name in names]
            manifest=release/'manifest.json'
            manifest.write_text(json.dumps({'files':entries[:1]}),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Required consumed CSV'):load_eur(release)
            manifest.write_text(json.dumps({'files':entries+[entries[0]]}),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Duplicate manifest'):load_eur(release)
            manifest.write_text(json.dumps({'files':entries}),encoding='utf-8');(release/names[0]).write_text('changed\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Input hash mismatch'):load_eur(release)
        d=fixture();rows=list(d.quarters);rows[0]=replace(rows[0],cap_f=9)
        self.assertNotEqual(d.source_hash,Dataset(rows).source_hash)

    def test_fx_dates_must_be_valid_strictly_prior_iso(self):
        for value in ('','garbage','2025-02-30','2025-01-02','2025-01-03','20250101'):
            self.assertFalse(valid_fx(value,'2025-01-02',5.,'BNR'))
        self.assertTrue(valid_fx('2024-12-31','2025-01-02',5.,'BNR'))
        self.assertFalse(valid_fx('2024-12-31','2025-01-02',None,'BNR'))
        self.assertFalse(valid_fx('2024-12-31','2025-01-02',5.,''))

    def test_system_limits_and_fcr_freeze_vector(self):
        d=fixture();rows=[replace(q,sys_u=2.9,energy_u=.1,sys_d=3.7,energy_d=.1,sys_f=4.8) for q in d.quarters]
        data=Dataset(rows);cfg=Config(power_mw=10,fcr_unit_caps=(5.,5.));r,a=first_solve(data,cfg)
        self.assertTrue(all(row['afrr_up_mw']<=2 and row['afrr_down_mw']<=3 and row['fcr_mw']<=4 for row in a['qh']))
        s=d.quarters[0].start;ledger={k:v for k,v in r['orders'].items() if parse(v['start'])>=nextday(s)}
        key=next(k for k,v in ledger.items() if v['product']=='F')
        ledger[key]=dict(ledger[key],units_mw=[6,0],amount_mw=6)
        with self.assertRaisesRegex(ValueError,'Frozen'):solve_window(data,cfg,nextday(s),s,nextday(s,3),cfg.e_min,{}, {2025:600},ledger)

if __name__=='__main__':unittest.main()
