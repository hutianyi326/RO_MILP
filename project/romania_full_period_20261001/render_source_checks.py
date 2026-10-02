from pathlib import Path
import json,pypdfium2 as pdfium
R=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent;D=W/'visual_source_checks';D.mkdir(exist_ok=True)
ms=[json.loads(p.read_text(encoding='utf-8')) for p in (R/'data/raw/RO/full_period/20261001').glob('*/receipt.json')]
for source,page in [('MONTH_2025-02',2),('MONTH_2025-10',2),('MONTH_2026-07',2),('TSO_H1_2026',24),('TSO_Q1_2026',24),('SETTLEMENT_SAMPLE_3',1)]:
    m=next(x for x in ms if x['id']==source and x.get('raw_file'));doc=pdfium.PdfDocument(R/m['raw_file']);image=doc[page-1].render(scale=1.6).to_pil();p=D/(source+'_p'+str(page)+'.png');image.save(p);print(p.relative_to(R).as_posix())
