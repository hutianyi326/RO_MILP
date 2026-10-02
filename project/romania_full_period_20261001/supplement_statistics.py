"""Descriptive analyses only; no device simulation or MILP."""
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import json,re,hashlib,math
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent;O=ROOT/'countries/RO/full_period_20261001';ro=ZoneInfo('Europe/Bucharest')
def read(n):
    # Native identifiers are strings; numeric inference loses source leading zeros.
    return pd.read_csv(O/n,dtype={'sheet':'string','source_hour_label':'string','source_local_hour_end_label':'string'})
def write(n,d):pd.DataFrame(d).to_csv(O/n,index=False,encoding='utf-8-sig')
prices=read('da_qh_descriptive_alignment.csv');prices['t']=pd.to_datetime(prices.delivery_start_utc,utc=True)
scada=read('scada_native_hourly.csv');scada['month']=scada.source_local_date.str[:7]
fields=[c for c in scada.columns if c.endswith('_mw') and c not in ['balance_identity_difference_mw','generation_sum_including_storage_difference_mw']]
sstat=[]
for month,g in scada.groupby('month'):
    a=pd.Timestamp(month+'-01',tz=ro);b=a+pd.offsets.MonthBegin(1);expected=int((b.tz_convert('UTC')-a.tz_convert('UTC')).total_seconds()/3600)
    for f in fields:
        v=g[f];sstat.append({'month':month,'field':f,'native_numeric_hours':v.notna().sum(),'expected_hours_under_Bucharest_A':expected,'observed_mwh_under_native_hour_duration_I':v.sum(min_count=1),'mean_mw':v.mean(),'minimum_mw':v.min(),'maximum_mw':v.max(),'negative_native_values':(v<0).sum(),'scope':'SCADA table fields; prosumer and net/gross coverage unknown; not national gross totals'})
write('scada_monthly_statistics.csv',sstat)
scada['source_local_hour_end_label']=scada.source_hour_label.astype(str)
profile_groups=scada.groupby(['month','source_local_hour_end_label'])
profiles=profile_groups[fields].mean()
profiles=profiles.join(profile_groups.size().rename('native_row_count'))
profiles=profiles.join(profile_groups[fields].count().add_suffix('_valid_count')).reset_index()
write('scada_hourly_profiles.csv',profiles)
negative=scada.loc[(scada[['coal_mw','hydrocarbons_mw','hydro_mw','nuclear_mw','wind_mw','solar_mw','bio_mw']]<0).any(axis=1)]
write('scada_negative_source_values.csv',negative)
eligible=scada[scada.descriptive_usable_under_clock_A].copy()
eligible['t']=pd.to_datetime(eligible.delivery_start_utc_provisional,utc=True)
p_hour=prices.set_index('t').price_eur_mwh.resample('h').mean().rename('da_time_mean_eur_mwh').reset_index()
joint=eligible.merge(p_hour,on='t',how='inner',validate='one_to_one');write('scada_price_joint_under_clock_A.csv',joint.drop(columns='t'))
corr=[];bins=[]
for month,g in joint.groupby('month'):
    v=g[['scada_residual_consumption_minus_wind_solar_mw','da_time_mean_eur_mwh']].dropna()
    corr.append({'month':month,'paired_hours':len(v),'pearson_under_clock_A':v.iloc[:,0].corr(v.iloc[:,1]),'not_causal':True,'timezone_alignment_provisional':True})
    g=g.copy();g['residual_bin_mw']=pd.cut(g.scada_residual_consumption_minus_wind_solar_mw,[-float('inf'),2000,3000,4000,5000,6000,float('inf')]).astype(str)
    for label,h in g.groupby('residual_bin_mw'):
        bins.append({'month':month,'scada_residual_bin_mw':label,'paired_hours':len(h),'mean_da_eur_mwh':h.da_time_mean_eur_mwh.mean(),'median_da_eur_mwh':h.da_time_mean_eur_mwh.median(),'negative_da_hours':(h.da_time_mean_eur_mwh<0).sum(),'clock_A':True})
