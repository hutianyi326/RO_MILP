"""Read-only checks for formal review P2 repairs; not a market/model test suite."""
from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, zipfile
import pandas as pd
import xlrd

R = Path(__file__).resolve().parents[2]
W = Path(__file__).resolve().parent
O = R / 'countries/RO/full_period_20261001'
BEFORE = W / 'round1_before_fix'
DTYPES = {'sheet': 'string', 'source_hour_label': 'string',
          'source_local_hour_end_label': 'string'}
checks = []
counts = {}
def check(name, ok, detail=''):
    checks.append({'check': name, 'pass': bool(ok), 'detail': detail})
def read(p):
    return pd.read_csv(p, dtype=DTYPES)
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

saved = json.loads((BEFORE / 'manifest.json').read_text(encoding='utf-8'))
check('all four original affected tables retained',
      all(sha(R/x['preserved_file']) == x['sha256'] for x in saved['files']))
receipt = next(json.loads(p.read_text(encoding='utf-8'))
               for p in (R/'data/raw/RO/full_period/20261001').glob('*/receipt.json')
               if json.loads(p.read_text(encoding='utf-8'))['id'] == 'TSO_GENERATION_ARCHIVE'
               and json.loads(p.read_text(encoding='utf-8')).get('raw_file'))
check('official archive immutable', sha(R/receipt['raw_file']) == receipt['sha256'])
native = read(O/'scada_native_hourly.csv')
archive = zipfile.ZipFile(R/receipt['raw_file'])
books = {m: xlrd.open_workbook(file_contents=archive.read(m))
         for m in native.member.unique()}
label_errors = []
labels = {}
dates = {}
for row in native.itertuples(index=False):
    book = books[row.member]
    try:
        sheet = book.sheet_by_name(row.sheet)  # Exact source name; no zfill correction.
        label = str(sheet.cell_value(row.row-1, 0)).strip()
        date = xlrd.xldate_as_datetime(sheet.cell_value(0, 5), book.datemode).date().isoformat()
        key = (row.member, row.sheet, row.row)
        labels[key] = label
        dates[key] = date
        if label != row.source_hour_label or date != row.source_local_date:
            label_errors.append(str(key))
    except Exception as e:
        label_errors.append(str((row.member, row.sheet, row.row, str(e))))
counts['direct_native_source_locator_rows'] = len(native)
check('native exact member/sheet/row labels and date match source',
      not label_errors, label_errors[:10])
for name in ['scada_native_hourly.csv', 'scada_price_joint_under_clock_A.csv',
             'scada_negative_source_values.csv']:
    current = read(O/name)
    errors = []
    for row in current.itertuples(index=False):
        key = (row.member, row.sheet, row.row)
        if labels.get(key) != row.source_hour_label or dates.get(key) != row.source_local_date:
            errors.append(str(key))
        if hasattr(row, 'source_local_hour_end_label'):
            if row.source_local_hour_end_label != labels.get(key):
                errors.append('hour_end ' + str(key))
    counts[name+' exact_locator_rows'] = len(current)
    check(name+' native labels and associated hour-end labels preserved', not errors, errors[:10])
    old = read(BEFORE/name)
    omitted = {'sheet', 'source_hour_label', 'source_local_hour_end_label'}
    columns = [c for c in old if c not in omitted]
    try:
        pd.testing.assert_frame_equal(old[columns], current[columns], check_dtype=False,
                                      check_exact=False, rtol=1e-12, atol=1e-9)
        check(name+' non-label values unchanged', True)
    except AssertionError as e:
        check(name+' non-label values unchanged', False, str(e)[:1500])

fields = [c for c in native if c.endswith('_mw') and c not in
          ['balance_identity_difference_mw', 'generation_sum_including_storage_difference_mw']]
