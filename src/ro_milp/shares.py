"""Versioned monthly capacity share assumptions; constrain awarded MW."""
import csv
from datetime import date
from math import isfinite
from pathlib import Path

DEFAULT_SHARE_FILE=Path(__file__).resolve().parents[2]/'config/capacity_share_monthly.csv'
FIELDS=('fcr_market_share_cap','afrr_market_share_cap','fcr_status','afrr_status',
        'fcr_reference_month','afrr_reference_month','scope')

def valid_month(value):
    try:return isinstance(value,str) and len(value)==7 and date.fromisoformat(value+'-01').strftime('%Y-%m')==value
    except (ValueError,TypeError):return False

def validate_schedule(schedule):
    if not isinstance(schedule,dict):raise ValueError('Share schedule must be a month mapping')
    for month,row in schedule.items():
        if not valid_month(month) or not isinstance(row,dict) or set(row)!=set(FIELDS):raise ValueError('Invalid monthly share row '+str(month))
        for prefix in ('fcr','afrr'):
            value=row[prefix+'_market_share_cap']
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not isfinite(value) or not 0<=value<=1:raise ValueError('Share coefficient outside [0,1] '+month)
            if not isinstance(row[prefix+'_status'],str) or not row[prefix+'_status'].strip():raise ValueError('Missing share provenance status '+month)
            ref=row[prefix+'_reference_month']
            if ref and not valid_month(ref):raise ValueError('Invalid share reference month '+month)
        if row['scope'] not in ('FORMAL','LOOKAHEAD_ONLY'):raise ValueError('Invalid share scope '+month)

def load_share_schedule(path=DEFAULT_SHARE_FILE):
    result={}
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames is None or len(reader.fieldnames)!=len(set(reader.fieldnames)) or set(reader.fieldnames)!={'month',*FIELDS}:raise ValueError('Invalid share CSV columns')
        for row in reader:
            month=row.pop('month')
            if month in result:raise ValueError('Duplicate share month '+month)
            for field in ('fcr_market_share_cap','afrr_market_share_cap'):row[field]=float(row[field])
            result[month]=row
    validate_schedule(result)
    return result
