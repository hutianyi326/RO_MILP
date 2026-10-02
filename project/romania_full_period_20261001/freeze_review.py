from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,shutil,argparse
R=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('round',type=int);args=p.parse_args();dest=W/f'round{args.round}_snapshot';dest.mkdir(exist_ok=False)
files=list((R/'countries/RO/full_period_20261001').rglob('*'))+[x for x in W.rglob('*') if x.is_file() and not any('snapshot' in a or a=='visual_source_checks' for a in x.relative_to(W).parts) and not x.name.startswith(('review_round','final_delivery_manifest'))]+[R/'project/country_status.yaml']
files=[x for x in files if x.is_file()];manifest=[]
for f in sorted(set(files)):
    b=f.read_bytes();rel=f.relative_to(R).as_posix();manifest.append({'file':rel,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)})
    if f.suffix in ['.md','.py','.json','.yaml'] and len(b)<500000:
        d=dest/rel;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,d)
out=W/f'review_round{args.round}_manifest.json'
with out.open('x',encoding='utf-8') as f:json.dump({'scope':'full step3 analysis record and limitations; live data frozen by hashes; selected light files copied','generated_utc':datetime.now(timezone.utc).isoformat(),'files':manifest},f,ensure_ascii=False,indent=2)
print('frozen files',len(manifest),'manifest',out.relative_to(R).as_posix())
