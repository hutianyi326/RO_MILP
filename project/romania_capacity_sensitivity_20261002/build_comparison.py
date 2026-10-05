"""Combine three independently optimized, audited scenarios; ES-style summary tables."""
from pathlib import Path
import argparse,json,hashlib,copy,sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image,ImageDraw
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
MARKETS=('DA','FCR_cap','cap_up','cap_down','act_up','act_down')
LABELS=dict(zip(MARKETS,('DA电能','FCR容量','aFRR容量上调','aFRR容量下调','aFRR激活上调','aFRR激活下调')))
COLORS=('#4472C4','#ED7D31','#70AD47','#A5A5A5','#FFC000','#8064A2')
SCENARIO_COLORS={100:'#2457A7',80:'#D48812',60:'#5E4A9B'}
CASH=dict(zip(MARKETS,('da_eur','fcr_capacity_eur','afrr_up_capacity_eur','afrr_down_capacity_eur','afrr_up_activation_eur','afrr_down_activation_eur')))
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fmt(x,digits=2):return f'{x:,.{digits}f}'
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'---|'*len(headers)]+['| '+' | '.join(map(str,r))+' |' for r in rows])
def save(frame,p):frame.to_csv(p,index=False,encoding='utf-8-sig',float_format='%.12g')

def build(base,outroot,destination):
    destination.mkdir(parents=True,exist_ok=False)
    locations={p:(outroot/f'p{p}_run',outroot/f'p{p}_report',outroot/f'p{p}_validation.json',outroot/f'p{p}_presentation_validation.json') for p in (100,80,60)}
    scenarios={};reference_identity=None;mask_reference=None;provenance={}
    for percent,(run,report,validation,pvalidation) in locations.items():
        manifest=read(run/'manifest.json');summary=read(run/'summary.json');check=read(validation);pcheck=read(pvalidation);report_manifest=read(report/'report_manifest.json')
        assert summary['status']=='COMPLETE' and check['status']==pcheck['status']=='PASS'
        assert check['run_manifest_sha256']==sha(run/'manifest.json') and pcheck['report_manifest_sha256']==sha(report/'report_manifest.json')
        assert report_manifest['run_manifest_sha256']==sha(run/'manifest.json')
        for name,h in report_manifest['files'].items():assert sha(report/name)==h
        identity=copy.deepcopy(manifest['identity']);cfg=identity['config']
        for field in ('p_up','p_down','p_fcr'):assert cfg.pop(field)==percent/100
        if reference_identity is None:reference_identity=identity
        else:assert identity==reference_identity,'Only capacity coefficients may differ'
        q=pd.read_csv(run/'executed_qh.csv');mask=q[['delivery_start_utc','delivery_end_utc','local_date','da_data_valid','afrr_hour_data_valid','fcr_hour_data_valid','initial_no_prior_commitment']]
        if mask_reference is None:mask_reference=mask
        else:assert mask.equals(mask_reference),'Scenario coverage differs'
        assert len(q)==58364 and summary['windows']==608 and abs(summary['end_soc_mwh']-10)<1e-6
        yearly=pd.read_csv(report/'annual.csv');monthly=pd.read_csv(report/'monthly.csv');rolling=pd.read_csv(report/'rolling_12m.csv');metrics=pd.read_csv(run/'window_metrics.csv')
        scenarios[percent]=dict(run=run,report=report,summary=summary,q=q,annual=yearly,monthly=monthly,rolling=rolling,metrics=metrics)
        provenance[str(percent)]={'run_manifest_sha256':sha(run/'manifest.json'),'report_manifest_sha256':sha(report/'report_manifest.json'),'full_validation_sha256':sha(validation),'presentation_validation_sha256':sha(pvalidation),'last_transaction_sha256':check['last_transaction_sha256'],'source_dir':str(run.resolve()),'report_dir':str(report.resolve())}
    baseline=scenarios[100]['summary']['total_eur'];baseline_cap=sum(scenarios[100]['summary']['cash_eur'][CASH[m]] for m in ('FCR_cap','cap_up','cap_down'))
    summaries=[];annual_all=[];month_all=[];rolling_all=[];market_all=[];efc_all=[];hourly_all=[]
    for percent,s in scenarios.items():
        q=s['q'];sm=s['summary'];revenue=sm['total_eur'];p=percent/100
        pure=baseline+(p-1)*baseline_cap
        r=dict(scenario=f'p{percent}',capacity_income_coefficient=p,total_eur=revenue,total_kEUR_per_MW=revenue/100000,delta_eur_vs_p100=revenue-baseline,change_pct_vs_p100=(revenue/baseline-1)*100,total_efc=q.efc.sum(),efc_2025=float(s['annual'].set_index('year').loc[2025,'efc']),efc_2026=float(s['annual'].set_index('year').loc[2026,'efc']),latest_12m_kEUR_per_MW=s['rolling'].iloc[-1].total_kEUR_per_MW,average_da_mw=q.da_mw.mean(),average_fcr_mw=q.fcr_mw.mean(),average_afrr_up_mw=q.afrr_up_mw.mean(),average_afrr_down_mw=q.afrr_down_mw.mean(),afrr_up_activation_mwh=q.afrr_up_activation_mwh.sum(),afrr_down_activation_mwh=q.afrr_down_activation_mwh.sum(),p100_trajectory_capacity_repricing_eur=pure,reoptimization_and_rolling_effect_eur=revenue-pure,windows=608,executed_qh=len(q),terminal_soc_mwh=sm['end_soc_mwh'],status0_windows=int((s['metrics'].status==0).sum()),status1_windows=int((s['metrics'].status==1).sum()),max_objective_gap=s['metrics'].objective_gap.max())
        for m in MARKETS:r[CASH[m]]=sm['cash_eur'][CASH[m]]
        r['capacity_cash_eur']=sum(r[CASH[m]] for m in ('FCR_cap','cap_up','cap_down'));r['da_and_activation_cash_eur']=revenue-r['capacity_cash_eur'];summaries.append(r)
        for collection,source in [(annual_all,s['annual']),(month_all,s['monthly']),(rolling_all,s['rolling']),(hourly_all,pd.read_csv(s['report']/'hourly.csv'))]:
            temp=source.copy();temp.insert(0,'scenario',f'p{percent}');collection.append(temp)
        for m in MARKETS:market_all.append(dict(scenario=f'p{percent}',market=m,label=LABELS[m],cash_eur=sm['cash_eur'][CASH[m]],kEUR_per_MW=sm['cash_eur'][CASH[m]]/100000,delta_eur_vs_p100=sm['cash_eur'][CASH[m]]-scenarios[100]['summary']['cash_eur'][CASH[m]]))
    summary=pd.DataFrame(summaries);annual=pd.concat(annual_all,ignore_index=True);monthly=pd.concat(month_all,ignore_index=True);rolling=pd.concat(rolling_all,ignore_index=True);markets=pd.DataFrame(market_all);hourly=pd.concat(hourly_all,ignore_index=True)
    for name,frame in [('scenario_summary',summary),('annual_comparison',annual),('monthly_comparison',monthly),('rolling_12m_comparison',rolling),('market_comparison',markets),('hourly_comparison',hourly)]:save(frame,destination/(name+'.csv'))
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'svg.fonttype':'none','font.size':10})
    def savefig(fig,name):
        fig.tight_layout();fig.savefig(destination/(name+'.svg'),bbox_inches='tight');fig.savefig(destination/(name+'.png'),dpi=140,bbox_inches='tight');plt.close(fig)
    for data,x,y,title,filename in [(monthly,'month','total_kEUR_per_MW','月度条件毛现金 · 三个独立优化情景','monthly_comparison'),(rolling,'month','total_kEUR_per_MW','滚动12个自然月 · 三个独立优化情景','rolling_12m_comparison'),(hourly,'hour','total_kEUR_per_MW','全期当地钟点平均现金 · 每个实际小时','hourly_comparison')]:
        fig,ax=plt.subplots(figsize=(14,5))
        for percent in scenarios:
            g=data[data.scenario==f'p{percent}'];ax.plot(g[x],g[y],'-o',markersize=3,label=f'p={percent}%',color=SCENARIO_COLORS[percent])
        ax.set_title(title,loc='left',fontweight='bold');ax.set_ylabel('kEUR/MW');ax.axhline(0,color='#777',linewidth=.6);ax.grid(axis='y',alpha=.2);ax.legend(frameon=False)
        if x=='month':ax.tick_params(axis='x',rotation=45)
        savefig(fig,filename)
    fig,ax=plt.subplots(figsize=(11,5.8));x=np.arange(3);pos=np.zeros(3);neg=np.zeros(3)
    for m,color in zip(MARKETS,COLORS):
        v=summary[CASH[m]].to_numpy()/1e6;bottom=np.where(v>=0,pos,neg);ax.bar(x,v,bottom=bottom,color=color,label=LABELS[m],width=.55);pos+=np.maximum(v,0);neg+=np.minimum(v,0)
    for i,value in enumerate(summary.total_eur/1e6):ax.text(i,pos[i]+1.2,fmt(value),ha='center',fontweight='bold')
    ax.set_xticks(x,['100%','80%','60%']);ax.set_xlabel('三产品共同容量收入系数');ax.set_ylabel('百万EUR');ax.set_title('全期六项现金构成 · 100MW/200MWh',loc='left',fontweight='bold');ax.set_ylim(top=pos.max()*1.15);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.legend(ncol=3,loc='upper center',bbox_to_anchor=(.5,-.16),frameon=False);savefig(fig,'market_cash_comparison')
    fig,ax=plt.subplots(figsize=(10,5));x=np.arange(2)
    for i,percent in enumerate(scenarios):
        vals=annual[annual.scenario==f'p{percent}'].sort_values('year').efc.to_numpy();ax.bar(x+(i-1)*.24,vals,width=.22,color=SCENARIO_COLORS[percent],label=f'p={percent}%')
    ax.plot(x,[600,399.452054795],'k_',markersize=75,label='固定预算');ax.set_xticks(x,['2025全年','2026年1—8月']);ax.set_ylabel('EFC');ax.set_title('年度EFC · 各情景预算相同',loc='left',fontweight='bold');ax.legend(frameon=False,ncol=4);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);savefig(fig,'annual_efc_comparison')
    report=['# 罗马尼亚100MW/200MWh：容量收入系数100% / 80% / 60%敏感性','',
        '正式期2025-01-01至2026-08-31，共608个Bucharest当地日。三个情景均按同一数值求解修复后的代码从头独立优化，各完成608窗/58,364QH。此前100%和80%完成结果保留并核对，不混用不同版本生成最终比较。','',
        '**p含义：** 同时作用于aFRR上调容量、下调容量和FCR容量三项现金，是外生研究系数，不是实测中标率。不直接折减DA或激活现金，也不削减备用功率、SOC缓冲及激活义务。它不是“总收益乘80%或60%”。','',
        '## 三情景汇总','',table(['容量系数','全期现金（百万EUR）','kEUR/MW','较100%变化','全期EFC','最新12月kEUR/MW'],[[f'{r.capacity_income_coefficient:.0%}',fmt(r.total_eur/1e6),fmt(r.total_kEUR_per_MW),fmt(r.change_pct_vs_p100)+'%',fmt(r.total_efc),fmt(r.latest_12m_kEUR_per_MW)] for _,r in summary.iterrows()]),'',
        '最新完整12个月均为2025-09至2026-08；2026自然年列仅含1—8月，不年化。所有现金均为EUR条件毛现金，未扣投资、运维、税费等成本。','',
        '![六项现金对比](market_cash_comparison.svg)','',
        '## 自然年现金与EFC','',table(['情景','期间','现金（百万EUR）','kEUR/MW','EFC','预算使用率'],[[r.scenario,('2025全年' if r.year==2025 else '2026年1—8月'),fmt(r.total_kEUR/1000),fmt(r.total_kEUR_per_MW),fmt(r.efc),fmt(r.budget_utilization*100)+'%'] for _,r in annual.iterrows()]),'',
        '![年度EFC](annual_efc_comparison.svg)','',
        '## 六项市场现金','',table(['市场','100%（百万EUR）','80%（百万EUR）','60%（百万EUR）'],[[LABELS[m]]+[fmt(scenarios[p]['summary']['cash_eur'][CASH[m]]/1e6) for p in scenarios] for m in MARKETS]),'',
        '负现金与原价格符号保留；容量项减价后，最优预留与DA/aFRR激活电量可以变化，故激活现金也可能改变。','',
        '## 调度与敏感性解释','',table(['指标','100%','80%','60%'],[[label]+[fmt(summary.set_index('scenario').loc[f'p{p}',field]) for p in scenarios] for field,label in [('average_da_mw','DA平均净MW'),('average_fcr_mw','FCR平均预留MW'),('average_afrr_up_mw','aFRR上调平均预留MW'),('average_afrr_down_mw','aFRR下调平均预留MW'),('afrr_up_activation_mwh','aFRR上调激活MWh'),('afrr_down_activation_mwh','aFRR下调激活MWh')]]),'',
        '平均MW分母为全部正式QH，包含首日零承诺和源失效禁用订单；不是仅参与时段的平均值。容量均值不能相加作为电站容量分配比例。','',
        '为区分价格系数与重新调度的影响，另计算固定100%轨迹只调整三项容量现金的算术参照；这不是另一个MILP运行，不替代上表独立重优化主结果。','',
        table(['情景','固定100%轨迹重计价（百万EUR）','实际重优化（百万EUR）','差额（百万EUR）'],[[r.scenario,fmt(r.p100_trajectory_capacity_repricing_eur/1e6),fmt(r.total_eur/1e6),fmt(r.reoptimization_and_rolling_effect_eur/1e6)] for _,r in summary.iterrows()]),'',
        '上述差额包含调度变化和两日滚动路径效应，不宣称是全时域优化增益，也不保证在所有其他情景中非负。','',
        '## 月度现金','', '![月度对比](monthly_comparison.svg)','',table(['月份','100% kEUR/MW','80% kEUR/MW','60% kEUR/MW'],[[mo]+[fmt(scenarios[p]['monthly'].set_index('month').loc[mo,'total_kEUR_per_MW']) for p in scenarios] for mo in scenarios[100]['monthly'].month]),'',
        '## 滚动12个月','', '![滚动12个月对比](rolling_12m_comparison.svg)','',table(['窗口终月','100% kEUR/MW','80% kEUR/MW','60% kEUR/MW'],[[mo]+[fmt(scenarios[p]['rolling'].set_index('month').loc[mo,'total_kEUR_per_MW']) for p in scenarios] for mo in scenarios[100]['rolling'].month]),'',
        '## 小时曲线','', '先合计每个实际小时的四个QH，再按当地钟点平均；每情景14,591个小时。秋季重复小时单独计样本。','', '![小时对比](hourly_comparison.svg)','',
        '## 同口径与验证','',
        '- 已逐项确认：除p_up/p_down/p_fcr外，三情景配置、输入/代码身份、正式期和年度预算一致；逐QH网格及市场有效性标记完全一致。',
        '- 每情景首末SOC10MWh，年度预算600/399.452054795；观察日不计正式现金和执行EFC。',
        '- 60%初次及v2在额度耗尽附近发生数值阻断。最终v3将内部保守余量改为g=min(1e-6,A/2)，A为扣除既定终端留存后的经济余额，窗口上限A−g仍不超经济预算。它是数值政策修订，不是原矩阵等价变换。HiGHS可行性精度收紧至1e-8；status2仍可在剩余时限内关闭presolve重试。SOC、冻结订单和原审计容差不变。',
        '- 全期自动独立回放现金、SOC、EFC、冻结、FCR缓冲、两日目标及年度资源约束；展示聚合另独立验证。reviewer结论见任务审核记录。','',
        table(['情景','成功窗口status0','限时可行窗口status1','最大目标尺度gap'],[[r.scenario,str(int(r.status0_windows)),str(int(r.status1_windows)),f'{r.max_objective_gap:.8g}'] for _,r in summary.iterrows()]),'',
        'status0是满足所设1e-4容许gap的单窗求解成功，不等于精确零gap或完整时域最优。','',
        '## 文件与边界','',
        '- scenario_summary.csv：总现金、变化、EFC、平均预留和重计价参照。market_comparison.csv：六项分解。',
        '- annual_comparison.csv、monthly_comparison.csv、rolling_12m_comparison.csv、hourly_comparison.csv：按情景并列完整明细。',
        '- 三组独立ES格式报告在上级p100_report、p80_report、p60_report，各含月/年/日、季度、热图等9张图；位置与来源由comparison_manifest.json记录。','',
        '**来源事实**：沿用OPCOM、Transelectrica/DAMAS、BNR的已审EUR数据，未新增来源或覆盖数据缺口。','',
        '**研究解释**：收入系数变化引发市场间调度替代，比较同时呈现容量、DA、激活与EFC变化。','',
        '**建模假设**：p、代理价格、名义时表、资格/研究单元、三相、FCR静态0.5h缓冲均沿用基线。FCR只计容量机会价值，未模拟频率激活损耗及额外循环。真实结算、历史信息可见性和项目资格限制仍未关闭。输出不是实际可执行净利润。']
    (destination/'三情景敏感性汇总.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    images=[]
    for path in sorted(destination.glob('*.png')):
        im=Image.open(path).convert('RGB');im.thumbnail((700,440));tile=Image.new('RGB',(720,480),'white');tile.paste(im,((720-im.width)//2,10));ImageDraw.Draw(tile).text((10,455),path.stem,fill='black');images.append(tile)
    sheet=Image.new('RGB',(1440,480*((len(images)+1)//2)),'#eceff3')
    for i,im in enumerate(images):sheet.paste(im,((i%2)*720,(i//2)*480))
    sheet.save(destination/'visual_check.png')
    previous={100:base/'run_v1',80:outroot.parent/'p80_run'}
    old_comparison={str(p):{'previous_total_eur':read(path/'summary.json')['total_eur'],'current_total_eur':scenarios[p]['summary']['total_eur'],'difference_eur':scenarios[p]['summary']['total_eur']-read(path/'summary.json')['total_eur']} for p,path in previous.items()}
    proof={'status':'BUILT_AWAITING_INDEPENDENT_REVIEW','common_identity_excluding_p':reference_identity,'scenarios':provenance,'previous_completed_run_comparison':old_comparison,'comparison_script_sha256':sha(__file__),'files':{p.name:sha(p) for p in sorted(destination.iterdir()) if p.is_file()},'equality_checks':['config_except_three_p','input_identity','solver_code_identity','formal_dates','annual_budgets','qh_time_grid','market_data_validity'],'scenario_summary':summary.to_dict(orient='records')}
    (destination/'comparison_manifest.json').write_text(json.dumps(proof,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(summary[['scenario','total_eur','change_pct_vs_p100','total_efc']].to_string(index=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();build(a.base,a.root,a.output)
