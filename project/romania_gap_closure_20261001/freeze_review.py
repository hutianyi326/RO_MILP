from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,zipfile,sys
R=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent;O=R/'countries/RO/gap_closure_20261001';RAW=R/'data/raw/RO/gap_closure/20261001'
roundno=sys.argv[1] if len(sys.argv)>1 else '1';target=W/f'review_round{roundno}_manifest.json'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
if target.exists():raise SystemExit('frozen review manifest already exists; use new round number')
entries=[]
for root in [O,W,RAW]:
    for p in sorted(root.rglob('*')):
        if p.is_file() and not (p.name.startswith('review_round') and p.name.endswith('_manifest.json')) and p.name!='final_delivery_manifest.json' and 'submission_snapshot.zip' not in p.name and 'review_archive' not in p.parts:
            entries.append(dict(file=p.relative_to(R).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
with (W/f'round{roundno}_submission_snapshot.zip').open('xb') as f:
    with zipfile.ZipFile(f,'w',zipfile.ZIP_DEFLATED,compresslevel=4) as z:
        for root in [O,W]:
            for p in sorted(root.rglob('*')):
                if p.is_file() and p.suffix.lower() in ['.md','.py','.csv','.json'] and not (p.name.startswith('review_round') and p.name.endswith('_manifest.json')) and p.name!='final_delivery_manifest.json' and 'submission_snapshot.zip' not in p.name and 'review_archive' not in p.parts:
                    z.write(p,p.relative_to(R).as_posix())
obj=dict(frozen_utc=datetime.now(timezone.utc).isoformat(),round=roundno,files=entries,scope='eight-gap research supplement only; all stage/model/asof gates false; original prior delivery immutable')
target.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(files=len(entries),manifest=str(target.relative_to(R)),snapshot=f'round{roundno}_submission_snapshot.zip')))
