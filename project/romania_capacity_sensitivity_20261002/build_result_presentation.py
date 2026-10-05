"""RO result presentation aligned to ES_MILP report baseline v1 at pinned Git commit.

Aggregation is rebuilt from executed QH/phases; model source and market inputs unchanged.
Run with Python/pandas/matplotlib (separate reporting environment from the solver).
"""
import argparse,json,hashlib,calendar,sys,html,re
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from PIL import Image,ImageOps,ImageDraw

MARKETS=('DA','FCR_cap','cap_up','cap_down','act_up','act_down')
FIELDS=dict(zip(MARKETS,('da_eur','fcr_capacity_eur','afrr_up_capacity_eur','afrr_down_capacity_eur','afrr_up_activation_eur','afrr_down_activation_eur')))
LABELS=dict(zip(MARKETS,('DA电能','FCR容量','aFRR容量上调','aFRR容量下调','aFRR激活上调','aFRR激活下调')))
COLORS=dict(zip(MARKETS,('#4472C4','#ED7D31','#70AD47','#A5A5A5','#FFC000','#8064A2')))
PIN='70651210d0ad98ac820644754508f76363d2c799'
HERE=Path(__file__).resolve().parent

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def fmt(value,digits=2):return '—' if value is None or pd.isna(value) else f'{value:,.{digits}f}'
def table(headers,records):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'---|'*len(headers)]+['| '+' | '.join(map(str,row))+' |' for row in records])
def save_csv(frame,path):frame.to_csv(path,index=False,encoding='utf-8-sig',float_format='%.12g')

def chart(labels,values,title,unit,path,bounds=None):
    fig,ax=plt.subplots(figsize=(14,5.5));x=np.arange(len(labels));pos=np.zeros(len(labels));neg=pos.copy()
    for m in MARKETS:
        y=np.array([row[m] for row in values]);bottom=np.where(y>=0,pos,neg)
        ax.bar(x,y,bottom=bottom,color=COLORS[m],label=LABELS[m],width=.72)
        pos+=np.maximum(y,0);neg+=np.minimum(y,0)
    ax.plot(x,pos+neg,color='#202936',linewidth=1.4,marker='o',markersize=3,label='合计')
    ax.axhline(0,color='#556070',linewidth=.7);ax.set_xticks(x,labels,rotation=45 if len(labels)>15 and '-' in str(labels[0]) else 0,ha='right' if '-' in str(labels[0]) else 'center')
    ax.set_ylabel(unit);ax.set_title(title,loc='left',fontweight='bold',pad=16);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    if bounds:ax.set_ylim(bounds)
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.19),ncol=4,frameon=False)
    fig.tight_layout();fig.savefig(path,bbox_inches='tight');fig.savefig(path.with_suffix('.png'),dpi=130,bbox_inches='tight');plt.close(fig)

