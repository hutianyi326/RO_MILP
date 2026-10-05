"""Independent Decimal reconstruction of one persisted random sample; no solver imports."""
import csv,json,hashlib
from pathlib import Path
from collections import defaultdict,Counter
from datetime import datetime,timedelta
from decimal import Decimal as D,getcontext
from zoneinfo import ZoneInfo
getcontext().prec=34
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/random_day_audit_p100_20261003'
RUN=ROOT/'outputs/capacity_sensitivity_100mw_200mwh_20261002/v3/p100_run'
DATA=ROOT/'data/processed/RO/prices_eur_v1_20261002'
RO=ZoneInfo('Europe/Bucharest');H=D('.25');ETA=D('.92')
CASH=('da_eur','fcr_capacity_eur','afrr_up_capacity_eur','afrr_down_capacity_eur','afrr_up_activation_eur','afrr_down_activation_eur')
LABELS=('DA电能','FCR容量','aFRR上调容量','aFRR下调容量','aFRR上调激活','aFRR下调激活')
FIELDS=('da_price_eur_per_mwh','fcr_capacity_price_eur_per_mw_h_proxy','afrr_up_capacity_price_eur_per_mw_h_proxy','afrr_down_capacity_price_eur_per_mw_h_proxy','afrr_up_activation_price_eur_per_mwh_proxy','afrr_down_activation_price_eur_per_mwh_proxy')
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canon(o):return json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def dt(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def local(s):return dt(s).astimezone(RO).isoformat()
def num(v):return None if v in (None,'') else D(str(v))
def truth(v):return str(v).lower()=='true'
def write_json(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8')
def write_csv(name,data):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
def fmt(v,n=6):return '缺失' if v is None else f'{D(str(v)):,.{n}f}'
def table(headers,rs):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'---|'*len(headers)]+['| '+' | '.join(map(str,r))+' |' for r in rs])

