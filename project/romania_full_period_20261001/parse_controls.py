"""Official monthly control tables; source Brussels months independent of target RO months."""
from pathlib import Path
from decimal import Decimal
import re,json,pandas as pd
ROOT=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent;O=ROOT/'countries/RO/full_period_20261001'
EN=['January','February','March','April','May','June','July','August','September','October','November','December']
def dec(s):
    s=s.strip().strip('%')
    if ',' in s and '.' in s:
        s=s.replace('.','').replace(',','.') if s.rfind(',')>s.rfind('.') else s.replace(',','')
    elif ',' in s:s=s.replace(',','.')
    return Decimal(s)
da=pd.read_csv(O/'da_native.csv',dtype={'source_price':str,'source_volume':str})
controls=[];idmonth=[];errors=[]
for p in sorted((W/'pdf_text').glob('MONTH*.txt')):
    month=p.stem[6:];year,num=map(int,month.split('-'));label=EN[num-1]+' '+str(year)
    txt=p.read_text(encoding='utf-8').split('PDF PAGE 2')[1].split('PDF PAGE 3')[0]
    first,second=txt.split('Intraday Market',1)
    def row(block):
        matches=[line[len(label):].strip().split() for line in block.splitlines() if line.startswith(label+' ')]
        assert matches and len(matches[0])==5,(month,matches)
        assert all(x==matches[0] for x in matches),(month,'contradictory repeated control')
        return [dec(x) for x in matches[0]]
    volume,avvol,share,arith,cash=row(first);iv,ia,is_,ip,ic=row(second)
    numeric=[dec(line.strip()) for line in second.splitlines() if re.fullmatch(r'[-\d.,]+',line.strip())]
    indices=[i for i,x in enumerate(numeric) if x==volume and i>=2]
    assert len(indices)==1,(month,'headline anchor',indices)
    weighted=numeric[indices[0]-1];assert numeric[indices[0]-2]==arith,(month,'headline arith mismatch')
    g=da[da.source_market_date.str.startswith(month)];energy=Decimal(0);derivedcash=Decimal(0);bound=Decimal(0);pricehours=Decimal(0);hours=Decimal(0)
    for r in g.itertuples():
        h=Decimal(str(r.native_resolution_minutes))/60;p_=Decimal(r.source_price);v_=Decimal(r.source_volume)
        energy+=v_*h;derivedcash+=p_*v_*h;pricehours+=p_*h;hours+=h
        bound+=h*(abs(v_)*Decimal('.005')+abs(p_)*Decimal('.05')+Decimal('.00025'))
    dw=derivedcash/energy;dt=pricehours/hours;dailymean=g.groupby('source_market_date').apply(lambda q:(q.price_eur_mwh*q.duration_hours).sum()/q.duration_hours.sum(),include_groups=False).mean()
    r={'month':month,'source_id':p.stem,'source_clock':'Europe/Brussels source day; not Bucharest monthly target','locator':'PDF page2 current-month comparison row and DAM weighted headline','official_da_volume_mwh':str(volume),'official_da_arithmetic_eur_mwh':str(arith),'official_da_weighted_eur_mwh':str(weighted),'official_da_value_eur':str(cash),'native_derived_volume_mwh':str(energy),'native_price_volume_value_eur':str(derivedcash),'native_time_mean_eur_mwh':str(dt),'native_daily_mean_average_eur_mwh':dailymean,'native_volume_weighted_eur_mwh':str(dw),'volume_difference_mwh':str(energy-volume),'value_difference_eur':str(derivedcash-cash),'value_rounding_bound_A_eur':str(bound+Decimal('.005')),'volume_match_within_display_precision':abs(energy-volume)<=Decimal('.050001'),'weighted_price_match_2decimal':abs(dw-weighted)<=Decimal('.005001'),'cash_within_public_precision_bound_A':abs(derivedcash-cash)<=bound+Decimal('.005'),'same_publisher_control_not_independent_source':True}
    controls.append(r)
    idmonth.append({'month':month,'source_id':p.stem,'locator':'PDF p2 Intraday Market current-month comparison row','volume_mwh':str(iv),'average_price_weighted_eur_mwh':str(ip),'value_eur':str(ic),'share_percent':str(is_),'no_IDA_round_identity':True,'no_intraday_interval_liquidity_inferred':True})
pd.DataFrame(controls).to_csv(O/'monthly_official_reconciliation.csv',index=False,encoding='utf-8-sig');pd.DataFrame(idmonth).to_csv(O/'intraday_monthly_aggregate.csv',index=False,encoding='utf-8-sig')
print(json.dumps({'months':len(controls),'volume_matches':sum(r['volume_match_within_display_precision'] for r in controls),'weighted_matches':sum(r['weighted_price_match_2decimal'] for r in controls),'cash_bounds':sum(r['cash_within_public_precision_bound_A'] for r in controls),'failed':[{k:r[k] for k in ['month','volume_difference_mwh','value_difference_eur','native_volume_weighted_eur_mwh']} for r in controls if not (r['volume_match_within_display_precision'] and r['weighted_price_match_2decimal'] and r['cash_within_public_precision_bound_A'])]}))
