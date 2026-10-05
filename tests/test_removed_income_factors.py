"""Removed parameters must fail explicitly, never be silently ignored."""
import contextlib, io, tempfile, unittest
from pathlib import Path
from ro_milp.config import Config, midnight, nextday
from ro_milp.cli import main
from ro_milp import rolling
from test_capacity_shares import demand_fixture


class RemovedIncomeFactorTests(unittest.TestCase):
    def test_old_config_and_function_are_unavailable(self):
        for field,value in [('p_up',1.),('p_down',.8),('p_fcr',.6),('daily_p',{})]:
            with self.subTest(field=field):
                with self.assertRaises(TypeError):Config(**{field:value})
                self.assertNotIn(field,Config().as_dict())
        self.assertFalse(hasattr(rolling,'posthoc'))
        self.assertFalse(hasattr(Config(),'p'))

    def test_cli_rejects_all_removed_entries_before_loading_data(self):
        from unittest.mock import patch
        calls=[['posthoc','--source','unused','--output','unused']]
        calls += [['run','--output','unused',flag,'0.8'] for flag in ('--p-up','--p-down','--p-fcr')]
        calls += [['run','--output','unused','--daily-p-file','unused.json']]
        with patch('ro_milp.cli.load_eur') as load:
            for argv in calls:
                with self.subTest(argv=argv),contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as exc:main(argv)
                    self.assertEqual(exc.exception.code,2)
            load.assert_not_called()

    def test_exports_have_no_income_factor_and_legacy_identity_is_rejected(self):
        d=demand_fixture(days=3);start=d.quarters[0].start;end=nextday(start)
        cfg=Config(power_mw=20,time_limit=10)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run';summary=rolling.run(d,cfg,start,end,out)
            self.assertEqual(summary['status'],'COMPLETE')
            manifest=rolling.read_json(out/'manifest.json')
            self.assertIn('M33',manifest['specification'])
            self.assertIn('retired M26',manifest['specification'])
            self.assertTrue({'p_up','p_down','p_fcr','daily_p'}.isdisjoint(manifest['identity']['config']))
            tx=rolling.read_json(out/'windows/0000.json')
            for row in list(tx['new_orders'].values())+list(tx['initial_orders'].values()):
                self.assertNotIn('p',row)
            # Even an old schema with coefficient 1 is a different run identity.
            manifest['identity']['config']['p_up']=1.
            rolling.atomic_json(out/'manifest.json',manifest)
            with self.assertRaisesRegex(ValueError,'identity mismatch'):
                rolling.run(d,cfg,start,end,out,resume=True)


if __name__=='__main__':unittest.main()
