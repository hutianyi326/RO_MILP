from pathlib import Path
from pypdf import PdfReader
import json
ROOT=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent
for receipt in (ROOT/'data/raw/RO/gap_closure/20261001').glob('*/receipt.json'):
    r=json.loads(receipt.read_text(encoding='utf8'))
    if r['status']!='HTTP_OK_UNPARSED':continue
    p=ROOT/r['raw_file'];out=W/'pdf_text'/(r['id']+'.txt')
    if p.suffix!='.pdf' or out.exists():continue
    doc=PdfReader(p)
    out.write_text('\n'.join(f'PDF PAGE {i+1}\n'+pg.extract_text() for i,pg in enumerate(doc.pages)),encoding='utf8')
    print(r['id'],len(doc.pages))
