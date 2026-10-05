import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const HERE=path.dirname(fileURLToPath(import.meta.url));
const OUT=path.resolve(HERE,'../../outputs/01a0f118-8c45-7e53-9dc7-5c2b28a5ed1c/20260801_02_audit');
await fs.mkdir(OUT,{recursive:true});
const p=JSON.parse(await fs.readFile(path.join(HERE,'payload.json'),'utf8'));
const wb=Workbook.create();
const d1=wb.worksheets.add('8月1日审计'),d2=wb.worksheets.add('8月2日审计'),build=wb.worksheets.add('两日求解价格与决策'),phase=wb.worksheets.add('相位SOC复算'),orders=wb.worksheets.add('订单与窗口'),src=wb.worksheets.add('原始输入与口径');
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const cell=(s,r,c,v,formula=false)=>{s.getCell(r-1,c-1)[formula?'formulas':'values']=[[v]];};
const fmt='#,##0.000000;[Red](#,##0.000000);0.000000';
const checkFmt='[>=0.000005]0.000000;[<=-0.000005](0.000000);"0.000000"';
function base(s,rows,cols){s.showGridLines=false;const g=s.getRangeByIndexes(0,0,rows,cols);g.format.font={name:'Arial',size:10,color:'#202B3A'};g.format.rowHeight=21;g.format.columnWidth=19;g.format.verticalAlignment='center';s.getRange(`A1:A${rows}`).format.columnWidth=27;}
function header(s,row,labels){const g=s.getRangeByIndexes(row-1,0,1,labels.length);g.values=[labels];g.format={fill:'#213B59',font:{bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:55,horizontalAlignment:'center',verticalAlignment:'center'};s.freezePanes.freezeRows(row);s.freezePanes.freezeColumns(1);}
function title(s,text,notes){cell(s,2,1,text);s.getRange('A2').format.font={size:14,bold:true};notes.forEach((v,i)=>cell(s,i+3,1,v));s.getRange('A3:A5').format.font={italic:true,color:'#566374'};}
const typed=v=>v===''?null:v==='True'||v==='true'?true:v==='False'||v==='false'?false:/^-?\d+(\.\d*)?([eE][+-]?\d+)?$/.test(v)?Number(v):v;
const excelDate=v=>(Date.parse(v)-Date.UTC(1899,11,30))/86400000;
const cashKeys=['da_eur','fcr_capacity_eur','afrr_up_capacity_eur','afrr_down_capacity_eur','afrr_up_activation_eur','afrr_down_activation_eur','total_eur'];
const savedKeys=Object.keys(p.saved[0]); const rawKeys=Object.keys(p.raw[0]);
const rawCols=Object.fromEntries(rawKeys.map((k,i)=>[k,col(i)]));
const savedCols=Object.fromEntries(savedKeys.map((k,i)=>[k,col(rawKeys.length+i)]));
base(src,345+p.sources.length,rawKeys.length+savedKeys.length);
title(src,'原始价格输入、执行记录与计算口径',['原始价格为EUR，容量价为平均接受报价代理；本表保留缺失和合法零价。','复制的原始数值为蓝字。修改价格只复算既定决策的现金，不会重新优化MILP。']);
src.getRange('A4:H6').values=[['7月31日末SOC MWh',p.prior_end_soc,'额定功率MW',100,'FCR月份额',0.3125,'aFRR月份额',0.13714285714285715],['单向效率',0.92,'名义能量MWh',200,'季度时长h',0.25,'EFC分母MWh',360],['SOC下限MWh',10,'SOC上限MWh',190,'容量现金旧系数','已删除','时区','Europe/Bucharest']];
src.getRange('B4:H6').format.font.color='#2459A6'; src.getRange('F4:H4').setNumberFormat('0.0000%');
header(src,8,[...rawKeys,...savedKeys.map(k=>'ledger_'+k)]);
const dateKeys=['delivery_start_utc','delivery_end_utc','capacity_hour_start_utc','local_date','fx_fixing_date'];
src.getRangeByIndexes(8,0,288,rawKeys.length+savedKeys.length).values=p.raw.map((r,i)=>[...rawKeys.map(k=>k==='local_time'?p.serials[i]:dateKeys.includes(k)?excelDate(r[k]):typed(r[k])),...savedKeys.map(k=>p.saved[i][k])]);
src.getRangeByIndexes(8,0,288,rawKeys.length+savedKeys.length).format.font.color='#2459A6';
src.getRangeByIndexes(8,0,288,rawKeys.length+savedKeys.length).setNumberFormat(fmt);
for(const k of [...dateKeys,'local_time']){src.getRange(`${rawCols[k]}9:${rawCols[k]}296`).setNumberFormat(['local_date','fx_fixing_date'].includes(k)?'yyyy-mm-dd':'yyyy-mm-dd hh:mm:ss');src.getRange(`${rawCols[k]}1:${rawCols[k]}296`).format.columnWidth=27;}
const notes=[
 ['版本','2026-10-04月度份额版，100MW/200MWh，全EUR，无旧100%/80%/60%现金系数。'],
 ['价格','DA及激活EUR/MWh，容量EUR/(MW·h)。FCR/aFRR容量均来自DAMAS averageAcceptedPrice，并非本站报价。'],
 ['汇率','按Bucharest交付日，取严格早于交付日的最近BNR参考日。原数据已换汇，本表不再次换汇。'],
 ['现金','六类市场毛现金，不是实际发票、到账款或净利润。窗口残值不计入每日现金。'],
 ['下调符号','下调激活现金=−激活MWh×原下调价格。负价格形成正现金。'],
 ['激活比例','系统激活MWh÷(系统已采购MW×0.25h)。本站激活=中标MW×有效比例×0.25h。'],
 ['门禁','aFRR任一季度必要数据异常则完整小时禁用；有效比例0仅表示模型无aFRR义务，不替换原数据。'],
 ['FCR','仅容量机会价值。已预留双向功率和30分钟能量缓冲，未计频率激活、恢复损耗及额外循环。'],
 ['信息','两日历史价格、激活比例及整月份额是事后完美信息输入，不表示当时已可获得。'],
 ['三相','下调、上调、无激活顺序为模型假设。相位时间由比例展开，不是实际AGC时间。'],
 ['计划复原','每日事务只存当日执行相位。次日轨迹由本窗冻结订单及下一日执行记录确定性复原，已核对订单、SOC连续及两日目标。'],
 ['来源','价格由OPCOM、Transelectrica/DAMAS提供，汇率由BNR提供。逐件来源键、URL和哈希如下。'],
 ['模型代码SHA256',p.provenance.code_sha256],['价格输入SHA256',p.provenance.input_file_sha256],['容量需求SHA256',p.provenance.capacity_file_sha256],['运行manifest SHA256',p.provenance.run_manifest_sha256]
];
src.getRange('A300:B315').values=notes;src.getRange('A300:B315').format.rowHeight=26;src.getRange('B300:B315').format.columnWidth=25;
header(src,320,['来源键','机构','官方URL','原件SHA256','获取UTC']);src.freezePanes.freezeRows(8);
src.getRangeByIndexes(320,0,p.sources.length,5).values=p.sources.map(r=>[r.source_key,r.publisher,r.url,r.sha256,r.retrieved_utc]);
src.getRange(`A321:E${320+p.sources.length}`).format.wrapText=true;src.getRange(`A321:E${320+p.sources.length}`).format.rowHeight=95;
const defs=[
 ['time','时间\nBucharest'],['da_price','DA价格\nEUR/MWh'],['fcr_price','FCR容量价\nEUR/(MW·h)'],['u_price','aFRR上容量价\nEUR/(MW·h)'],['d_price','aFRR下容量价\nEUR/(MW·h)'],['ua_price','aFRR上激活价\nEUR/MWh'],['da_price_act','aFRR下激活价\nEUR/MWh'],['fa_price','FCR激活\n未纳入模型'],
 ['ein','起SOC\nMWh'],['eout','末SOC\nMWh'],['B','DA净申报\nMW'],['F','FCR中标预留\nMW'],['U','aFRR上中标\nMW'],['D','aFRR下中标\nMW'],['eu','上调激活\nMWh'],['ed','下调激活\nMWh'],
 ['cash_da','DA现金\nEUR'],['cash_f','FCR容量现金\nEUR'],['cash_u','aFRR上容量现金\nEUR'],['cash_d','aFRR下容量现金\nEUR'],['cash_ua','aFRR上激活现金\nEUR'],['cash_da_act','aFRR下激活现金\nEUR'],['total','总现金\nEUR'],['ledger','原账本总现金\nEUR'],['cash_diff','现金差异\nEUR'],['role','执行或计划'],
 ['valid_a','aFRR小时有效\n1/0'],['valid_f','FCR小时有效\n1/0'],['hours','时长h'],['sf','FCR月份额'],['sa','aFRR月份额'],['au','有效α上'],['ad','有效α下'],['sys_u','系统上采购\nMW'],['sys_d','系统下采购\nMW'],['sys_eu','系统上激活\nMWh'],['sys_ed','系统下激活\nMWh'],['sys_f','系统FCR采购\nMW'],
 ['efc','EFC复算'],['charge','AC充电\nMWh'],['discharge','AC放电\nMWh'],['soc_calc','相位复算末SOC\nMWh'],['soc_diff','SOC差异\nMWh'],['fx','汇率\nRON/EUR'],['fx_date','汇率来源日'],['utc','UTC起点'],['da_id','DA原生订单ID'],['da_minutes','DA原生分钟'],['gate_reason','aFRR门禁原因'],['demand_f','FCR需求\nMW'],['demand_u','aFRR上需求\nMW'],['demand_d','aFRR下需求\nMW'],['limit_f','FCR最终容量上限\nMW'],['limit_u','aFRR上最终上限\nMW'],['limit_d','aFRR下最终上限\nMW'],['window','求解窗口起日'],
 ['calc_da','DA现金计算过程'],['calc_f','FCR容量现金计算过程'],['calc_u','aFRR上容量现金计算过程'],['calc_d','aFRR下容量现金计算过程'],['calc_ua','aFRR上激活现金计算过程'],['calc_da_act','aFRR下激活现金计算过程'],['calc_total','总现金计算过程']
];
const C=Object.fromEntries(defs.map(([k],i)=>[k,col(i)])); const headers=defs.map(x=>x[1]);
base(build,403,defs.length);base(d1,123,defs.length);base(d2,123,defs.length);
title(build,'两次MILP求解的价格、决策与现金',['首192行：8月1日求解，8月1日执行及8月2日冻结计划；后192行：8月2日求解及8月3日计划。','六类现金在本表通过Excel公式计算，日审计表链接执行部分。8月3日不计入两天现金。']);
title(d1,'2026-08-01 MILP审计',['100MW/200MWh，月度份额版。订单由7月31日冻结，8月1日正式执行。','A列为15分钟，B—H价格，I—P状态与选择，Q—W现金，BE—BK为带取值的计算过程。']);
title(d2,'2026-08-02 MILP审计',['100MW/200MWh，月度份额版。订单由8月1日冻结，8月2日正式执行。','A列为15分钟，B—H价格，I—P状态与选择，Q—W现金，BE—BK为带取值的计算过程。']);
for(const s of [build,d1,d2])header(s,8,headers);
d1.tabColor='#213B59';d2.tabColor='#213B59';build.tabColor='#577392';
const priceKeys=['da_price_eur_per_mwh','fcr_capacity_price_eur_per_mw_h_proxy','afrr_up_capacity_price_eur_per_mw_h_proxy','afrr_down_capacity_price_eur_per_mw_h_proxy','afrr_up_activation_price_eur_per_mwh_proxy','afrr_down_activation_price_eur_per_mwh_proxy'];
const lastPhase=new Map();p.phases.forEach((v,i)=>lastPhase.set(v.plan_index,i+9));
const formulas=p.plan.map((v,i)=>{
 const r=i+9,s=v.raw_index+9,ref=k=>`'原始输入与口径'!${rawCols[k]}${s}`,led=k=>`'原始输入与口径'!${savedCols[k]}${s}`,at=k=>`${C[k]}${r}`,f=Object.fromEntries(defs.map(([k])=>[k,null]));
 f.time=`=${ref('local_time')}`;
 ['da_price','fcr_price','u_price','d_price','ua_price','da_price_act'].forEach((k,j)=>f[k]=`=IF(ISNUMBER(${ref(priceKeys[j])}),${ref(priceKeys[j])},"缺失")`); f.fa_price='="未模拟"';
 for(const [k,field] of Object.entries({ein:'ein_mwh',eout:'eout_mwh',B:'da_mw',F:'fcr_mw',U:'afrr_up_mw',D:'afrr_down_mw',ledger:'total_eur',sf:'fcr_capacity_share_coefficient',sa:'afrr_up_capacity_share_coefficient',demand_f:'fcr_demand_mw',demand_u:'afrr_up_demand_mw',demand_d:'afrr_down_demand_mw',limit_f:'fcr_upper',limit_u:'afrr_up_upper',limit_d:'afrr_down_upper'}))f[k]=`=${led(field)}`;
 f.valid_a=`=IF(${ref('afrr_hour_data_valid')},1,0)`;f.valid_f=`=IF(${ref('fcr_hour_data_valid')},1,0)`;f.hours="='原始输入与口径'!$F$5";
 for(const [k,field] of Object.entries({sys_u:'afrr_up_accepted_capacity_mw',sys_d:'afrr_down_accepted_capacity_mw',sys_eu:'afrr_up_system_activation_energy_mwh',sys_ed:'afrr_down_system_activation_energy_mwh',sys_f:'fcr_accepted_capacity_mw'}))f[k]=`=IF(ISNUMBER(${ref(field)}),${ref(field)},"缺失")`;
 f.au=`=IF(${at('valid_a')}=0,0,${at('sys_eu')}/(${at('sys_u')}*${at('hours')}))`;f.ad=`=IF(${at('valid_a')}=0,0,${at('sys_ed')}/(${at('sys_d')}*${at('hours')}))`;
 f.eu=`=${at('U')}*${at('au')}*${at('hours')}`;f.ed=`=${at('D')}*${at('ad')}*${at('hours')}`;
 for(const [k,q,price] of [['cash_da','B','da_price'],['cash_f','F','fcr_price'],['cash_u','U','u_price'],['cash_d','D','d_price']])f[k]=`=IF(${at(q)}=0,0,IF(ISNUMBER(${at(price)}),${at(q)}*${at(price)}*${at('hours')},NA()))`;
 f.cash_ua=`=IF(${at('eu')}=0,0,${at('eu')}*${at('ua_price')})`;f.cash_da_act=`=IF(${at('ed')}=0,0,-${at('ed')}*${at('da_price_act')})`;
 f.total=`=SUM(${at('cash_da')}:${at('cash_da_act')})`;f.cash_diff=`=${at('total')}-${at('ledger')}`;
 f.role=`="${v.role}"`;f.window=`=${p.windows[v.window].serial}`;
 const pe=8+p.phases.length;
 for(const [k,c] of [['efc','N'],['charge','Q'],['discharge','R']])f[k]=`=SUMIFS('相位SOC复算'!$${c}$9:$${c}$${pe},'相位SOC复算'!$S$9:$S$${pe},${i+1})`;
 f.soc_calc=`='相位SOC复算'!J${lastPhase.get(i)}`;f.soc_diff=`=${at('soc_calc')}-${at('eout')}`;
 for(const [k,field] of Object.entries({fx:'fx_ron_per_eur',fx_date:'fx_fixing_date',utc:'delivery_start_utc',da_id:'da_contract_id',da_minutes:'da_native_resolution_minutes',gate_reason:'afrr_order_gate_reason'}))f[k]=`=IF(ISBLANK(${ref(field)}),"",${ref(field)})`;
 const text=k=>`TEXT(${at(k)},"0.000000")`;
 for(const [k,q,price,cash] of [['calc_da','B','da_price','cash_da'],['calc_f','F','fcr_price','cash_f'],['calc_u','U','u_price','cash_u'],['calc_d','D','d_price','cash_d']])f[k]=`=IF(${at(q)}=0,"零头寸，无结算现金",${text(q)}&" MW × "&${text(price)}&" × "&${text('hours')}&" h = "&${text(cash)}&" EUR")`;
 f.calc_ua=`=IF(${at('eu')}=0,"零上调激活电量",${text('eu')}&" MWh × "&${text('ua_price')}&" = "&${text('cash_ua')}&" EUR")`;
 f.calc_da_act=`=IF(${at('ed')}=0,"零下调激活电量","−("&${text('ed')}&" MWh × "&${text('da_price_act')}&") = "&${text('cash_da_act')}&" EUR")`;
 f.calc_total=`=${text('cash_da')}&" + "&${text('cash_f')}&" + "&${text('cash_u')}&" + "&${text('cash_d')}&" + "&${text('cash_ua')}&" + "&${text('cash_da_act')}&" = "&${text('total')}&" EUR"`;
 return defs.map(([k])=>f[k]);
});
build.getRangeByIndexes(8,0,384,defs.length).formulas=formulas;
for(const [s,offset] of [[d1,0],[d2,192]])s.getRangeByIndexes(8,0,96,defs.length).formulas=Array.from({length:96},(_,i)=>defs.map(([k],j)=>k==='role'?'="正式执行"':`='两日求解价格与决策'!${col(j)}${offset+i+9}`));
for(const [s,n] of [[build,384],[d1,96],[d2,96]]){
 const end=n+8; s.getRange(`B9:BC${end}`).setNumberFormat(fmt);s.getRange(`A9:A${end}`).setNumberFormat('yyyy-mm-dd hh:mm');s.getRange(`${C.utc}9:${C.utc}${end}`).setNumberFormat('yyyy-mm-dd hh:mm');s.getRange(`${C.fx_date}9:${C.fx_date}${end}`).setNumberFormat('yyyy-mm-dd');s.getRange(`${C.window}9:${C.window}${end}`).setNumberFormat('yyyy-mm-dd');
 s.getRange(`B9:H${end}`).format.fill='#EEF3FA';s.getRange(`I9:P${end}`).format.fill='#F3F5F7';s.getRange(`Q9:W${end}`).format.fill='#EDF4ED';
 s.getRange(`${C.sf}9:${C.ad}${end}`).setNumberFormat('0.0000%');s.getRange(`${C.role}9:${C.role}${end}`).format.columnWidth=25;s.getRange(`${C.da_id}9:${C.da_id}${end}`).format.columnWidth=28;s.getRange(`${C.gate_reason}9:${C.gate_reason}${end}`).format.columnWidth=36;s.getRange(`${C.utc}9:${C.utc}${end}`).format.columnWidth=27;
 s.getRange(`${C.calc_da}8:${C.calc_da_act}${end}`).format.columnWidth=66;s.getRange(`${C.calc_total}8:${C.calc_total}${end}`).format.columnWidth=104;
 s.getRange(`${C.cash_diff}9:${C.cash_diff}${end}`).conditionalFormats.addCustom(`ABS(${C.cash_diff}9)>0.00001`,{fill:'#FBE3E3',font:{color:'#A52828'}});s.getRange(`${C.soc_diff}9:${C.soc_diff}${end}`).conditionalFormats.addCustom(`ABS(${C.soc_diff}9)>0.000001`,{fill:'#FBE3E3',font:{color:'#A52828'}});
 s.getRange(`${C.cash_diff}9:${C.cash_diff}${end}`).setNumberFormat(checkFmt);s.getRange(`${C.soc_diff}9:${C.soc_diff}${end}`).setNumberFormat(checkFmt);
 if(n===96){const r=end+2;cell(s,r,1,'当日现金及电量合计');for(const k of ['eu','ed','cash_da','cash_f','cash_u','cash_d','cash_ua','cash_da_act','total','ledger'])cell(s,r,defs.findIndex(x=>x[0]===k)+1,`=SUM(${C[k]}9:${C[k]}${end})`,true);s.getRange(`A${r}:X${r}`).format.font.bold=true;s.getRange(`O${r}:X${r}`).setNumberFormat(fmt);}
}
build.getRange('A201:BK201').format.borders={top:{style:'medium',color:'#213B59'}};
for(const [s,idx] of [[d1,0],[d2,1]]){
 cell(s,109,1,'承接前日末SOC MWh');cell(s,109,2,`='订单与窗口'!C${idx+6}`,true);
 cell(s,110,1,'当日期末SOC MWh');cell(s,110,2,'=J104',true);
 cell(s,112,1,'两天正式现金合计 EUR');cell(s,112,2,"='8月1日审计'!W106+'8月2日审计'!W106",true);
 cell(s,115,1,'容量现金=中标预留MW×价格×时长；月份额只限制MW，不再次乘现金。');
 cell(s,116,1,'FCR对称容量只计一次；激活电量已为MWh，不再乘0.25小时。');
 cell(s,117,1,'逐行现金公式在Q—W，含取值的过程在BE—BK；显示精度不改变底层数值。');
 s.getRange('B109:B112').setNumberFormat(fmt);
}
base(phase,p.phases.length+12,20);title(phase,'两次规划的相位SOC与循环复算',['每个窗口独立承接其前日末SOC。上调、下调、无激活相位来自冻结订单的确定性轨迹。','净功率、充放电、SOC及EFC均用Excel公式复算。相位细分时间为模型展开时刻。']);
header(phase,8,['相位起点\nBucharest','相位终点\nBucharest','所属15分钟起点','相位 d/u/0','相位时长h','净功率MW','充电MW','放电MW','复算起SOC MWh','复算末SOC MWh','原记录起SOC','原记录末SOC','SOC差异MWh','复算EFC','原记录EFC','EFC差异','AC充电MWh','AC放电MWh','规划QH序号','窗口起日']);
phase.getRangeByIndexes(8,0,p.phases.length,20).values=p.phases.map(v=>[v.serial_start,v.serial_end,p.serials[p.plan[v.plan_index].raw_index],v.phase,v.hours,null,null,null,null,null,v.ein,v.eout,null,null,v.efc,null,null,null,v.plan_index+1,p.windows[v.window].serial]);
const phPower=[],phEfc=[],phEnergy=[];
for(let i=0;i<p.phases.length;i++){
 const v=p.phases[i],r=i+9,q=v.plan_index+9,ref=k=>`'两日求解价格与决策'!${C[k]}${q}`;
 const start=i===0||p.phases[i-1].window!==v.window;
 phPower.push([`=IF(D${r}="d",${ref('B')}-${ref('D')},IF(D${r}="u",${ref('B')}+${ref('U')},${ref('B')}))`,`=MAX(-F${r},0)`,`=MAX(F${r},0)`,start?`='订单与窗口'!C${v.window+6}`:`=J${r-1}`,`=I${r}+E${r}*(G${r}*'原始输入与口径'!$B$5-H${r}/'原始输入与口径'!$B$5)`]);
 phEfc.push([`=J${r}-L${r}`,`=E${r}*(G${r}*'原始输入与口径'!$B$5+H${r}/'原始输入与口径'!$B$5)/'原始输入与口径'!$H$5`]);phEnergy.push([`=N${r}-O${r}`,`=E${r}*G${r}`,`=E${r}*H${r}`]);
}
const pe=p.phases.length+8;phase.getRange(`F9:J${pe}`).formulas=phPower;phase.getRange(`M9:N${pe}`).formulas=phEfc;phase.getRange(`P9:R${pe}`).formulas=phEnergy;phase.getRange(`A9:C${pe}`).setNumberFormat('yyyy-mm-dd hh:mm:ss.000');phase.getRange(`T9:T${pe}`).setNumberFormat('yyyy-mm-dd');phase.getRange(`A1:C${pe}`).format.columnWidth=30;phase.getRange(`E9:R${pe}`).setNumberFormat(fmt);phase.getRange(`M9:M${pe}`).conditionalFormats.addCustom('ABS(M9)>0.000001',{fill:'#FBE3E3'});phase.getRange(`P9:P${pe}`).conditionalFormats.addCustom('ABS(P9)>0.0000001',{fill:'#FBE3E3'});
base(orders,p.orders.length+16,21);title(orders,'求解窗口、订单来源与容量上限',['订单变量为模型选择的中标预留量，不是完整报价曲线。时刻为研究时表，不声称已核定实际招标时间。','8月1日订单承接7月31日冻结，8月2日订单由8月1日冻结。残值仅用于规划目标。']);
header(orders,5,['窗口起日','事务序号','起SOC MWh','当日期末SOC','两日期末SOC','两日计划现金EUR','窗口残值EUR','目标复算EUR','原目标EUR','目标差异EUR','变量数','整数数','二元数','约束数','Gap','状态']);
orders.getRange('A6:P7').values=p.windows.map(w=>[w.serial,w.sequence,w.start_soc,w.end_execution_soc,w.end_plan_soc,w.metrics.plan_cash_eur,w.metrics.salvage_eur,null,w.metrics.incumbent_eur,null,w.metrics.variables,w.metrics.integer,w.metrics.binary,w.metrics.rows,w.metrics.objective_gap,w.metrics.audit]);
orders.getRange('H6:H7').formulas=[['=F6+G6'],['=F7+G7']];orders.getRange('J6:J7').formulas=[['=H6-I6'],['=H7-I7']];orders.getRange('A6:A7').setNumberFormat('yyyy-mm-dd');orders.getRange('C6:J7').setNumberFormat(fmt);orders.getRange('O6:O7').setNumberFormat('0.000000%');orders.getRange('J6:J7').conditionalFormats.addCustom('ABS(J6)>0.00001',{fill:'#FBE3E3'});
header(orders,12,['窗口起日','产品','交付起点\nBucharest','交付终点\nBucharest','订单来源','中标预留MW','最终上限MW','月份额','系统需求MW','份额形成上限MW','关闸\nBucharest','结果时刻\nBucharest','门禁原因','份额来源状态','参考月份','订单ID','原承诺状态','交付起点UTC','FCR单元分配MW','事务SHA256']);
orders.getRangeByIndexes(12,0,p.orders.length,20).values=p.orders.map(o=>[p.windows[o.window].serial,o.product,excelDate(o.start)+3/24,excelDate(o.end)+3/24,o.origin,o.amount_mw,o.upper,o.capacity_share_coefficient??null,o.system_demand_min_mw??null,o.share_limit_mw??null,excelDate(o.gate)+3/24,excelDate(o.result)+3/24,o.reason,o.capacity_share_status??'',o.capacity_share_reference_month??'',o.key,o.commitment,o.start,(o.units_mw??[]).join(', '),p.windows[o.window].sha256]);
const oe=p.orders.length+12;orders.getRange(`A13:A${oe}`).setNumberFormat('yyyy-mm-dd');orders.getRange(`C13:D${oe}`).setNumberFormat('yyyy-mm-dd hh:mm');orders.getRange(`K13:L${oe}`).setNumberFormat('yyyy-mm-dd hh:mm');orders.getRange(`F13:J${oe}`).setNumberFormat(fmt);orders.getRange(`H13:H${oe}`).setNumberFormat('0.0000%');orders.getRange(`C1:D${oe}`).format.columnWidth=27;orders.getRange(`K1:L${oe}`).format.columnWidth=27;orders.getRange(`P1:T${oe}`).format.columnWidth=38;
console.log('Populated audit, planning, phase, source and order sheets');
phase.getRange(`M9:M${pe}`).setNumberFormat(checkFmt);phase.getRange(`P9:P${pe}`).setNumberFormat(checkFmt);orders.getRange('J6:J7').setNumberFormat(checkFmt);
wb.recalculate();
let maxCash=0,maxSoc=0,comparisons=0;
const values=build.getRangeByIndexes(8,0,384,defs.length).values;
const index=k=>defs.findIndex(x=>x[0]===k);
for(let i=0;i<384;i++){
 const a=values[i],s=p.plan[i].ledger;
 for(const [k,field] of Object.entries({ein:'ein_mwh',eout:'eout_mwh',B:'da_mw',F:'fcr_mw',U:'afrr_up_mw',D:'afrr_down_mw',eu:'afrr_up_activation_mwh',ed:'afrr_down_activation_mwh',cash_da:'da_eur',cash_f:'fcr_capacity_eur',cash_u:'afrr_up_capacity_eur',cash_d:'afrr_down_capacity_eur',cash_ua:'afrr_up_activation_eur',cash_da_act:'afrr_down_activation_eur',total:'total_eur',efc:'efc'})){
  const got=a[index(k)];if(typeof got!=='number'||Math.abs(got-s[field])>1e-5)throw Error(`Row ${i} ${k}: ${got} != ${s[field]}`);comparisons++;
 }
 maxCash=Math.max(maxCash,Math.abs(a[index('cash_diff')]));maxSoc=Math.max(maxSoc,Math.abs(a[index('soc_diff')]));
}
if(maxSoc>1e-6)throw Error('Phase SOC mismatch');
for(const [s,wi] of [[d1,0],[d2,1]]){const got=s.getRange('W106').values[0][0];if(Math.abs(got-p.windows[wi].execution_cash.total_eur)>1e-6)throw Error('Daily sum mismatch');}
const expectedTotal=p.windows.reduce((a,w)=>a+w.execution_cash.total_eur,0);if(Math.abs(d1.getRange('B112').values[0][0]-expectedTotal)>1e-6)throw Error('Two day sum mismatch');
for(let wi=0;wi<2;wi++){const sum=values.slice(wi*192,(wi+1)*192).reduce((a,v)=>a+v[index('total')],0);if(Math.abs(sum-p.windows[wi].metrics.plan_cash_eur)>1e-5)throw Error('Window plan cash mismatch');}
const test=p.plan.findIndex(v=>v.qh<96&&Math.abs(v.ledger.da_mw)>1),rr=test+9,ss=p.plan[test].raw_index+9,addr=`${rawCols.da_price_eur_per_mwh}${ss}`,old=src.getRange(addr).values[0][0],before=build.getRange(`${C.cash_da}${rr}`).values[0][0];
src.getRange(addr).values=[[old+1]];wb.recalculate();const after=build.getRange(`${C.cash_da}${rr}`).values[0][0];if(Math.abs(after-before-p.plan[test].ledger.da_mw*.25)>1e-6)throw Error('DA price change test');src.getRange(addr).values=[[old]];wb.recalculate();
const zero=p.plan.findIndex(v=>v.ledger.fcr_mw===0);if(zero>=0){const ss=p.plan[zero].raw_index+9,addr=`${rawCols.fcr_capacity_price_eur_per_mw_h_proxy}${ss}`,old=src.getRange(addr).values[0][0];src.getRange(addr).values=[[null]];wb.recalculate();if(build.getRange(`${C.cash_f}${zero+9}`).values[0][0]!==0)throw Error('Zero headroom missing-price test');src.getRange(addr).values=[[old]];wb.recalculate();}
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},summary:'final formula error scan'});await fs.writeFile(path.join(OUT,'formula_scan.ndjson'),errors.ndjson);console.log(errors.ndjson);
for(const [s,range,name] of [[d1,'A2:G13','aug1_prices'],[d1,'I8:P15','aug1_choices'],[d1,'Q8:Y15','aug1_cash'],[d1,'BE8:BF12','cash_process'],[d2,'Q99:Y106','aug2_cash_total'],[build,'A198:G205','window_boundary'],[phase,'A8:J14','phase_soc'],[orders,'A5:J7','windows'],[src,'A4:H10','source']]){
 const png=await wb.render({sheetName:s.name,range,scale:1.3,format:'png'});await fs.writeFile(path.join(OUT,name+'.png'),new Uint8Array(await png.arrayBuffer()));
}
const file=await SpreadsheetFile.exportXlsx(wb);const filename='RO_100MW_200MWh_20260801_02_MILP审计.xlsx';await file.save(path.join(OUT,filename));
const result={status:'PASS',file:filename,executionRows:192,sourceRows:288,planningRows:384,phaseRows:p.phases.length,comparisons,maxCashDifference:maxCash,maxSocDifference:maxSoc,formulaChangeTest:'PASS: price +1 changes fixed-dispatch DA cash by signed MW*0.25; restored',dailyCash:p.windows.map(w=>w.execution_cash),totalCash:expectedTotal,provenance:p.provenance,nativeExcelLaunched:false};await fs.writeFile(path.join(OUT,'validation.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({output:OUT,comparisons,maxCash,maxSoc,totalCash:expectedTotal}));
