"""Read exported CSV independently with Decimal; do not regenerate price files."""
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo
import csv, hashlib, json

ROOT=Path(__file__).resolve().parents[2]; WORK=Path(__file__).resolve().parent
OUT=ROOT/'data/processed/RO/prices_eur_v1_20261002'; SRC=ROOT/'data/processed/RO/prices_v1_20261002'
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
for r in manifest['files']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
rates={r['delivery_date_bucharest']:r for r in rows(OUT/'fx_by_bucharest_delivery_day.csv')}
count=0;values=0
for before,after in [('prices_qh_formal_20250101_20260831.csv','prices_eur_qh_20250101_20260831.csv'),('prices_qh_observation_20260901.csv','prices_eur_observation_20260901.csv')]:
    a=rows(SRC/before);b=rows(OUT/after);assert len(a)==len(b)
    for old,new in zip(a,b):
        assert new['price_currency']=='EUR'
        assert not any('_price_ron_' in c for c in new)
        assert old['delivery_start_utc']==new['delivery_start_utc']
        day=datetime.fromisoformat(new['delivery_start_utc'].replace('Z','+00:00')).astimezone(ZoneInfo('Europe/Bucharest')).date().isoformat()
        assert day==new['local_date']
        fx=rates[day];assert new['fx_fixing_date']==fx['fx_fixing_date']<day
        assert Decimal(new['fx_ron_per_eur'])==Decimal(fx['fx_ron_per_eur'])
        assert Decimal(old['da_price_eur_per_mwh'])==Decimal(new['da_price_eur_per_mwh'])
        for key,value in old.items():
            if '_price_ron_' not in key:continue
            target=key.replace('_ron_','_eur_').replace('_candidate','_proxy');actual=new[target]
            if not value:assert not actual;continue
            expected=Decimal(value)/Decimal(fx['fx_ron_per_eur'])
            assert abs(expected-Decimal(actual))<Decimal('0.00000001'),(key,new['delivery_start_utc'])
            assert (Decimal(value)==0)==(Decimal(actual)==0)
            assert (Decimal(value)<0)==(Decimal(actual)<0)
            values+=1
        count+=1
sources=rows(OUT/'source_registry.csv');da=[r for r in sources if r['publisher']=='OPCOM' and r['source_id'].startswith('DA_')]
for r in da:
    text=(ROOT/r['raw_file']).read_text(encoding='utf-8-sig')
    assert 'Euro/MWh' in text[:2500],r['source_key']
report=dict(status='PASS',exported_qh_rows=count,non_null_RON_to_EUR_values_recomputed=values,DA_original_headers_confirmed_Euro_per_MWh=len(da),manifest_files_verified=len(manifest['files']),tolerance_eur='1e-8',method='Independent csv/Decimal read-back; timezone from datetime and zoneinfo; not an independent agent review')
(WORK/'export_readback_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