def build():
    selection=read(OUT/'selection.json');i=selection['sequence'];day=selection['local_date']
    manifest=read(RUN/'manifest.json');ident=manifest['identity'];cfg=ident['config']
    assert sha(RUN/'manifest.json')==selection['run_manifest_sha256']
    assert cfg['power_mw']==100 and cfg['hours']==2 and cfg['p_up']==cfg['p_down']==cfg['p_fcr']==1 and not cfg['daily_p']
    parent=hashlib.sha256(canon(manifest).encode()).hexdigest();state=manifest['initial_state'];chain_count=0
    for j in range(i+1):
        path=RUN/f'windows/{j:04d}.json';tx=read(path);signature=tx['sha256'];payload={k:v for k,v in tx.items() if k!='sha256'}
        assert hashlib.sha256(canon(payload).encode()).hexdigest()==signature
        assert tx['previous_sha256']==parent and tx['start']==state['next_start']
        assert tx['identity_hash']==hashlib.sha256(canon(ident).encode()).hexdigest()
        parent=signature;chain_count+=1
        if j==i:opening=state
        state=tx['next_state']
    assert tx['sha256']==selection['transaction_sha256']
    prev=read(RUN/f'windows/{i-1:04d}.json') if i else None
    next_tx=read(RUN/f'windows/{i+1:04d}.json')
    start=dt(tx['start']);end=start+timedelta(days=2)
    assert start.astimezone(RO).date().isoformat()==day
    release=read(DATA/'manifest.json');source=DATA/'prices_eur_qh_20250101_20260831.csv'
    entry=next(e for e in release['files'] if Path(e['path']).name==source.name)
    assert sha(source)==entry['sha256']
    with source.open(encoding='utf-8-sig',newline='') as f:
        raw=[r for r in csv.DictReader(f) if start<=dt(r['delivery_start_utc'])<end]
    assert len(raw)==192 and all(r['price_currency']=='EUR' for r in raw)
    assert all(dt(r['delivery_start_utc'])==start+timedelta(minutes=15*j) for j,r in enumerate(raw))
    write_csv('inputs_two_days.csv',raw)
    write_json('opening_state.json',opening)
    if prev:write_csv('previous_day_executed_qh.csv',prev['executed_qh'])
    orders=dict(opening['frozen']);orders.update(tx['new_orders']);orders.update(tx['initial_orders'])
    expected={'DA|'+r['da_contract_id'] for r in raw}|{p+'|'+r['capacity_hour_start_utc'] for r in raw for p in ('u','d','F')}
    assert set(orders)==expected
    native=[]
    for key,o in sorted(orders.items(),key=lambda kv:(kv[1]['start'],kv[1]['product'])):
        origin='前日冻结' if key in opening['frozen'] else '当日新增'
        assert (dt(o['gate'])<start)==(origin=='前日冻结')
        native.append(dict(key=key,product=o['product'],delivery_start_local=local(o['start']),delivery_end_local=local(o['end']),gate_local=local(o['gate']),result_local=local(o['result']),origin=origin,decision_sequence=i-1 if origin=='前日冻结' else i,amount_mw=o['amount_mw'],fcr_units_mw=json.dumps(o.get('units_mw',[])),reason=o['reason']))
    write_csv('native_orders_two_days.csv',native)
    hourly=defaultdict(list)
    for r in raw:hourly[r['capacity_hour_start_utc']].append(r)
    valid_a={};valid_f={}
    for h,rs in hourly.items():
        def afrr_valid(r):
            vals=[num(r[k]) for k in FIELDS[2:]]+[num(r[k]) for k in ('afrr_up_accepted_capacity_mw','afrr_down_accepted_capacity_mw','afrr_up_system_activation_energy_mwh','afrr_down_system_activation_energy_mwh')]
            if any(v is None for v in vals) or min(vals[4:6])<=0:return False
            au=vals[6]/(vals[4]*H);ad=vals[7]/(vals[5]*H)
            return min(au,ad)>=0 and au+ad<=1
        valid_a[h]=all(afrr_valid(r) for r in rs)
        valid_f[h]=all(num(r[FIELDS[1]]) is not None and num(r['fcr_accepted_capacity_mw']) is not None and num(r['fcr_accepted_capacity_mw'])>0 for r in rs)
        assert all(truth(r['afrr_hour_data_valid'])==valid_a[h] and truth(r['fcr_hour_data_valid'])==valid_f[h] for r in rs)
    E=num(opening['soc_mwh']);checks=Counter();errors=defaultdict(lambda:D(0));phases=[];plan=[]
    def near(a,b,kind='physical'):
        diff=abs(num(a)-num(b));tol=D('.000001') if kind=='physical' else D('.0000001') if kind=='efc' else D('.00001')+D('1e-9')*max(abs(num(a)),abs(num(b)))
        assert diff<=tol,(kind,a,b,diff);errors[kind]=max(errors[kind],diff);checks[kind]+=1
    def bounded(v,lo,hi):assert lo-D('.000001')<=v<=hi+D('.000001')
    saved={r['delivery_start_utc']:r for r in tx['executed_qh']+next_tx['executed_qh']}
    saved_phases={(r['start'],r['phase']):r for r in tx['executed_phases']+next_tx['executed_phases']}
    for r in raw:
        t=r['delivery_start_utc'];h=r['capacity_hour_start_utc'];B=num(orders['DA|'+r['da_contract_id']]['amount_mw'])
        U,V,F=(num(orders[p+'|'+h]['amount_mw']) for p in ('u','d','F'))
        if not valid_a[h]:assert U==V==0
        if not valid_f[h]:assert F==0
        for p,v,source_col in [('u',U,'afrr_up_accepted_capacity_mw'),('d',V,'afrr_down_accepted_capacity_mw'),('F',F,'fcr_accepted_capacity_mw')]:
            assert v==v.to_integral_value() and 0<=v<=100
            if v:assert v<=int(min(num(rr[source_col]) for rr in hourly[h]))
        assert U+F<=100 and V+F<=100;bounded(B+U+F,D(-100),D(100));bounded(B-V-F,D(-100),D(100))
        units=orders['F|'+h]['units_mw'];assert len(units)==5 and sum(units)==F and all(0<=v<=20 and int(v)==v for v in units)
        au=num(r['afrr_up_system_activation_energy_mwh'])/(num(r['afrr_up_accepted_capacity_mw'])*H) if valid_a[h] else D(0)
        ad=num(r['afrr_down_system_activation_energy_mwh'])/(num(r['afrr_down_accepted_capacity_mw'])*H) if valid_a[h] else D(0)
        sequence=[('d',H*ad,B-V),('u',H*au,B+U),('0',H*(1-au-ad),B)] if valid_a[h] else [('NO_AFRR_OBLIGATION',H,B)]
        ein=E;efc=D(0);charge=D(0);discharge=D(0)
        for name,duration,Y in sequence:
            if duration==0:continue
            C=max(-Y,D(0));O=max(Y,D(0));before=E;E+=duration*(ETA*C-O/ETA)
            increment=duration*(ETA*C+O/ETA)/360;efc+=increment;charge+=duration*C;discharge+=duration*O
            bounded(Y-F,D(-100),D(100));bounded(Y+F,D(-100),D(100))
            for e in (before,E):bounded(e,D(10)+F*D('.5')/ETA,D(190)-F*D('.5')*ETA)
            ph=dict(start=t,local_time=local(t),phase=name,hours=duration,minutes=duration*60,Y=Y,C=C,D=O,ein=before,eout=E,efc=increment)
            original=saved_phases[(t,name)]
            for field in ('hours','Y','C','D','ein','eout','efc'):near(ph[field],original[field],'efc' if field=='efc' else 'physical')
            phases.append(ph)
        EU=U*H*au;ED=V*H*ad
        prices=[num(r[k]) for k in FIELDS]
        quantities=(B*H,F*H,U*H,V*H,EU,-ED)
        cash={k:q*p if q else D(0) for k,q,p in zip(CASH,quantities,prices)}
        row=dict(delivery_start_utc=t,local_time=local(t),role='D执行/前日冻结' if r['local_date']==day else 'D+1规划/当日新增',da_mw=B,fcr_mw=F,afrr_up_mw=U,afrr_down_mw=V,alpha_up=au,alpha_down=ad,alpha_idle=1-au-ad,afrr_hour_valid=valid_a[h],fcr_hour_valid=valid_f[h],afrr_up_activation_mwh=EU,afrr_down_activation_mwh=ED,da_signed_mwh=B*H,ac_charge_mwh=charge,ac_discharge_mwh=discharge,ein_mwh=ein,eout_mwh=E,efc=efc,**cash,total_eur=sum(cash.values()))
        original=saved[t]
        for field in ('da_mw','fcr_mw','afrr_up_mw','afrr_down_mw','afrr_up_activation_mwh','afrr_down_activation_mwh','ein_mwh','eout_mwh','efc',*CASH,'total_eur'):
            near(row[field],original[field],'cash' if field in (*CASH,'total_eur') else 'efc' if field=='efc' else 'physical')
        plan.append(row)
    executed=plan[:96];totals={c:sum(r[c] for r in executed) for c in CASH};total=sum(totals.values())
    near(executed[-1]['eout_mwh'],tx['next_state']['soc_mwh'])
    used=num(opening['used_efc']['2025']);day_efc=sum(r['efc'] for r in executed)
    near(used+day_efc,tx['next_state']['used_efc']['2025'],'efc')
    A=num(ident['budgets']['2025'])-used;guard=min(D('.000001'),A/2);allow=A-guard
    assert sum(r['efc'] for r in plan)<=allow+D('.0000001')
    meanprice=sum(num(r[FIELDS[0]]) for r in raw[96:])/96;salvage_rate=ETA*max(meanprice,D(0));salvage=salvage_rate*(E-10)
    plan_cash=sum(r['total_eur'] for r in plan)
    near(plan_cash,tx['metrics']['plan_cash_eur'],'cash');near(salvage,tx['metrics']['salvage_eur'],'cash');near(plan_cash+salvage,tx['metrics']['incumbent_eur'],'cash')
    write_csv('plan_two_days_qh.csv',plan);write_csv('phase_replay_two_days.csv',phases)
    detail=[{**raw[j],**executed[j]} for j in range(96)]
    write_csv('executed_day_cash_calculation.csv',detail)
    hrs=[]
    for hh in range(24):
        rs=executed[hh*4:hh*4+4]
        hrs.append(dict(hour=f'{hh:02d}:00',fcr_mw=rs[0]['fcr_mw'],afrr_up_mw=rs[0]['afrr_up_mw'],afrr_down_mw=rs[0]['afrr_down_mw'],da_signed_mwh=sum(r['da_signed_mwh'] for r in rs),afrr_up_activation_mwh=sum(r['afrr_up_activation_mwh'] for r in rs),afrr_down_activation_mwh=sum(r['afrr_down_activation_mwh'] for r in rs),ein_mwh=rs[0]['ein_mwh'],eout_mwh=rs[-1]['eout_mwh'],**{c:sum(r[c] for r in rs) for c in CASH},total_eur=sum(r['total_eur'] for r in rs)))
    write_csv('hourly_execution_and_cash.csv',hrs)
    keys={r[k] for r in raw for k in r if k.endswith('source_key') and r[k]}
    with (DATA/'source_registry.csv').open(encoding='utf-8-sig',newline='') as f:sources=[r for r in csv.DictReader(f) if r['source_key'] in keys]
    assert {r['source_key'] for r in sources}==keys
    write_csv('source_registry_selected.csv',sources)
    example_index=max(range(96),key=lambda j:(sum(executed[j][k]>0 for k in ('fcr_mw','afrr_up_mw','afrr_down_mw')),executed[j]['da_mw']!=0,executed[j]['afrr_up_activation_mwh']>0 and executed[j]['afrr_down_activation_mwh']>0))
    ex=executed[example_index];inp=raw[example_index];exph=[r for r in phases if r['start']==ex['delivery_start_utc']]
    moneyrows=[[label,fmt(totals[c],8)] for label,c in zip(LABELS,CASH)]+[['合计',fmt(total,8)]]
    report=[f'# 100%情景随机单日独立审计：{day}','',
        f'从原608个正式日均匀随机抽取一次，选中序号{i}（从0计数），未按收益或市场有效性筛选，未重抽。抽样记录见[selection.json](selection.json)。审计对象为已通过审核的v3/p100账本；本报告从原订单及EUR输入独立重算，没有重新优化或替换原调度。主线程新增本审计项目/输出目录获本次任务范围授权，原始数据、求解器及原结果不修改。','',
        '**核心时间关系：11月25日优化了11月25—26日，其中26日订单在25日提交并冻结；11月26日优化26—27日，26日订单作为常量，新增决策是27日订单。** 因而“当天收入”不能把27日计划收入或两日目标中的期末残值加进去。','',
        '## 1. 输入和结转状态','',
        table(['输入','数值/含义'],[
            ['项目','100MW / 200MWh（直流名义）；SOC10—190MWh；单向效率92%'],
            ['容量现金系数','FCR、aFRR上/下均100%；不缩减物理预留或激活义务'],
            ['当地时区','Europe/Bucharest；本样本两天均UTC+02:00，每天96个15分钟时段'],
            ['前一日11月25日00:00 SOC',fmt(prev['executed_qh'][0]['ein_mwh'])+' MWh'],
            ['前一日结束=11月26日00:00 SOC',fmt(opening['soc_mwh'],12)+' MWh；名义SOC '+fmt(num(opening['soc_mwh'])/200*100,8)+'%'],
            ['年内已执行EFC（截至前日）',fmt(used,12)],['2025年度预算',fmt(ident['budgets']['2025'],12)],
            ['本窗2025剩余额度/内部guard/允许额度',f'{fmt(A,12)} / {fmt(guard,12)} / {fmt(allow,12)} EFC；2025无正式终端留存'],
            ['两日输入网格',f'{local(raw[0]["delivery_start_utc"])} 至 {local(raw[-1]["delivery_end_utc"])}（右端不含）；192QH'],
            ['传入冻结订单数',len(opening['frozen'])],['本窗新增订单数',len(tx['new_orders'])],
            ['有效aFRR小时 D / D+1',f'{sum(valid_a[r["capacity_hour_start_utc"]] for r in raw[:96])/4:g} / {sum(valid_a[r["capacity_hour_start_utc"]] for r in raw[96:])/4:g}'],
            ['有效FCR小时 D / D+1',f'{sum(valid_f[r["capacity_hour_start_utc"]] for r in raw[:96])/4:g} / {sum(valid_f[r["capacity_hour_start_utc"]] for r in raw[96:])/4:g}']]),'',
        '完整前日96QH见[previous_day_executed_qh.csv](previous_day_executed_qh.csv)，完整传入状态含逐订单冻结量见[opening_state.json](opening_state.json)。价格及市场系统容量/激活电量、汇率日期/数值、字段状态、源键均逐行保留在[inputs_two_days.csv](inputs_two_days.csv)。价格已为EUR，不在本次重复换汇。FCR激活价格不进入该模型，缺失字段不当作零价格。','',
        '## 2. 订单、激活电量与物理执行','',
        'DA的B是带符号净申报功率，正数卖电、负数买电。FCR的F为单次计费的对称备用MW；aFRR的U/V分别是上调/下调备用MW。原生订单表列出当地交付、关闸及结果时间、前日冻结/当日新增、MW和5个FCR研究单元分配：[native_orders_two_days.csv](native_orders_two_days.csv)。这些申报与中标等同的数量是模型假设，不是电站真实成交记录。','',
        '激活电量不是独立的优化申报变量。由系统数据得到 α↑=系统上调激活MWh÷(系统上调中标MW×0.25h)，α↓同理。模型电站激活电量为 E↑=U×α↑×0.25，E↓=V×α↓×0.25。严格有效小时需各QH满足α↑+α↓≤1；否则该整小时aFRR订单为0，不做归一化。','',
        '每QH依次按下调、上调、无激活三相计算净功率Y=B−V、B+U、B，时长为0.25α↓、0.25α↑、0.25(1−α↑−α↓)小时。C=max(−Y,0)，D=max(Y,0)，SOC变化=h×(0.92C−D/0.92)。EFC=h×(0.92C+D/0.92)/360；不能把aFRR激活MWh简单当作电池充放电吞吐，因为还需叠加DA基准。','',
        '每个相位前后检查SOC∈[10+0.5F/0.92,190−0.5F×0.92]，同时检查全部功率边界。FCR只收容量现金，不额外生成激活电量、损耗和EFC。完整192QH结果见[plan_two_days_qh.csv](plan_two_days_qh.csv)，逐相SOC链见[phase_replay_two_days.csv](phase_replay_two_days.csv)。','',
        '## 3. 当天收入逐项计算','',
        '对每个15分钟时段，DA/激活价格单位为EUR/MWh，容量价格单位为EUR/(MW·h)，各项现金单位均为EUR：','',
        '| 市场 | 每QH现金公式（p=1） |\n|---|---|\n| DA | B×0.25×πDA |\n| FCR容量 | F×0.25×πF |\n| aFRR上调容量 | U×0.25×πcap↑ |\n| aFRR下调容量 | V×0.25×πcap↓ |\n| aFRR上调激活 | E↑×πact↑ |\n| aFRR下调激活 | −E↓×πact↓ |','',
        '下调激活使用原价格的负号：原价格为负时，这一项现金为正。DA负功率买电的支出已计入带符号DA现金。FCR对称容量只收一次容量款，不乘2。容量每QH乘0.25h，四个QH合计一小时，不能每QH再收一次整小时价格。','',
        table(['11月26日现金组成','EUR'],moneyrows),'',
        f'当日结束SOC={fmt(executed[-1]["eout_mwh"],12)} MWh；当日EFC={fmt(day_efc,12)}；年度累计={fmt(used+day_efc,12)}。当日aFRR上/下激活电量分别{fmt(sum(r["afrr_up_activation_mwh"] for r in executed),9)} / {fmt(sum(r["afrr_down_activation_mwh"] for r in executed),9)} MWh。','',
        '### 一个15分钟时段的完整代入','',
        f'示例取当日{ex["local_time"]}起的15分钟；仅用于展示公式，日样本没有重新筛选。B={fmt(ex["da_mw"],9)}，F={fmt(ex["fcr_mw"])}, U={fmt(ex["afrr_up_mw"])}, V={fmt(ex["afrr_down_mw"])} MW。',
        f'系统上/下中标容量={inp["afrr_up_accepted_capacity_mw"]}/{inp["afrr_down_accepted_capacity_mw"]} MW；系统上/下激活电量={inp["afrr_up_system_activation_energy_mwh"]}/{inp["afrr_down_system_activation_energy_mwh"]} MWh。',
        f'α↑={fmt(ex["alpha_up"],12)}，α↓={fmt(ex["alpha_down"],12)}；电站E↑={fmt(ex["afrr_up_activation_mwh"],12)}，E↓={fmt(ex["afrr_down_activation_mwh"],12)} MWh。','',
        table(['现金项','带符号数量','输入价格','乘积 EUR'],[[label,fmt(q,12),fmt(num(inp[field]),12),fmt(ex[c],12)] for label,q,field,c in zip(LABELS,(ex['da_signed_mwh'],ex['fcr_mw']*H,ex['afrr_up_mw']*H,ex['afrr_down_mw']*H,ex['afrr_up_activation_mwh'],-ex['afrr_down_activation_mwh']),FIELDS,CASH)]),'',
        f'上表DA/激活数量单位MWh，容量数量单位MW·h；六项相加={fmt(ex["total_eur"],12)} EUR。','',
        table(['相位','时长h','净功率MW','充电MW','放电MW','起SOC MWh','末SOC MWh','EFC'],[[r['phase']]+[fmt(r[k],12) for k in ('hours','Y','C','D','ein','eout','efc')] for r in exph]),'',
        '## 4. 两日优化目标与当天现金的区别','',
        table(['项目','EUR'],[['11月26日实际纳入本回测执行现金',fmt(total,10)],['11月27日计划现金',fmt(plan_cash-total,10)],['两日现金合计',fmt(plan_cash,10)],['窗口末SOC残值（非当日收入）',fmt(salvage,10)],['两日求解目标',fmt(plan_cash+salvage,10)],['原始求解器incumbent',fmt(tx['metrics']['incumbent_eur'],10)],['原始求解器上界',fmt(tx['metrics']['bound_eur'],10)]]),'',
        f'残值单价=0.92×max(11月27日DA均价,0)={fmt(salvage_rate,12)} EUR/MWh，乘(11月27日末SOC {fmt(E,12)}−10)。此窗口906个变量（588连续、72一般整数、246二元），1,765行约束；原始status0，目标尺度gap={tx["metrics"]["objective_gap"]}。只验证保存的解和求解器记录，不把单窗求解证明扩展成608日全局最优。','',
        '## 5. 当日24小时汇总','',
        '每小时F/U/V为该小时恒定备用MW；DA列为四个QH净电量MWh，保留买卖符号。小时内DA功率可不同，逐QH表在后文。','',
        table(['当地小时','F MW','U MW','V MW','DA MWh','激活↑MWh','激活↓MWh','末SOC MWh','现金EUR'],[[r['hour']]+[fmt(r[k],6) for k in ('fcr_mw','afrr_up_mw','afrr_down_mw','da_signed_mwh','afrr_up_activation_mwh','afrr_down_activation_mwh','eout_mwh','total_eur')] for r in hrs]),'',
        '## 6. 来源、验证与边界','',
        f'独立重算使用Python标准库Decimal，从EUR源CSV和冻结/新订单构建，不调用求解器、生产审计或生产输入适配器；验证到抽样日的{chain_count}个事务链、全部192QH现金/相位/功率/预算，且D+1计划与次日原执行账本交叉核对。计算检查结果见[validation.json](validation.json)，独立reviewer结论见[review_and_acceptance.md](review_and_acceptance.md)。',
        '来源事实：OPCOM日前、Transelectrica/DAMAS容量/激活数据、BNR汇率，沿用已审数据包；[本窗口来源清单](source_registry_selected.csv)保留完整URL、原件路径、SHA及获取时间。本轮没有发布新规则结论。',
        '研究解释：按冻结时间线拆分“D日执行”与“D日新申报D+1”，按六项现金逐QH复算。完美信息假设使用两日事后历史价；不证明这些价格当时已发布或可用于真实交易。',
        '建模假设/未解决边界：系统价格代理和激活比例、名义关闸时点、p=100%、项目资格和FCR研究单元均沿用既有假设。模型给出条件事后毛现金，不是实际发票、净利润或完整FCR履约收益；不包括FCR频率激活损耗和额外循环。单日通过不替代未来情景的全期审计。','',
        '## 附录A：两天全部市场价格（192行）','',
        'DA及aFRR激活价格EUR/MWh；FCR/aFRR容量价格EUR/(MW·h)。A/F列分别标识整小时aFRR/FCR是否允许参与。缺失保留，价格有效不等于可以绕过整小时数据门禁。完整精度和系统价量/汇率见inputs_two_days.csv。','',
        table(['当地交付起点','DA','FCR容量','aFRR容量↑','aFRR容量↓','aFRR激活↑','aFRR激活↓','A/F有效'],[[local(r['delivery_start_utc'])]+[fmt(num(r[k]),9) for k in FIELDS]+[f'{int(valid_a[r["capacity_hour_start_utc"]])}/{int(valid_f[r["capacity_hour_start_utc"]])}'] for r in raw]),'',
        '## 附录B：两天逐QH申报、激活电量与SOC（192行）','',
        '26日为冻结执行，27日为本窗口新增计划。B/F/U/V单位MW，激活和SOC单位MWh；FCR激活电量未模拟。容量小时订单为核算展开到QH，原生订单没有重复申报。','',
        table(['当地起点','角色','B','F','U','V','激活↑','激活↓','起SOC','末SOC'],[[r['local_time'],r['role']]+[fmt(r[k],9) for k in ('da_mw','fcr_mw','afrr_up_mw','afrr_down_mw','afrr_up_activation_mwh','afrr_down_activation_mwh','ein_mwh','eout_mwh')] for r in plan]),'',
        '## 附录C：11月26日96QH现金明细','',
        '每项EUR，逐行相加为该QH现金，再对96行求和得到当日合计；CSV保留未做展示舍入的Decimal计算值。','',
        table(['当地起点',*LABELS,'合计'],[[r['local_time']]+[fmt(r[k],9) for k in (*CASH,'total_eur')] for r in executed])]
    second_j=next(j for j,r in enumerate(executed) if r['da_mw']<D('-1') and r['afrr_up_activation_mwh']>D('.01'))
    second=executed[second_j];second_input=raw[second_j]
    extra=['### 第二个示例：DA买电与上调激活同时存在','',
        f'当地{second["local_time"]}，B={fmt(second["da_mw"],9)} MW；U={fmt(second["afrr_up_mw"])}、V={fmt(second["afrr_down_mw"])}、F={fmt(second["fcr_mw"])} MW。系统上调中标{second_input["afrr_up_accepted_capacity_mw"]} MW、激活{second_input["afrr_up_system_activation_energy_mwh"]} MWh，因此α↑={fmt(second["alpha_up"],12)}，电站激活上调={fmt(second["afrr_up_activation_mwh"],12)} MWh。','',
        table(['现金项','带符号数量','价格','现金EUR'],[[label,fmt(q,12),fmt(num(second_input[field]),12),fmt(second[c],12)] for label,q,field,c in zip(LABELS,(second['da_signed_mwh'],second['fcr_mw']*H,second['afrr_up_mw']*H,second['afrr_down_mw']*H,second['afrr_up_activation_mwh'],-second['afrr_down_activation_mwh']),FIELDS,CASH)]),'',
        table(['相位','时长h','净功率MW','充电MW','放电MW','起SOC','末SOC'],[[r['phase']]+[fmt(r[k],12) for k in ('hours','Y','C','D','ein','eout')] for r in phases if r['start']==second['delivery_start_utc']]),'',
        f'该QH现金合计{fmt(second["total_eur"],12)} EUR。上调激活代表相对DA基准的增量，未必对应电池实际放电；相位净功率Y决定真实充放电及SOC。','']
    at=report.index('## 4. 两日优化目标与当天现金的区别');report[at:at]=extra
    (OUT/'随机单日独立审计.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    result=dict(status='PASS',local_date=day,sequence=i,chain_transactions_checked=chain_count,input_qh=192,executed_qh=96,phase_count=len(phases),orders=len(native),opening_soc_mwh=num(opening['soc_mwh']),closing_soc_mwh=executed[-1]['eout_mwh'],daily_efc=day_efc,used_efc_before=used,used_efc_after=used+day_efc,cash_eur=totals,total_eur=total,plan_cash_eur=plan_cash,salvage_eur=salvage,objective_eur=plan_cash+salvage,afrr_up_activation_mwh=sum(r['afrr_up_activation_mwh'] for r in executed),afrr_down_activation_mwh=sum(r['afrr_down_activation_mwh'] for r in executed),example_local_time=ex['local_time'],checks=dict(checks),maximum_errors=dict(errors),source_sha256=sha(source),run_manifest_sha256=sha(RUN/'manifest.json'),transaction_sha256=tx['sha256'],prior_transaction_sha256=prev['sha256'],script_sha256=sha(Path(__file__)))
    result['transaction_file_bytes_sha256']=sha(RUN/f'windows/{i:04d}.json')
    result['hash_definitions']={'transaction_sha256':'SHA256 of canonical transaction payload excluding its sha256 member; identical meaning in immutable selection.json','transaction_file_bytes_sha256':'SHA256 of complete original JSON file bytes','run_manifest_sha256':'SHA256 of complete run manifest file bytes'}
    write_json('validation.json',result)
    write_json('artifact_manifest.json',dict(status='BUILT',files={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name not in ('artifact_manifest.json','review_and_acceptance.md')}))
    print(json.dumps(result,ensure_ascii=False,default=str))

if __name__=='__main__':build()
