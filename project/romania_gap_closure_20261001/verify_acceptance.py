"""Post-review preservation, scope, state and links. No market computation."""
from pathlib import Path
from datetime import datetime,timezone
import csv,hashlib,json,re,zipfile
R=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent;O=R/'countries/RO/gap_closure_20261001';RAW=R/'data/raw/RO/gap_closure/20261001'
# Create the report before checking the acceptance document's link to it.
# This derived verification file is finalized with the actual verdict below.
(O/'acceptance_checks.json').write_text(json.dumps(dict(status='RUNNING',scope='post-review preservation checks')),encoding='utf8')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def get(p):return json.loads(p.read_text(encoding='utf8'))
checks=[];counts={}
def check(n,ok,detail=None):checks.append(dict(check=n,passed=bool(ok),detail=detail))
m=get(W/'review_round2_manifest.json')
bad=[x['file'] for x in m['files'] if not (R/x['file']).exists() or (R/x['file']).stat().st_size!=x['bytes'] or sha(R/x['file'])!=x['sha256']]
check('All 4766 independently reviewed frozen files unchanged',len(m['files'])==4766 and not bad,bad)
counts['reviewed_frozen_files']=len(m['files'])
prior=get(W/'prior_delivery_integrity_at_start.json')
bad=[x['file'] for x in prior['files'] if (R/x['file']).stat().st_size!=x['bytes'] or sha(R/x['file'])!=x['sha256']]
check('Prior 1662 delivery files immutable except expressly authorized state',set(bad).issubset({'project/country_status.yaml'}),bad)
check('Prior final manifest unchanged',sha(R/prior['prior_final_manifest'])==prior['manifest_sha256'],prior['prior_final_manifest'])
base=get(R/'project/romania_data_samples_20260930/baseline_integrity.json')
check('All four fixed baselines unchanged',len(base['files'])==4 and all(sha(R/x['file'])==x['expected_sha256'] for x in base['files']),[x['file'] for x in base['files']])
old=get(R/'project/romania_data_samples_20260930/final_delivery_manifest.json')
oldfiles=[x for x in old['files'] if x['file']!='project/country_status.yaml']
check('Previous sample delivery files unchanged',all(sha(R/x['file'])==x['sha256'] for x in oldfiles),len(oldfiles))
oldraw=[x for x in get(R/'countries/RO/data_samples_20260930/raw_manifest.json') if x.get('raw_file')]
check('All previous sample original bodies unchanged',all(sha(R/x['raw_file'])==x['sha256'] for x in oldraw),len(oldraw))
protection=get(W/'review_round1_preservation.json')
for filename,key in [('review_round1_manifest.json','manifest_sha256'),('round1_submission_snapshot.zip','snapshot_sha256')]:
    check('First-round preservation '+filename,sha(W/filename)==protection[key])
check('First-round FAIL opinion preserved',sha(O/'review_round1.md')==protection['review_opinion_sha256'])
snapshot_meta=[]
for roundno,expected in [(1,104),(2,110)]:
    manifest=get(W/f'review_round{roundno}_manifest.json');index={x['file']:x for x in manifest['files']}
    zpath=W/f'round{roundno}_submission_snapshot.zip';mismatch=[];size=0
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            h=hashlib.sha256()
            with z.open(info) as f:
                for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
            if info.filename not in index or info.file_size!=index[info.filename]['bytes'] or h.hexdigest()!=index[info.filename]['sha256']:mismatch.append(info.filename)
            size+=info.file_size
        entries=len(z.infolist())
        if roundno==2:
            check('Second ZIP contains entire large IDCT CSV',z.getinfo('countries/RO/gap_closure_20261001/idct_native_publication_occurrences.csv').file_size==(O/'idct_native_publication_occurrences.csv').stat().st_size)
    check(f'Round{roundno} snapshot complete and matches frozen version',entries==expected and not mismatch,dict(entries=entries,uncompressed_bytes=size,mismatches=mismatch))
    snapshot_meta.append(dict(round=roundno,file=zpath.relative_to(R).as_posix(),bytes=zpath.stat().st_size,sha256=sha(zpath),entries=entries))
