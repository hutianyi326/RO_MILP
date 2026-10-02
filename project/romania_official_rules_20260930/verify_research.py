"""Validate documentation references, immutable evidence and hypothetical arithmetic."""
from pathlib import Path
import csv,hashlib,json,re
ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent
OUT=ROOT/'countries/RO/rules_20260930'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest().upper()
errors=[]
base=json.loads((WORK/'baseline/manifest.json').read_text(encoding='utf-8-sig'))
baseline=[]
for r in base:
 a=sha(ROOT/'project'/r['File']);b=sha(WORK/'baseline'/r['File'])
 ok=a==b==r['SHA256'];baseline.append({'file':r['File'],'unchanged':ok})
 if not ok:errors.append('Baseline changed '+r['File'])
sources=list(csv.DictReader((OUT/'sources.csv').open(encoding='utf-8-sig')))
rules=list(csv.DictReader((OUT/'rule_register.csv').open(encoding='utf-8-sig')))
sids={s['evidence_id'] for s in sources};rids={r['rule_id'] for r in rules}
if len(sids)!=len(sources) or len(rids)!=len(rules):errors.append('Duplicate IDs')
integrity=[]
for s in sources:
 if s['original_path']:
  p=ROOT/s['original_path']; ok=p.exists() and sha(p).lower()==s['sha256'].lower()
  integrity.append({'id':s['evidence_id'],'sha256_matches':ok})
  if not ok:errors.append('Original hash '+s['evidence_id'])
for r in rules:
 for k in ['publishers','document_titles','publication_or_approval_dates','effective_or_operational_scope','urls','locations','access_date']:
  if not r[k]:errors.append(r['rule_id']+' missing '+k)
 for s in r['evidence_ids'].split('|'):
  if s not in sids:errors.append(r['rule_id']+' unknown source '+s)
 if r['layer']!='F' or r['modeling_approved']!='false':errors.append(r['rule_id']+' unexpected gate/layer')
docs=[ROOT/'countries/RO/research.md',*OUT.glob('*.md')]
ucontent=(OUT/'open_questions.md').read_text(encoding='utf-8')
uids=set(re.findall(r'\bU\d{2}\b',ucontent))
for r in rules:
 for u in r['unresolved_ids'].split('|'):
  if u not in uids:errors.append(r['rule_id']+' unknown U '+u)
for f in docs:
 t=f.read_text(encoding='utf-8')
 for s in set(re.findall(r'\bE\d{2}\b',t)):
  if s not in sids:errors.append(f.name+' unknown source '+s)
 for rid in set(re.findall(r'RO-R\d{3}',t)):
  if rid not in rids:errors.append(f.name+' unknown rule '+rid)
 for target in re.findall(r'\]\(([^)]+)\)',t):
  if target.startswith(('https://','http://','#')):continue
  if not (f.parent/target).exists():errors.append(f.name+' broken local link '+target)
cases=[('none',0,0,1.5,0,0,0,475),('up',.5,0,1.9,800,0,1000,775),('down_positive',0,.4,1.1,0,200,1000,395),('down_negative',0,.4,1.1,0,-200,1000,555),('under_delivery',.5,0,1.8,800,0,1000,675),('both',.5,.4,1.6,800,200,1000,795)]
arithmetic=[]
for name,up,down,meter,pup,pdown,pimb,expected in cases:
 contract=1.5+up-down;imb=meter-contract;act=up*pup-down*pdown
 cash=475+act+imb*pimb;ok=abs(cash-expected)<1e-9
 arithmetic.append({'name':name,'net_contract_MWh':round(contract,6),'imbalance_MWh':round(imb,6),'subtotal_RON':round(cash,6),'pass':ok})
 if not ok:errors.append('Arithmetic '+name)
for name,val,expected in [('capacity_unit_hypothesis',2*40*.25,20),('monthly_fee_hypothesis',(100-90)*50,500),('negative_spot_purchase',-1*(-100),100),('deficit_dual_price',-.1*1000,-100),('surplus_dual_price',.1*100,10),('DSO_official_cross_month_quantity',(100-80)+(0-18),2),('DSO_cross_month_hypothetical_cash',20*50-18*50,100)]:
 arithmetic.append({'name':name,'result':val,'pass':abs(val-expected)<1e-9})
 if abs(val-expected)>1e-9:errors.append(name)
for f in (WORK/'extracted').glob('E*.member_receipt.json'):
 receipt=json.loads(f.read_text(encoding='utf8'));p=ROOT/receipt['derived_path']
 if not p.exists() or sha(p).lower()!=receipt['member_sha256']:errors.append('Archive member hash '+receipt['evidence_id'])
result={'date':'2026-09-30','status':'PASS' if not errors else 'FAIL','scope':'Documentation/evidence integrity and examples only; not legal completeness, model, data QA or backtest approval','frozen_baselines':baseline,'original_integrity':integrity,'source_count':len(sources),'rule_count':len(rules),'unresolved_count':len(uids),'arithmetic_checks':arithmetic,'manually_viewed_key_original_pages':['E14 p19','E15 p1—2','E16 p1—3','E17 p2,4','E24 p22','E26 p17,21,26','E43 p11,12,15','E50 p9—10'],'warnings':['E14/E54 mixed versions; amendment overrides required','E33 binary DOC extraction excluded','E66/E67 raw RAR saved with html extension; selected PDF/DOCX members safely extracted and separately hashed','E46/E52/E65 web verification only; raw original unavailable','Historical version gaps remain U01—U12'],'errors':errors}
(WORK/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:result[k] for k in ['status','source_count','rule_count','unresolved_count','errors']},ensure_ascii=False))
raise SystemExit(1 if errors else 0)