def build(run_dir,out,validation):
    run_dir=run_dir.resolve();out=out.resolve();out.mkdir(parents=True,exist_ok=False)
    manifest=read(run_dir/'manifest.json');summary=read(run_dir/'summary.json');audit=read(validation);cfg=manifest['identity']['config'];P=cfg['power_mw'];p=cfg['p_up'];assert p==cfg['p_down']==cfg['p_fcr'] and p in (0.6,0.8,1.) and not cfg['daily_p']
    assert summary['status']=='COMPLETE' and audit['status']=='PASS' and audit['run_manifest_sha256']==sha(run_dir/'manifest.json')
    assert audit['code_sha256']==manifest['identity']['code_sha256'] and audit['input_sha256']==manifest['identity']['input_sha256']
    q=pd.read_csv(run_dir/'executed_qh.csv');phase=pd.read_csv(run_dir/'executed_phases.csv');metrics=pd.read_csv(run_dir/'window_metrics.csv')
    t=pd.to_datetime(q['delivery_start_utc'],utc=True);local=t.dt.tz_convert('Europe/Bucharest')
    expected=pd.date_range(manifest['identity']['start'],manifest['identity']['end'],freq='15min',inclusive='left')
    assert list(t)==list(expected) and len(q)==58364 and len(metrics)==608
    q['month']=local.dt.strftime('%Y-%m');q['year']=local.dt.year;q['day']=local.dt.strftime('%Y-%m-%d');q['quarter']='Q'+local.dt.quarter.astype(str);q['hour']=local.dt.hour
    q['utc_hour']=t.dt.floor('h');q['fcr_in_scope']=q['day']>='2025-06-01'
    for m,f in FIELDS.items():q[m]=q[f].astype(float)
    assert np.isfinite(q[list(MARKETS)].to_numpy()).all()
    assert np.allclose(q[list(MARKETS)].sum(axis=1),q.total_eur,rtol=1e-9,atol=1e-5)
    assert abs(q.total_eur.sum()-summary['total_eur'])<.01
    physical=phase.assign(charge_ac_mwh=phase.C*phase.hours,discharge_ac_mwh=phase.D*phase.hours).groupby('start')[['charge_ac_mwh','discharge_ac_mwh']].sum()
    q=q.join(physical,on='delivery_start_utc');assert not q[['charge_ac_mwh','discharge_ac_mwh']].isna().any().any()
    def aggregate(group,key):
        records=[]
        for name,g in group:
            row={key:name}
            for m in MARKETS:row[m+'_kEUR']=g[m].sum()/1000;row[m+'_kEUR_per_MW']=g[m].sum()/1000/P
            row.update(total_kEUR=g.total_eur.sum()/1000,total_kEUR_per_MW=g.total_eur.sum()/1000/P,efc=g.efc.sum(),total_qh=len(g),executed_qh=len(g),execution_coverage=1.,da_valid_qh=int(g.da_data_valid.sum()),afrr_valid_qh=int(g.afrr_hour_data_valid.sum()),fcr_valid_qh=int(g.fcr_hour_data_valid.sum()),fcr_in_scope_qh=int(g.fcr_in_scope.sum()),initial_no_prior_qh=int(g.initial_no_prior_commitment.sum()),charge_ac_mwh=g.charge_ac_mwh.sum(),discharge_ac_mwh=g.discharge_ac_mwh.sum())
            for m in ('da','afrr','fcr'):row[m+'_data_coverage']=row[m+'_valid_qh']/len(g)
            row['fcr_in_scope_coverage']=row['fcr_valid_qh']/row['fcr_in_scope_qh'] if row['fcr_in_scope_qh'] else None
            row['afrr_up_activation_mwh']=g.afrr_up_activation_mwh.sum();row['afrr_down_activation_mwh']=g.afrr_down_activation_mwh.sum()
            for field in ('da_mw','afrr_up_mw','afrr_down_mw','fcr_mw'):row['average_'+field]=g[field].mean()
            row['first_local_date']=g.day.iloc[0];row['last_local_date']=g.day.iloc[-1];row['complete_days']=g.day.nunique();row['calendar_complete']=True
            records.append(row)
        return pd.DataFrame(records)
    monthly=aggregate(q.groupby('month',sort=True),'month');annual=aggregate(q.groupby('year',sort=True),'year');daily=aggregate(q.groupby('day',sort=True),'day')
    for i,row in annual.iterrows():
        y=int(row.year);annual.loc[i,'budget_efc']=manifest['identity']['budgets'][str(y)];annual.loc[i,'budget_utilization']=row.efc/annual.loc[i,'budget_efc'];annual.loc[i,'calendar_year_days']=366 if calendar.isleap(y) else 365
    assert len(monthly)==20 and len(annual)==2 and len(daily)==608
    shares=monthly[['month','total_qh','afrr_valid_qh','fcr_valid_qh']].copy()
    for m in MARKETS:shares[m+'_share_pct']=monthly[m+'_kEUR']/monthly.total_kEUR.replace(0,np.nan)*100
    # UTC groups keep repeated autumn local hours separate; four QH per actual hour.
    assert q.groupby('utc_hour').size().eq(4).all()
    actual=q.groupby('utc_hour').agg({**{m:'sum' for m in MARKETS},'month':'first','quarter':'first','hour':'first','day':'first','afrr_hour_data_valid':'all','fcr_hour_data_valid':'all'}).reset_index()
    assert len(actual)==14591
    def hourmeans(group,keys):
        records=[]
        for key,g in group:
            key=key if isinstance(key,tuple) else (key,);r=dict(zip(keys,key))
            for m in MARKETS:r[m+'_kEUR_per_MW']=g[m].mean()/1000/P
            r.update(total_kEUR_per_MW=sum(r[m+'_kEUR_per_MW'] for m in MARKETS),sample_hours=len(g),afrr_valid_hours=int(g.afrr_hour_data_valid.sum()),fcr_valid_hours=int(g.fcr_hour_data_valid.sum()))
            records.append(r)
        return pd.DataFrame(records)
    hourly=hourmeans(actual.groupby('hour'),['hour']);quarterly=hourmeans(actual.groupby(['quarter','hour']),['quarter','hour']);heat=hourmeans(actual.groupby(['month','hour']),['month','hour'])
    rolling=[]
    for i in range(11,len(monthly)):
        g=monthly.iloc[i-11:i+1];r=dict(month=g.month.iloc[-1],window_start=g.month.iloc[0],window_end=g.month.iloc[-1],total_kEUR=g.total_kEUR.sum(),total_kEUR_per_MW=g.total_kEUR_per_MW.sum(),efc=g.efc.sum(),total_qh=int(g.total_qh.sum()),executed_qh=int(g.executed_qh.sum()),execution_coverage=1.)
        for m in ('da','afrr','fcr'):r[m+'_data_coverage']=g[m+'_valid_qh'].sum()/g.total_qh.sum()
        for m in MARKETS:r[m+'_kEUR_per_MW']=g[m+'_kEUR_per_MW'].sum()
        rolling.append(r)
    rolling=pd.DataFrame(rolling);assert len(rolling)==9
    for name,frame in [('monthly',monthly),('annual',annual),('daily',daily),('monthly_market_shares',shares),('hourly',hourly),('quarterly_hourly',quarterly),('monthly_hourly_heatmap',heat),('rolling_12m',rolling)]:save_csv(frame,out/(name+'.csv'))
    total=q.total_eur.sum();efc=q.efc.sum();market=pd.DataFrame([dict(market=m,label=LABELS[m],kEUR=q[m].sum()/1000,kEUR_per_MW=q[m].sum()/1000/P,share_pct=q[m].sum()/total*100) for m in MARKETS]);save_csv(market,out/'market_totals.csv')
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'svg.fonttype':'none','font.size':10})
    def vals(frame,suffix):return [{m:row[m+suffix] for m in MARKETS} for _,row in frame.iterrows()]
    for unit,suffix in [('kEUR','_kEUR'),('kEUR/MW','_kEUR_per_MW')]:chart(list(monthly.month),vals(monthly,suffix),'罗马尼亚 100MW/200MWh · 月度条件毛现金',unit,out/('monthly_revenue_'+unit.replace('/','_per_')+'.svg'))
    chart(list(hourly.hour),vals(hourly,'_kEUR_per_MW'),'全期当地钟点平均现金 · 每个实际小时','kEUR/MW',out/'hourly_average_kEUR_per_MW.svg')
    v=quarterly[[m+'_kEUR_per_MW' for m in MARKETS]].to_numpy();lo=min(0,np.minimum(v,0).sum(axis=1).min());hi=max(0,np.maximum(v,0).sum(axis=1).max());pad=max(.001,(hi-lo)*.12);bounds=(lo-pad,hi+pad)
    for quarter,g in quarterly.groupby('quarter'):chart(list(g.hour),vals(g,'_kEUR_per_MW'),quarter+'当地钟点平均现金 · 跨年度同季度合并','kEUR/MW',out/(quarter.lower()+'_hourly_average_kEUR_per_MW.svg'),bounds)
    fig,ax=plt.subplots(figsize=(14,5));ax.plot(rolling.month,rolling.total_kEUR_per_MW,'o-',color=COLORS['DA'],linewidth=2)
    for i,value in enumerate(rolling.total_kEUR_per_MW):ax.annotate(fmt(value),(i,value),xytext=(0,9),textcoords='offset points',ha='center',fontsize=9)
    ax.set_ylim(0,rolling.total_kEUR_per_MW.max()*1.15);ax.set_ylabel('kEUR/MW');ax.set_title('滚动12个完整自然月 · 条件毛现金',loc='left',fontweight='bold');ax.grid(axis='y',alpha=.2)
    fig.tight_layout();fig.savefig(out/'rolling_12m_revenue_kEUR_per_MW.svg');fig.savefig(out/'rolling_12m_revenue_kEUR_per_MW.png',dpi=130);plt.close(fig)
    grid=heat.pivot(index='month',columns='hour',values='total_kEUR_per_MW');lim=max(abs(grid.min().min()),abs(grid.max().max()),1e-9)
    fig,ax=plt.subplots(figsize=(14,8));im=ax.imshow(grid.values,cmap='RdBu',norm=TwoSlopeNorm(vmin=-lim,vcenter=0,vmax=lim),aspect='auto')
    ax.set_xticks(range(24),range(24));ax.set_yticks(range(len(grid)),grid.index);ax.set_xlabel('Bucharest当地钟点');ax.set_title('月份×钟点平均现金 · 蓝正红负、零中心',loc='left',fontweight='bold');fig.colorbar(im,ax=ax,label='kEUR/MW / 实际小时')
    fig.tight_layout();fig.savefig(out/'monthly_hourly_heatmap_kEUR_per_MW.svg');fig.savefig(out/'monthly_hourly_heatmap_kEUR_per_MW.png',dpi=130);plt.close(fig)
    latest=rolling.iloc[-1];solvertime=float(metrics.solve_seconds.sum());status=metrics.status.value_counts().to_dict()
    report=[f'# 罗马尼亚MILP完整测算结果：100MW / 200MWh · 容量收入系数{p:.0%}','', '正式统计期：2025-01-01至2026-08-31（Bucharest当地交付日），608天。运行COMPLETE，608个窗口、58,364个正式QH；2026-09-01观察日不计正式现金。','',
            '## 假设概览','',table(['项目','本次配置'],[
            ['电池规模与SOC','100MW / 200MWh直流名义容量；SOC10—190MWh，可用180MWh；初末10MWh'],['效率/年度EFC','单向92%；DC吞吐/360MWh；2025预算600，2026年1—8月399.452054795'],['优化与币种','全EUR；两当地日规划首日执行；完美历史信息、价格接受者'],['容量系数',f'p上调=p下调=pFCR={p:.0%}，独立重新优化；外生现金系数，不是实测中标率'],['名义事件时表','交付前一当地日：容量09关闸/10结果，DA13关闸/14结果；研究假设'],['FCR','对称研究单元5×20MW、共享能量池；30分钟双向静态缓冲，仅容量机会价值'],['aFRR','严格三相下→上→基准；不归一化；无效QH覆盖的完整小时上下订单禁用'],['源数据/汇率','OPCOM DA、Transelectrica DAMAS容量/激活价量、BNR；按Bucharest交付日严格前序参考日换汇'],['数据覆盖','DA 58,364/58,364；aFRR 53,500/58,364；FCR 43,292/43,872（6月起范围）'],['首日','过去已关闸且无历史账本订单为0，96QH；容量/激活与日前均不补报'],['求解状态',f'{int((metrics.status==0).sum())}窗status0，{int((metrics.status==1).sum())}窗限时可行解（按1e-4容许gap）；最大还原目标gap={metrics.objective_gap.max():.8g}'],['求解耗时',f'累计{solvertime:.2f}秒；单窗中位{metrics.solve_seconds.median():.3f}秒，最大{metrics.solve_seconds.max():.3f}秒'],['审核状态','全期独立自动复算PASS；reviewer最终结论见本任务review_and_acceptance.md']]),'',
            '**解释边界：** 以下为条件事后市场毛现金，未扣投资、运维、税费等成本。系统容量均价和激活字段采用已批准代理口径，不等于本站结算发票。FCR没有频率激活电量、损耗及额外循环。两日滚动不是已证明的全时域全局最优上界。','',
            '## 结果概览','', '### 全期与自然年市场现金','',table(['期间','kEUR','kEUR/MW','EFC'],[['全期20个月',fmt(total/1000),fmt(total/1000/P),fmt(efc)],['月均（20个月、不外推）',fmt(total/20000),fmt(total/20000/P),fmt(efc/20)]]+[[str(int(r.year))+'年 '+r.first_local_date+'—'+r.last_local_date,fmt(r.total_kEUR),fmt(r.total_kEUR_per_MW),fmt(r.efc)] for _,r in annual.iterrows()]),'',
            f'2026年只含1—8月，不年化。模型执行覆盖为100%，不代表各市场原始字段都完整；aFRR/FCR源失效订单按既定规则禁用，缺失收益不补算。','',
            '### 最新及逐月滚动12个月','',f'最新窗口：{latest.window_start}—{latest.window_end}，{fmt(latest.total_kEUR)} kEUR，{fmt(latest.total_kEUR_per_MW)} kEUR/MW。','',
            f'本报告为p={p:.0%}独立重优化情景，三情景比较另见汇总报告。每窗为12个完整自然月，不对市场缺口按比例外推。','', '![滚动12个月现金](rolling_12m_revenue_kEUR_per_MW.svg)','',
            table(['窗口终月','12个月范围','kEUR/MW','aFRR数据覆盖','FCR数据覆盖（全窗口）'],[[r.month,r.window_start+'—'+r.window_end,fmt(r.total_kEUR_per_MW),fmt(r.afrr_data_coverage*100)+'%',fmt(r.fcr_data_coverage*100)+'%'] for _,r in rolling.iterrows()]),'',
            '### EFC及能量','',table(['年份','已执行EFC','固定预算','使用率'],[[str(int(r.year)),fmt(r.efc,6),fmt(r.budget_efc,6),fmt(r.budget_utilization*100)+'%'] for _,r in annual.iterrows()]),'',
            f'全期AC物理充电{fmt(q.charge_ac_mwh.sum())}MWh，放电{fmt(q.discharge_ac_mwh.sum())}MWh；EFC直接累加相位DC吞吐，非QH净SOC差，亦非完整充放事件计数。正式末SOC={summary["end_soc_mwh"]:.9f}MWh。','',
            '### 六项市场现金与占比','',table(['市场','kEUR','kEUR/MW','占总现金'],[[r.label,fmt(r.kEUR),fmt(r.kEUR_per_MW),fmt(r.share_pct)+'%'] for _,r in market.iterrows()]+[['合计',fmt(total/1000),fmt(total/1000/P),'100.00%']]),'',
            '所有现金保持符号，负价不裁剪；下调现金＝−原价格×下调激活电量，负下调价格可产生正现金。占比以带符号总现金为分母，正项合计可能超过100%。','',
            '### 平均功率与预留容量','',table(['市场','平均MW','含义'],[['DA',fmt(q.da_mw.mean()),'售正购负，净额可抵消'],['FCR容量',fmt(q.fcr_mw.mean()),'对称预留、收入只计一次'],['aFRR容量上调',fmt(q.afrr_up_mw.mean()),'全额物理预留'],['aFRR容量下调',fmt(q.afrr_down_mw.mean()),'全额物理预留'],['aFRR激活上调',fmt(q.afrr_up_activation_mwh.sum()/(len(q)*.25)),'模型激活MWh/全期小时'],['aFRR激活下调',fmt(q.afrr_down_activation_mwh.sum()/(len(q)*.25)),'方向电量为正，现金另按价格符号']]),'',
            '均值分母包含全部58,364个正式QH和首日零承诺；不是各市场可用时段条件均值。各行不可相加解释为电站容量分配比例。','',
            '## 月度结果概览','', '![月度现金kEUR](monthly_revenue_kEUR.svg)','', '![月度单位功率现金](monthly_revenue_kEUR_per_MW.svg)','']
    for suffix,unit in [('_kEUR','kEUR'),('_kEUR_per_MW','kEUR/MW')]:
        records=[]
        for year,mg in monthly.groupby(monthly.month.str[:4]):
            for _,r in mg.iterrows():records.append([r.month]+[fmt(r[m+suffix]) for m in MARKETS]+[fmt(r['total'+suffix])])
            records.append([year+'年月均']+[fmt(mg[m+suffix].sum()/len(mg)) for m in MARKETS]+[fmt(mg['total'+suffix].sum()/len(mg))])
            records.append([year+'年合计']+[fmt(mg[m+suffix].sum()) for m in MARKETS]+[fmt(mg['total'+suffix].sum())])
        report+=['### 月度明细与年汇总 · '+unit,'',table(['月份']+[LABELS[m] for m in MARKETS]+['合计'],records),'']
    report+=['### 月度六项现金占比','',table(['月份']+[LABELS[m] for m in MARKETS],[[r.month]+[fmt(r[m+'_share_pct'])+'%' for m in MARKETS] for _,r in shares.iterrows()]),'',
             '### 月度数据覆盖与EFC','',table(['月份','执行QH','aFRR有效QH','FCR有效/范围内QH','EFC'],[[r.month,str(int(r.total_qh)),str(int(r.afrr_valid_qh)),str(int(r.fcr_valid_qh))+'/'+str(int(r.fcr_in_scope_qh)),fmt(r.efc)] for _,r in monthly.iterrows()]),'',
             '## 小时级结果概览','', '先合计每个实际小时的四个执行QH，再按Bucharest当地钟点取均值；秋季重复小时按不同UTC偏移分别计样本。全期14,591个完整执行小时，源失效市场的模型零订单保留，数据有效小时数在CSV单列。','',
             '所有小时曲线与热图均用kEUR/MW/实际小时；图上0.03表示30EUR/MW。季度图跨年度同季度合并，四图共用纵轴。','', '![全期小时现金](hourly_average_kEUR_per_MW.svg)','', '### 月份×小时热力图','', '蓝正红负，零中心；每格为该月该钟点每个实际小时平均现金，不是该月累计。','', '![月小时热力图](monthly_hourly_heatmap_kEUR_per_MW.svg)','']
    for quarter,g in actual.groupby('quarter'):
        report+=['### '+quarter,'',f'样本月份：{", ".join(sorted(g.month.unique()))}；实际小时样本{len(g):,}。','',f'![{quarter}小时现金]({quarter.lower()}_hourly_average_kEUR_per_MW.svg)','']
    report+=['## 输出、来源和适用范围','',
             '- monthly.csv、annual.csv、daily.csv：六项现金（kEUR/kEUR每MW）、EFC、物理电量、逐市场数据覆盖。2026年不外推全年。',
             '- market_totals.csv、monthly_market_shares.csv：带符号金额及占比。',
             '- hourly.csv、quarterly_hourly.csv、monthly_hourly_heatmap.csv：小时均值和实际样本数；DST分别处理。',
             '- rolling_12m.csv：9个滚动12自然月窗口。SVG共9张，PNG为对应预览。',
             '- report_manifest.json：生成脚本/原始执行文件/完整验证/参考ES版本哈希和报告环境。核心run_v1保留QH、相位、订单、窗口指标、年度预算和不可变事务链。','',
             '**F（事实）**：OPCOM/DAMAS/BNR官方来源及价格/数量/空值证据见输入数据包source_registry。','',
             '**I（解释）**：本报告按Bucharest交付日归集已执行现金；数据缺口、执行完整性与市场参与量分列。','',
             f'**A（假设）**：已确认代理字段、名义时表、资格/单元、p={p:.0%}、三相及FCR静态机会价值仍是研究假设。p仅折减容量现金，不折减物理预留或激活义务。API最终结算语义、真实项目资格、实际历史信息可见性和FCR频率轨迹未因本次计算而得到确认。','',
             f'格式参照[ES_MILP固定提交的报告生成代码](https://github.com/hutianyi326/ES_MILP/blob/{PIN}/code/project/build_es_result_presentation.py)，并将ES的ID分项替换为RO的FCR容量分项。只参考展示结构，不导入西班牙市场规则、预算或测算结果。']
    (out/'结果展示.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    # A self-contained visual inspection contact sheet, not a substitute for CSV checks.
    images=[]
    for p in sorted(out.glob('*.png')):
        im=Image.open(p).convert('RGB');im.thumbnail((700,430));tile=Image.new('RGB',(720,470),'white');tile.paste(im,((720-im.width)//2,25));ImageDraw.Draw(tile).text((10,445),p.stem,fill='black');images.append(tile)
    sheet=Image.new('RGB',(1440,470*((len(images)+1)//2)),'#eceff3')
    for i,im in enumerate(images):sheet.paste(im,((i%2)*720,(i//2)*470))
    sheet.save(out/'visual_check.png')
    proof={'report_version':'RO 1.0 / ES presentation baseline v1 adapted','created_utc':datetime.now(timezone.utc).isoformat(),'run_dir':str(run_dir),'input_sha256':manifest['identity']['input_sha256'],'code_sha256':manifest['identity']['code_sha256'],'report_script_sha256':sha(__file__),'reference_commit':PIN,'reference_files':{p.name:sha(p) for p in (HERE.parent/'romania_full_run_20261002/es_reference').glob('*.py')},'run_manifest_sha256':sha(run_dir/'manifest.json'),'full_validation_sha256':sha(validation),'run_files':{p.name:sha(p) for p in [run_dir/'executed_qh.csv',run_dir/'executed_phases.csv',run_dir/'summary.json',run_dir/'window_metrics.csv']},'last_transaction_sha256':audit['last_transaction_sha256'],'config':cfg,'formal_start':manifest['identity']['start'],'formal_end':manifest['identity']['end'],'total_eur':float(total),'total_efc':float(efc),'cash_coverage':1.,'market_data_coverage':summary['data_coverage'],'solver_seconds':solvertime,'solver_status_counts':{str(k):int(v) for k,v in status.items()},'max_objective_gap':float(metrics.objective_gap.max()),'runtime':{'python':sys.version,'pandas':pd.__version__,'matplotlib':matplotlib.__version__},'files':{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}}
    (out/'report_manifest.json').write_text(json.dumps(proof,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':'BUILT','total_eur':float(total),'total_efc':float(efc),'latest_12m_kEUR_per_MW':float(latest.total_kEUR_per_MW),'monthly_rows':len(monthly),'actual_hours':len(actual),'svg_count':len(list(out.glob('*.svg'))),'output':str(out)},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--validation',type=Path,required=True);a=p.parse_args();build(a.run,a.output,a.validation)