before=(W/'state_before_supplement_acceptance.yaml').read_bytes();after=(R/'project/country_status.yaml').read_bytes()
check('State before acceptance matches reviewed state',hashlib.sha256(before).hexdigest()==prior['state_at_start_sha256'])
def state_parts(b):
    start=re.search(rb'(?m)^  RO:\r?\n',b).start();end=re.search(rb'(?m)^# ',b[start:]).start()+start
    return b[:start],b[start:end],b[end:]
bp,br,bt=state_parts(before);ap,ar,at=state_parts(after)
check('Non-RO state bytes unchanged',bp==ap and bt==at)
def flat_ro_fields(b):
    # Only existing four-space scalar fields are inspected; unchanged bytes below
    # additionally prove that nested scopes and blocker lists were not altered.
    return {k:v.strip('"') for k,v in re.findall(r'^    ([a-z_]+): (.*)$',b.decode('utf8'),re.M)}
ro=flat_ro_fields(ar);rb=flat_ro_fields(br)
changed={k for k in set(ro)|set(rb) if ro.get(k)!=rb.get(k)}
allowed={'last_updated','next_action','third_step_supplement_record_status','third_step_supplement_record_approved','third_step_supplement_document','third_step_supplement_review','third_step_supplement_reviewed_by','third_step_supplement_acceptance','third_step_supplement_acceptance_date','third_step_supplement_source_access_date','third_step_supplement_full_exit_conditions_met','third_step_supplement_validation'}
check('RO semantic changes limited to supplemental acceptance fields',changed==allowed,sorted(changed))
restored=ar.decode('utf8')
restored=re.sub(r'^    third_step_supplement_[a-z_]+: .*\n','',restored,flags=re.M)
for field in ['last_updated','next_action']:
    original=re.search(r'^    '+field+r': .*$',br.decode('utf8'),re.M).group(0)
    restored=re.sub(r'^    '+field+r': .*$',lambda _:original,restored,flags=re.M)
check('All remaining RO bytes unchanged after reversing authorized additions',restored.encode('utf8')==br)
check('RO remains researching',ro['status']=='researching')
check('Only restricted supplemental record accepted',ro['third_step_supplement_record_status']=='PASS_WITH_RESTRICTIONS' and ro['third_step_supplement_record_approved']=='true')
gates=['official_rules_full_exit_conditions_met','historical_rule_coverage_approved','data_sample_full_exit_conditions_met','third_step_full_exit_conditions_met','third_step_supplement_full_exit_conditions_met','full_period_data_acquired','asof_input_approved','modeling_approved','mathematical_design_approved','implementation_approved','historical_backtest_approved']
check('All eleven overall/data/asof/model/backtest gates remain false',all(ro[k]=='false' for k in gates),{k:ro[k] for k in gates})
check('Old U and DS question counts preserved',ro['open_research_questions']=='12' and ro['open_data_questions']=='12')
check('Actual local acceptance date recorded separately from source access',ro['last_updated']==ro['third_step_supplement_acceptance_date']=='2026-10-02' and ro['third_step_supplement_source_access_date']=='2026-10-01')
v=get(O/'validation_summary.json')
check('32 technical checks saved PASS',v['passed']==32 and v['failed']==0 and all(x['result']=='PASS' for x in v['checks']))
full=get(W/'idct_source_stream_verification.json')
check('Full raw-to-output technical verification still hash anchored',full['passed'] and full['verified_files']==1216 and full['verified_occurrences']==3741324 and full['csv_sha256']==sha(O/'idct_native_publication_occurrences.csv') and full['audit_sha256']==sha(O/'intraday_file_round_audit.csv'))
inv=get(W/'review_invocation.json')
check('Actual high reviewer and two verdicts retained',inv['actual_existing_reviewer_model']=='gpt-6-astra' and inv['actual_existing_reasoning_effort']=='high' and [x['result'] for x in inv['rounds']]==['FAIL','PASS_WITH_RESTRICTIONS'] and inv['rounds'][0]['P1']==1 and all(inv['rounds'][1][x]==0 for x in ['P0','P1','P2']))
check('Reviewer readonly and depth one recorded',inv['read_only'] and inv['max_depth']==1 and not inv['subdelegation'])
check('Round2 returned opinion identical in final copy',sha(O/'review_round2.md')==sha(O/'review_final.md'))
flags=get(O/'research_use_flags.json')
check('All supplemental overall gates stay false and eight groups PARTIAL',all(x is False for k,x in flags.items() if k not in ['closed_subtasks','eight_group_status']) and len(flags['eight_group_status'])==8 and all(x=='PARTIAL' for x in flags['eight_group_status'].values()))
missing=[];targets=0
for root in [O,W]:
    for p in root.rglob('*.md'):
        if 'review_archive' in p.parts:continue
        text=p.read_text(encoding='utf-8-sig')
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)',text):
            link=link.strip('<>')
            if re.match(r'^(https?://|mailto:|#)',link):continue
            link=link.split('#')[0];link=re.sub(r':\d+$','',link)
            target=Path(link) if re.match(r'^[A-Za-z]:[/\\]',link) else p.parent/link
            targets+=1
            if not target.exists():missing.append(dict(document=p.relative_to(R).as_posix(),target=link))