write('scada_residual_price_correlations.csv',corr);write('scada_residual_price_bins.csv',bins)
load=read('dailyConsumptionOverview.csv');load['hour']=pd.to_datetime(load.delivery_start_utc,utc=True).dt.tz_convert(ro).dt.hour;load['weekend']=pd.to_datetime(load.delivery_start_utc,utc=True).dt.tz_convert(ro).dt.dayofweek>=5
write('load_weekday_weekend.csv',load.groupby(['month','weekend']).grossRealizedConsumption.agg(['mean','count','min','max']).reset_index())
duration=load.grossRealizedConsumption.sort_values(ascending=False).reset_index(drop=True);write('load_duration_curve.csv',pd.DataFrame({'rank':range(1,len(duration)+1),'hours_exceeded':pd.Series(range(1,len(duration)+1))*.25,'gross_load_mw':duration}))
# Native provider labels, not consolidated legal entities. Join only within verified tender intervals.
cap=read('capacity_statistics.csv');cap['month']=pd.to_datetime(cap.delivery_start_utc,utc=True).dt.tz_convert(ro).dt.strftime('%Y-%m')
provider=[]
for item in json.loads((O/'capacity_provider_structures.json').read_text(encoding='utf-8')):
    for label,v in item['contracted_power'].items():
        for r in v.get('timeIntervalList',[]):
            a=pd.Timestamp(r['timeInterval']['from']);b=pd.Timestamp(r['timeInterval']['to'])
            provider.append({'tender_code':item['tender_code'],'product':item['product'],'provider_source_label':label,'delivery_start_utc':a.isoformat().replace('+00:00','Z'),'delivery_end_utc':b.isoformat().replace('+00:00','Z'),'contracted_power_mw':r.get('power'),'duration_hours':(b-a).total_seconds()/3600,'source_id':item['source_id']})
pr=pd.DataFrame(provider);key=['tender_code','product','delivery_start_utc']
valid=pr.merge(cap[key+['demand_mw','satisfied_ratio','month']],on=key,how='inner',validate='many_to_one')
write('capacity_provider_native_filtered.csv',valid)
sums=valid.groupby(key).contracted_power_mw.sum(min_count=1).rename('sum_provider_contracted_mw').reset_index().merge(cap[key+['demand_mw','satisfied_ratio']],on=key,how='right',validate='one_to_one')
sums['demand_times_source_ratio_mw']=sums.demand_mw*sums.satisfied_ratio;sums['difference_mw']=sums.sum_provider_contracted_mw-sums.demand_times_source_ratio_mw;sums['complete_sum_check']=sums.difference_mw.abs()<.000001
write('capacity_provider_sum_checks.csv',sums)
complete=valid.merge(sums.loc[sums.complete_sum_check,key],on=key,validate='many_to_one');complete['contracted_mw_hours']=complete.contracted_power_mw*complete.duration_hours
shares=[];hhi=[]
for (month,product),g in complete.groupby(['month','product']):
    amounts=g.groupby('provider_source_label').contracted_mw_hours.sum(min_count=1);total=amounts.sum();s=amounts/total if total>0 else amounts*float('nan')
    for name,value in amounts.items():shares.append({'month':month,'product':product,'source_provider_label':name,'contracted_mw_hours_over_checked_intervals':value,'share_of_published_labels':s[name],'not_consolidated_legal_entity':True})
    hhi.append({'month':month,'product':product,'checked_native_hours':g.delivery_start_utc.nunique(),'published_positive_labels':(amounts>0).sum(),'contracted_exposure_mw_hours':total,'HHI_published_label_shares_0_10000':(s*s).sum()*10000,'not_competition_or_station_award_probability':True})
write('capacity_provider_label_shares.csv',shares);write('capacity_provider_label_concentration.csv',hhi)
# Capacity/DA UTC correspondence does not make raw LEI prices monetary payments.
cc=cap.merge(p_hour.rename(columns={'t':'timestamp'}).assign(delivery_start_utc=lambda d:d.timestamp.dt.strftime('%Y-%m-%dT%H:%M:%SZ')).drop(columns='timestamp'),on='delivery_start_utc',validate='many_to_one')
capcorr=[]
for (month,product),g in cc.groupby(['month','product']):
    v=g[['average_accepted_price_LEI_denominator_unknown','da_time_mean_eur_mwh']].dropna();capcorr.append({'month':month,'product':product,'paired_hours':len(v),'pearson_raw_statistical_values':v.iloc[:,0].corr(v.iloc[:,1]) if len(v)>1 else None,'currency_and_denominator_not_converted':True,'not_margin_or_payments':True})
