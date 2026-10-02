"""Final preservation, documentation and gate checks; no market calculations."""
from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, re

R = Path(__file__).resolve().parents[2]
W = Path(__file__).resolve().parent
O = R/'countries/RO/full_period_20261001'
OUT = O/'acceptance_checks.json'
checks = []
counts = {}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def get(p): return json.loads(p.read_text(encoding='utf-8'))
def check(n, ok, detail=''):
    checks.append({'check':n, 'pass':bool(ok), 'detail':detail})

# Only review-result labels and RO record state may change after formal review.
allowed = {'countries/RO/full_period_20261001/analysis_report.md',
           'project/romania_full_period_20261001/review_repairs.md',
           'project/romania_full_period_20261001/review_invocation.json',
           'project/country_status.yaml'}
m = get(W/'review_round2_manifest.json')
changed = [x['file'] for x in m['files'] if sha(R/x['file']) != x['sha256']]
counts['round2_reviewed_files'] = len(m['files'])
counts['unchanged_reviewed_files'] = len(m['files'])-len(changed)
check('post-review changes limited to verdict/acceptance labels and RO record',
      set(changed).issubset(allowed), changed)
raw = get(O/'raw_manifest.json')
bodies = [x for x in raw if x.get('raw_file')]
bad = [x['id'] for x in bodies if sha(R/x['raw_file']) != x['sha256']]
counts['this_batch_raw_bodies'] = len(bodies)
check('all 728 current/reused official raw bodies unchanged', len(bodies)==728 and not bad, bad)
old = get(R/'countries/RO/data_samples_20260930/raw_manifest.json')
old_bodies = [x for x in old if x.get('raw_file')]
counts['prior_sample_raw_bodies'] = len(old_bodies)
check('prior sample raw bodies unchanged', all(sha(R/x['raw_file'])==x['sha256'] for x in old_bodies))
base = get(R/'project/romania_data_samples_20260930/baseline_integrity.json')
check('all four fixed baselines unchanged', len(base['files'])==4 and
      all(sha(R/x['file'])==x['expected_sha256'] for x in base['files']))
prior = get(R/'project/romania_data_samples_20260930/final_delivery_manifest.json')
items = [x for x in prior['files'] if x['file']!='project/country_status.yaml']
counts['prior_delivery_files'] = len(items)
check('prior audited delivery preserved except authorized country state',
      all(sha(R/x['file'])==x['sha256'] for x in items))
before = get(W/'round1_before_fix/manifest.json')
check('four affected round1 before-images unchanged',
      all(sha(R/x['preserved_file'])==x['sha256'] for x in before['files']))
round1 = get(W/'review_round1_manifest.json')
light=[]
for x in round1['files']:
    p=W/'round1_snapshot'/x['file']
    if p.exists():light.append((p,x['sha256']))
counts['round1_light_snapshots'] = len(light)
check('all archived first-round light files match original manifest',
      len(light)==80 and all(sha(p)==h for p,h in light))

state_path=R/'project/country_status.yaml'
current=state_path.read_bytes()
prior_state=(R/'project/romania_data_samples_20260930/round2_snapshot/project/country_status.yaml').read_bytes()
def outside_ro_bytes(s):
    match=re.search(rb'\r?\n  RO:\r?\n',s)
    if not match:raise ValueError('RO header missing')
    start=match.start()
    end=re.search(rb'\r?\n# ',s[match.end():]).start()+match.end()
    return s[:start]+s[end:]
check('non-RO bytes match prior audited state', outside_ro_bytes(current)==outside_ro_bytes(prior_state))
s=current.decode('utf-8');a=s.index('\n  RO:');b=s.index('\n# ',a);ro=s[a:b]
check('RO stays researching', '    status: researching' in ro)
check('only restricted data record approved', '    third_step_record_approved: true' in ro
      and '    third_step_record_status: "PASS_WITH_RESTRICTIONS"' in ro)
gates=['third_step_full_exit_conditions_met','full_period_data_acquired','asof_input_approved',
       'modeling_approved','mathematical_design_approved','implementation_approved','historical_backtest_approved']
check('all seven full-stage/asof/model/backtest gates remain false',
      all(re.search(r'^    '+k+r': false\s*$',ro,re.M) for k in gates))
check('12 U and 12 DS counts not reduced', '    open_research_questions: 12' in ro
      and '    open_data_questions: 12' in ro)
inv=get(W/'review_invocation.json')
check('actual two-round review counts preserved', len(inv['rounds'])==2
      and inv['rounds'][0]['P2']==2 and inv['rounds'][1]['P2']==0
      and inv['rounds'][1]['P0']==0 and inv['rounds'][1]['P1']==0)
check('runtime/high/depth restrictions recorded without next-stage approval',
      inv['requested_model']=='gpt-6-astra/high' and inv['depth']==1
      and inv['subdelegation']=='prohibited' and not inv['full_step3_exit_conditions_met']
      and not inv['model_or_next_stage_authorized'])
for n in ['verification.json','supplement_verification.json','p2_repair_verification.json']:
    v=get(O/n);check(n+' saved checks PASS',v['status']=='PASS' and not v['failed'])
png=list((O/'figures').glob('*.png'));svg=list((O/'figures').glob('*.svg'))
check('12 scientific figures available in both PNG and SVG',len(png)==12 and len(svg)==12)
counts['figures_png']=len(png);counts['figures_svg']=len(svg)

missing=[];checked=0
for p in list(O.glob('*.md'))+list(W.glob('*.md')):
    for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
        target=target.strip().strip('<>')
        if re.match(r'^(?:https?://|#|app:|codex:)',target):continue
        target=re.sub(r':\d+$','',target)
        if target.startswith('/C:/'):target=target[1:]
        q=Path(target)
        if not q.is_absolute():q=p.parent/q
        checked+=1
        # This check's own JSON is written after validation finishes.
        if not q.is_file() and q.resolve()!=OUT.resolve():missing.append(str(q))
counts['local_markdown_targets_checked']=checked
check('all final-document local links and figure references resolve',not missing,missing)
for filename in ['review_final.md','acceptance.md','stage_completion_and_gaps.md']:
    t=(O/filename).read_text(encoding='utf-8')
    check(filename+' retains full third-step exit false', 'false' in t and '第三步' in t)
result={'generated_utc':datetime.now(timezone.utc).isoformat(),
        'status':'PASS' if all(x['pass'] for x in checks) else 'FAIL',
        'scope':'post-review integrity, approved scope, state and links; not closure of market dependencies',
        'checks':len(checks),'counts':counts,'failed':[x for x in checks if not x['pass']],
        'details':checks,'allowed_post_review_changes':changed}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['details','allowed_post_review_changes']},ensure_ascii=False))
if result['status']!='PASS':raise SystemExit(1)

# Final hashes, after the check record is saved. Exclude self to avoid circular hash.
files=[p for top in [O,W] for p in top.rglob('*') if p.is_file()]
files+=list((R/'data/raw/RO/full_period/20261001').rglob('*'))+[state_path]
entries=[]
for p in sorted(set(files)):
    if not p.is_file() or p==W/'final_delivery_manifest.json':continue
    entries.append({'file':p.relative_to(R).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
final={'generated_utc':datetime.now(timezone.utc).isoformat(),
       'record_status':'PASS_WITH_RESTRICTIONS','full_step3_exit_conditions_met':False,
       'model_or_next_stage_authorized':False,'files':entries}
with (W/'final_delivery_manifest.json').open('x',encoding='utf-8') as f:
    json.dump(final,f,ensure_ascii=False,indent=2)
print('Final delivery manifest entries:',len(entries))