check('All local Markdown file links resolve',not missing,dict(targets=targets,missing=missing))
for name in ['acceptance.md','review_final.md','closure_ledger.md']:
    t=(O/name).read_text(encoding='utf8')
    check('Overall exit remains explicit in '+name,('false' in t or '未开启' in t) and ('第三步' in t or '整体' in t))
counts.update(prior_files=len(prior['files']),baseline_files=4,prior_sample_files=len(oldfiles),prior_sample_raw_bodies=len(oldraw),local_markdown_targets=targets,whole_third_step_exit=False)
obj=dict(checked_utc=datetime.now(timezone.utc).isoformat(),acceptance_local_date='2026-10-02',timezone='Asia/Shanghai',status='PASS' if all(x['passed'] for x in checks) else 'FAIL',passed=sum(x['passed'] for x in checks),failed=sum(not x['passed'] for x in checks),checks=checks,counts=counts,review_snapshots=snapshot_meta,scope='post-review integrity and restricted acceptance only, not full third-step exit',state_before_sha256=hashlib.sha256(before).hexdigest(),state_after_sha256=hashlib.sha256(after).hexdigest())
(O/'acceptance_checks.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:obj[k] for k in ['status','passed','failed','counts']},ensure_ascii=False),flush=True)
if obj['failed']:raise SystemExit('Acceptance validation failed; no final manifest')
entries=[]
for root in [O,W,RAW]:
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.name!='final_delivery_manifest.json':
            entries.append(dict(file=p.relative_to(R).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
p=R/'project/country_status.yaml';entries.append(dict(file=p.relative_to(R).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
final=dict(generated_utc=datetime.now(timezone.utc).isoformat(),record_status='PASS_WITH_RESTRICTIONS',P0=0,P1=0,P2=0,scope='supplemental eight-gap research record and authorized RO state entry; prior delivery and baselines preserved',whole_third_step_exit=False,asof_input_approved=False,modeling_approved=False,mathematical_design_approved=False,implementation_approved=False,historical_backtest_approved=False,files=entries,review_snapshots=snapshot_meta,referenced_baseline_integrity=base,prior_final_manifest=prior['prior_final_manifest'],prior_final_manifest_sha256=prior['manifest_sha256'],acceptance_checks='countries/RO/gap_closure_20261001/acceptance_checks.json')
target=W/'final_delivery_manifest.json'
if target.exists():raise SystemExit('Final manifest already exists; do not overwrite')
target.write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(dict(final_manifest=target.relative_to(R).as_posix(),files=len(entries),sha256=sha(target))),flush=True)

