"""Dependency-free unittest entry point; optionally save reviewable test evidence."""
import sys,unittest,argparse,json,io,time
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'src'))
from ro_milp.rolling import code_hash

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path);a=p.parse_args()
    stream=io.StringIO();start=time.perf_counter()
    suite=unittest.defaultTestLoader.discover(str(root/'tests'))
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    print(stream.getvalue())
    if a.report:
        a.report.parent.mkdir(parents=True,exist_ok=True)
        evidence={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'seconds':time.perf_counter()-start,'code_sha256':code_hash(),'log':stream.getvalue()}
        a.report.write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
