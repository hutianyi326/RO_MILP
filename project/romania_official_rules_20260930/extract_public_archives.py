"""Extract only named non-executable official archive members to derived evidence."""
from pathlib import Path
from xml.etree import ElementTree as ET
import hashlib,json,subprocess,sys,zipfile
from pypdf import PdfReader
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[2];WORK=Path(__file__).resolve().parent
for sid,member in [('E66','09 10 2024 REVIZIA 1 PO RSF 2022.docx'),('E67','PO CAPACITATE ECHILIBRARE 2024 ED1 REV 2 .pdf')]:
 original=ROOT/'data/raw/RO/rules/20260930'/sid/'original.html'
 # The saved bytes are RAR; extension was inferred incorrectly. Never rename/overwrite raw.
 assert original.read_bytes().startswith(b'Rar!')
 listing=subprocess.check_output(['tar','-tf',str(original)],text=True,encoding='utf-8')
 names=listing.splitlines()
 assert member in names
 for name in names:
  safe=Path(name.replace('\\','/'))
  assert not safe.is_absolute() and '..' not in safe.parts and ':' not in name
 out=WORK/'extracted'/sid;out.mkdir(exist_ok=True)
 target=out/member
 if not target.exists():subprocess.run(['tar','-xf',str(original),'-C',str(out),member],check=True)
 if target.suffix=='.pdf':
  reader=PdfReader(target);text='\n\n'.join(f'=== PDF PAGE {i+1} ===\n'+(p.extract_text() or '') for i,p in enumerate(reader.pages))
 else:
  with zipfile.ZipFile(target) as z:root=ET.fromstring(z.read('word/document.xml'))
  text='\n'.join(''.join(n.itertext()) for n in root.iter() if n.tag.endswith('}p'))
 (WORK/'extracted'/f'{sid}.txt').write_text('DERIVED FROM OFFICIAL RAR MEMBER: '+member+'\n'+text,encoding='utf8')
 receipt={'evidence_id':sid,'raw_content_type':'RAR archive; original.html extension incorrect but immutable bytes retained','original_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'selected_member':member,'derived_path':str(target.relative_to(ROOT)),'member_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'characters':len(text),'archive_members':names}
 (WORK/'extracted'/f'{sid}.member_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps({k:receipt[k] for k in ['evidence_id','selected_member','characters']},ensure_ascii=False))