write('capacity_DA_descriptive_correlations.csv',capcorr)
# Explicitly preserve the four cost samples and actual revision differences, no price inference.
costs=[];costmeta=[]
pattern=re.compile(r'^(\d{1,2}\.\d{2}\.\d{4}) (\d{2}:\d{2}) - (\d{2}:\d{2}) (-?[\d,]+\.\d{2}) (-?[\d,]+\.\d{2}) (-?[\d,]+\.\d{2}) (-?[\d,]+\.\d{2})$')
for f in sorted(W.glob('SETTLEMENT_SAMPLE_*_text.txt')):
    source=f.stem.removesuffix('_text');txt=f.read_text(encoding='utf-8');count=0;date=re.search(r'Data: ([\d.]+)',txt).group(1)
    for page in re.split(r'PDF PAGE \d+\n',txt)[1:]:
        pno=txt[:txt.find(page)].count('PDF PAGE ')
        for line in page.splitlines():
            r=pattern.match(line)
            if not r:continue
            values=[float(x.replace(',','')) for x in r.groups()[3:]]
            costs.append({'source_id':source,'source_record_date_not_publication':date,'delivery_local_date':r.group(1),'local_interval_start_label':r.group(2),'source_interval_end_inclusive_label':r.group(3),'system_cost_lei':values[0],'system_revenue_lei':values[1],'network_constraint_cost_lei':values[2],'effective_system_cost_lei':values[3],'page':pno,'identity_diff_lei':values[3]-(values[0]-values[1]-values[2]),'not_imbalance_price':True});count+=1
    costmeta.append({'source_id':source,'date_label_not_publication':date,'parsed_native_intervals':count,'schema':'system amounts LEI, no LEI/MWh deficit/surplus price'})
write('official_settlement_cost_samples.csv',costs);write('settlement_cost_sample_checks.csv',costmeta)
cf=pd.DataFrame(costs);changes=[]
base=cf[cf.source_id=='SETTLEMENT_SAMPLE_1'];key2=['delivery_local_date','local_interval_start_label']
for source in ['SETTLEMENT_SAMPLE_2','SETTLEMENT_SAMPLE_3']:
    g=base.merge(cf[cf.source_id==source],on=key2,suffixes=('_VM','_revision'),validate='one_to_one');delta=g.effective_system_cost_lei_revision-g.effective_system_cost_lei_VM
    changes.append({'comparison':'SETTLEMENT_SAMPLE_1 vs '+source,'paired_intervals':len(g),'changed_effective_cost_intervals':(delta.abs()>.00001).sum(),'total_effective_cost_change_lei':delta.sum(),'largest_absolute_interval_change_lei':delta.abs().max(),'not_imbalance_price_change':True})
write('settlement_revision_demonstration.csv',changes)
# Deterministic event selection prevents selective narratives.
event=[]
for kind,index in [('DA minimum',prices.price_eur_mwh.idxmin()),('DA maximum',prices.price_eur_mwh.idxmax())]:
    r=prices.loc[index];event.append({'kind':kind,'anchor_utc':r.delivery_start_utc,'anchor_value':r.price_eur_mwh,'unit':'EUR/MWh','source_id':r.source_id,'selection':'global first-occurring extreme'})
r=load.loc[load.grossRealizedConsumption.idxmax()];event.append({'kind':'gross load maximum','anchor_utc':r.delivery_start_utc,'anchor_value':r.grossRealizedConsumption,'unit':'MW','source_id':r.source_id,'selection':'global first-occurring maximum'})
for file,kind,col in [('negative_price_events.csv','longest negative-price run','duration_hours'),('activation_continuous_events.csv','longest positive system aFRR run','duration_hours')]:
    g=read(file);r=g.loc[g[col].idxmax()];event.append({'kind':kind,'anchor_utc':r.start_utc,'end_utc':r.end_utc,'anchor_value':r[col],'unit':'hours','source_id':r.source_id,'selection':'global first-occurring longest continuous run; gaps/zero cut runs'})
write('deterministic_event_cards.csv',event)
summary={'scada_native_rows':len(scada),'scada_utc_pair_hours_under_A':len(joint),'scada_negative_technology_rows_retained':len(negative),'provider_native_filtered_rows':len(valid),'provider_hour_sum_checks':len(sums),'provider_hour_sum_match':int(sums.complete_sum_check.sum()),'cost_samples':costmeta,'cost_amount_max_identity_diff_lei':cf.identity_diff_lei.abs().max(),'no_market_price_inferred_from_costs':True,'overall_step3_complete':False}
(O/'supplement_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,default=str))