native['month'] = native.source_local_date.str[:7]
native['source_local_hour_end_label'] = native.source_hour_label
groups = native.groupby(['month', 'source_local_hour_end_label'])
profiles = read(O/'scada_hourly_profiles.csv').set_index(['month', 'source_local_hour_end_label'])
expected_n = groups.size().rename('native_row_count')
expected_valid = groups[fields].count().add_suffix('_valid_count')
expected_means = groups[fields].mean()
for name, expected, actual in [
    ('profile row counts', expected_n.to_frame(), profiles[['native_row_count']]),
    ('profile per-field valid counts', expected_valid, profiles[expected_valid.columns]),
    ('profile means', expected_means, profiles[fields])]:
    try:
        pd.testing.assert_frame_equal(expected.sort_index(), actual.sort_index(),
                                      check_dtype=False, check_exact=False, rtol=1e-12, atol=1e-9)
        check(name+' recomputed from source-located native rows', True)
    except AssertionError as e:
        check(name+' recomputed from source-located native rows', False, str(e)[:1500])
counts['profile_groups'] = len(profiles)
counts['profile_mean_fields'] = len(fields)
counts['profile_valid_count_cells'] = len(profiles)*len(fields)
old_profile = read(BEFORE/'scada_hourly_profiles.csv').set_index(['month', 'source_local_hour_end_label'])
try:
    pd.testing.assert_frame_equal(old_profile[fields], profiles[fields], check_dtype=False,
                                  check_exact=False, rtol=1e-12, atol=1e-9)
    check('all existing profile means unchanged', True)
except AssertionError as e:
    check('all existing profile means unchanged', False, str(e)[:1500])
examples = [('2025-10', '03', 31), ('2025-10', '03 bis', 1),
            ('2025-03', '03', 30), ('2026-03', '03', 30)]
for month, label, expected in examples:
    check(f'DST {month} label {label} disclosed native n={expected}',
          profiles.loc[(month, label), 'native_row_count'] == expected)
check('all group counts sum to 14,567 native rows', profiles.native_row_count.sum() == 14567)
check('three DST days still excluded from UTC joint',
      not set(['2025-03-30', '2025-10-26', '2026-03-29']).intersection(
          read(O/'scada_price_joint_under_clock_A.csv').source_local_date))
check('A joint row count unchanged at 14,496',
      len(read(O/'scada_price_joint_under_clock_A.csv')) == 14496)
check('negative source row count unchanged at 111',
      len(read(O/'scada_negative_source_values.csv')) == 111)
check('frequency field still does not assert Hz', 'frequency_hz' not in native)

# Round1 exact old-state manifests remain immutable; quantify all other live changes.
manifest = json.loads((W/'review_round1_manifest.json').read_text(encoding='utf-8'))
changed = [x['file'] for x in manifest['files'] if sha(R/x['file']) != x['sha256']]
expected_changes = {
 'countries/RO/full_period_20261001/scada_native_hourly.csv',
 'countries/RO/full_period_20261001/scada_price_joint_under_clock_A.csv',
 'countries/RO/full_period_20261001/scada_negative_source_values.csv',
 'countries/RO/full_period_20261001/scada_hourly_profiles.csv',
 'countries/RO/full_period_20261001/analysis_report.md',
 'countries/RO/full_period_20261001/data_dictionary.md',
 'countries/RO/full_period_20261001/supplement_verification.json',
 'project/romania_full_period_20261001/supplement_statistics.py',
 'project/romania_full_period_20261001/final_supplements.py',
 'project/romania_full_period_20261001/review_invocation.json',
}
check('changes confined to disclosed repair/data/validation/doc files',
      set(changed).issubset(expected_changes), changed)
out = {'generated_utc': datetime.now(timezone.utc).isoformat(),
       'status': 'PASS' if all(x['pass'] for x in checks) else 'FAIL',
       'scope': 'P2 source labels and profile counts only; no U/DS or model gate closure',
       'counts': counts, 'checks': len(checks),
       'failed': [x for x in checks if not x['pass']], 'details': checks,
       'round1_live_changes': changed}
(O/'p2_repair_verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k not in ['details','round1_live_changes']},ensure_ascii=False))
if out['status'] != 'PASS':
    raise SystemExit(1)
