from pathlib import Path
import subprocess, shutil, hashlib, json
ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent
RAW=ROOT/'data/raw/RO/gap_closure/20261001'
out=WORK/'derived_official_documents';out.mkdir(exist_ok=True)
records=[]
for id in ['STS_DOC_1','STS_DOC_2']:
    source=RAW/(id+'__a1')/'original.html'
    names=subprocess.check_output(['tar','-tf',str(source)],encoding='utf-8').splitlines()
    dest=(out/id).resolve();dest.mkdir(exist_ok=True)
    for name in names:
        target=(dest/name).resolve()
        if not target.is_relative_to(dest):raise ValueError('unsafe archive member')
    subprocess.run(['tar','-xf',str(source),'-C',str(dest)],check=True)
    for p in dest.rglob('*'):
        if p.is_file():records.append({'source_id':id,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'file':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'derivation':'unpacked original RAR5; archive source misclassified by generic downloader; raw untouched'})
for id,attempt in [('STS_DOC_3',2),('STS_DOC_4',1)]:
    source=RAW/(id+f'__a{attempt}')/'original.xls'
    target=out/(id+'.doc');shutil.copyfile(source,target)
    records.append({'source_id':id,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'file':target.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'derivation':'byte-identical DOC staging copy; raw OLE Word misclassified as XLS; no source modification'})
(out/'derivation_manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'archive_documents':len(records),'staged_contracts':2}))
