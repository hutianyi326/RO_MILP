import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const HERE=path.dirname(fileURLToPath(import.meta.url));
const OUT=path.resolve(HERE,'../../outputs/01a0f118-8c45-7e53-9dc7-5c2b28a5ed1c/20250101_audit');
await fs.mkdir(OUT,{recursive:true});
const p=JSON.parse(await fs.readFile(path.join(HERE,'payload.json'),'utf8'));
const wb=Workbook.create();
const day=wb.worksheets.add('1月1日审计'),build=wb.worksheets.add('两日价格与决策'),phase=wb.worksheets.add('相位SOC复算'),src=wb.worksheets.add('原始输入与口径');
const day2=wb.worksheets.add('1月2日审计');
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s};
const cell=(s,r,c,v,formula=false)=>{s.getCell(r-1,c-1)[formula?'formulas':'values']=[[v]]};
const fmt='#,##0.000000;[Red](#,##0.000000);0.000000';
function base(s,rows,cols){s.showGridLines=false;s.getRangeByIndexes(0,0,rows,cols).format.font={name:'Arial',size:10,color:'#202B3A'};s.getRangeByIndexes(0,0,rows,cols).format.rowHeight=21;s.getRangeByIndexes(0,0,rows,cols).format.columnWidth=18;s.getRangeByIndexes(0,0,rows,cols).format.verticalAlignment='center';s.getRange(`A1:A${rows}`).format.columnWidth=26;}
function header(s,row,labels){s.getRangeByIndexes(row-1,0,1,labels.length).values=[labels];s.getRangeByIndexes(row-1,0,1,labels.length).format={fill:'#213B59',font:{bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:52,horizontalAlignment:'center',verticalAlignment:'center'};s.freezePanes.freezeRows(row);s.freezePanes.freezeColumns(1);}
function title(s,t,notes){cell(s,2,1,t);s.getRange('A2').format.font={size:14,bold:true};notes.forEach((n,i)=>cell(s,i+3,1,n));s.getRange('A3:A4').format.font={italic:true,color:'#566374'};}
const rawKeys=Object.keys(p.raw[0]);
const savedKeys=['ein_mwh','eout_mwh','da_mw','fcr_mw','afrr_up_mw','afrr_down_mw','afrr_up_activation_mwh','afrr_down_activation_mwh','da_eur','fcr_capacity_eur','afrr_up_capacity_eur','afrr_down_capacity_eur','afrr_up_activation_eur','afrr_down_activation_eur','total_eur','efc'];
const rawCols=Object.fromEntries(rawKeys.map((k,i)=>[k,col(i)]));
const savedCols=Object.fromEntries(savedKeys.map((k,i)=>[k,col(rawKeys.length+i)]));
base(src,231,rawKeys.length+savedKeys.length);
title(src,'源输入与原模型记录',['原输入保留缺失；数字未按显示精度截断。价格已为EUR；本文件不重复换汇。','无2024-12-31运行账本；10MWh是正式期初始化。蓝字为来源数值；改表不会重新运行MILP。']);
src.getRange('A5:H6').values=[['初始SOC MWh',10,'单向效率',0.92,'容量现金系数',1,'EFC分母 MWh',360],['时间尺度h',0.25,'模型名义MWh',200,'功率上限MW',100,'时区','Europe/Bucharest']];
src.getRange('B5:H6').format.font.color='#2459A6';
header(src,8,[...rawKeys,...savedKeys.map(k=>'ledger_'+k)]);
const typed=v=>v===''?null:v==='True'||v==='true'?true:v==='False'||v==='false'?false:/^-?\d+(\.\d*)?([eE][+-]?\d+)?$/.test(v)?Number(v):v;
const excelDate=v=>(Date.parse(v)-Date.UTC(1899,11,30))/86400000;
const utcKeys=['delivery_start_utc','delivery_end_utc','capacity_hour_start_utc'];
src.getRangeByIndexes(8,0,192,rawKeys.length+savedKeys.length).values=p.raw.map((r,i)=>[...rawKeys.map(k=>k==='local_time'?p.serials[i]:[...utcKeys,'local_date','fx_fixing_date'].includes(k)?excelDate(r[k]):typed(r[k])),...savedKeys.map(k=>p.saved[i][k])]);
src.getRangeByIndexes(8,0,192,rawKeys.length+savedKeys.length).format.font.color='#2459A6';
src.getRangeByIndexes(8,0,192,rawKeys.length+savedKeys.length).setNumberFormat('0.000000');
for(const k of [...utcKeys,'local_time','local_date','fx_fixing_date']){src.getRange(`${rawCols[k]}9:${rawCols[k]}200`).setNumberFormat(['local_date','fx_fixing_date'].includes(k)?'yyyy-mm-dd':'yyyy-mm-dd hh:mm:ss');src.getRange(`${rawCols[k]}1:${rawCols[k]}200`).format.columnWidth=27;}
const sourceHeaders=['来源键','机构','官方URL','原件SHA256','获取UTC'];header(src,204,sourceHeaders);src.freezePanes.freezeRows(8);
src.getRangeByIndexes(204,0,p.sources.length,5).values=p.sources.map(r=>[r.source_key,r.publisher,r.url,r.sha256,r.retrieved_utc]);
src.getRange('A205:E211').format.wrapText=true;src.getRange('A205:E211').format.rowHeight=250;
src.getRange('A215:H226').format.rowHeight=23;
const notes=[['口径','DA/激活 EUR/MWh；容量 EUR/(MW·h)；功率MW；SOC/电量MWh。'],['首日','1月1日已过关闸且无前置订单，申报为0；1月2日为本窗新增计划。'],['FCR','1月无可用容量价格，保留缺失；FCR激活未纳入模型，非零价格假设。'],['完美信息','两日价格为事后历史价，模型已知不等于现实当时已发布。'],['现金','结算列为既定代理价下模型毛现金，不是实际发票或净利润。'],['下调符号','下调现金=−下调激活MWh×原下调价；容量均按时长计费。'],['相位时间','相位起止由模型假设的下调→上调→空闲顺序展开，并非实测激活时刻。'],['窗口残值EUR',p.metrics.salvage_eur],['窗口原目标EUR',p.metrics.incumbent_eur],['代码SHA',p.provenance.code_sha256],['源CSV SHA',p.provenance.input_file_sha256],['事务0000 SHA',p.provenance.transaction_0000_payload_sha256]];
src.getRange('A215:B226').values=notes;
const headers=['时间｜Bucharest','DA价格\nEUR/MWh','FCR容量价格\nEUR/(MW·h)','aFRR上容量价\nEUR/(MW·h)','aFRR下容量价\nEUR/(MW·h)','aFRR上激活价\nEUR/MWh','aFRR下激活价\nEUR/MWh','FCR激活价\n未纳入模型','起SOC\nMWh','末SOC\nMWh','DA净申报\nMW','FCR申报\nMW','aFRR上申报\nMW','aFRR下申报\nMW','上调激活\nMWh','下调激活\nMWh','DA现金\nEUR','FCR容量现金\nEUR','aFRR上容量现金\nEUR','aFRR下容量现金\nEUR','aFRR上激活现金\nEUR','aFRR下激活现金\nEUR','总现金\nEUR','原账本总现金\nEUR','现金差异\nEUR','执行/计划','aFRR小时有效\n1/0','FCR小时有效\n1/0','时长h','容量系数','有效α上','有效α下','系统上容量\nMW','系统下容量\nMW','系统上激活\nMWh','系统下激活\nMWh','系统FCR容量\nMW','EFC复算','AC充电\nMWh','AC放电\nMWh','相位复算末SOC\nMWh','SOC差异\nMWh','汇率\nRON/EUR','汇率日期','UTC起点','DA原生订单ID','原生DA分钟','aFRR门禁原因'];
base(build,202,headers.length);base(day,107,headers.length);base(day2,108,headers.length);
title(day2,'2025-01-02｜100%情景审计',['1月1日优化后冻结的订单，已核对1月2日正式执行账本。期初SOC承接1月1日末值10MWh。','15分钟明细；现金为模型毛现金EUR。价格与决策来自首次两日求解，现金合计不含窗口残值。']);
header(day2,6,headers);day2.tabColor='#213B59';
title(build,'首次MILP｜两日价格与决策',['2025-01-01—01-02｜192个15分钟时段；公式重算现金，原模型决策保持原值。','前96行是1月1日执行；后96行是1月2日计划。缺失价格显示“缺失”；FCR激活显示“未模拟”。']);
title(day,'2025-01-01｜100%情景审计',['首日无前置订单：申报及现金均为0；SOC全天10MWh，为初始化而非前日实测。','A列为市场最细15分钟；更细模型相位见“相位SOC复算”。完整两日已知价格与计划见第二表。']);
header(build,6,headers);header(day,6,headers);day.tabColor='#213B59';build.tabColor='#577392';
const priceKeys=['da_price_eur_per_mwh','fcr_capacity_price_eur_per_mw_h_proxy','afrr_up_capacity_price_eur_per_mw_h_proxy','afrr_down_capacity_price_eur_per_mw_h_proxy','afrr_up_activation_price_eur_per_mwh_proxy','afrr_down_activation_price_eur_per_mwh_proxy'];
const rows=[];
for(let i=0;i<192;i++){
 const r=7+i,s=9+i,ref=k=>`'原始输入与口径'!${rawCols[k]}${s}`,saved=k=>`'原始输入与口径'!${savedCols[k]}${s}`;
 const f=Array(headers.length).fill(null);f[0]=`=${p.serials[i]}`;
 priceKeys.forEach((k,j)=>f[j+1]=`=IF(ISNUMBER(${ref(k)}),${ref(k)},"缺失")`);f[7]='="未模拟"';
 ['ein_mwh','eout_mwh','da_mw','fcr_mw','afrr_up_mw','afrr_down_mw'].forEach((k,j)=>f[j+8]=`=${saved(k)}`);
 f[14]=`=M${r}*AE${r}*AC${r}`;f[15]=`=N${r}*AF${r}*AC${r}`;
 for(const [j,q,price,extra] of [[16,'K','B',''],[17,'L','C',`*AD${r}`],[18,'M','D',`*AD${r}`],[19,'N','E',`*AD${r}`]])f[j]=`=IF(${q}${r}=0,0,IF(ISNUMBER(${price}${r}),${q}${r}*AC${r}*${price}${r}${extra},NA()))`;
 f[20]=`=IF(O${r}=0,0,IF(ISNUMBER(F${r}),O${r}*F${r},NA()))`;f[21]=`=IF(P${r}=0,0,IF(ISNUMBER(G${r}),-P${r}*G${r},NA()))`;
 f[22]=`=SUM(Q${r}:V${r})`;f[23]=`=${saved('total_eur')}`;f[24]=`=W${r}-X${r}`;
 f[25]=`="${i<96?'1月1日执行｜初始化零订单':'1月2日计划｜本窗新增'}"`;
 f[26]=`=IF(${ref('afrr_hour_data_valid')},1,0)`;f[27]=`=IF(${ref('fcr_hour_data_valid')},1,0)`;f[28]=`=${ref('duration_hours')}`;f[29]="='原始输入与口径'!$F$5";
 f[30]=`=IF(AA${r}=0,0,AI${r}/(AG${r}*AC${r}))`;f[31]=`=IF(AA${r}=0,0,AJ${r}/(AH${r}*AC${r}))`;
 ['afrr_up_accepted_capacity_mw','afrr_down_accepted_capacity_mw','afrr_up_system_activation_energy_mwh','afrr_down_system_activation_energy_mwh','fcr_accepted_capacity_mw'].forEach((k,j)=>f[32+j]=`=IF(ISNUMBER(${ref(k)}),${ref(k)},"缺失")`);
 const last=p.phases.map((v,j)=>[v,j]).filter(([v])=>v.qh_index===i).at(-1)[1]+7;
 for(const [j,c] of [[37,'N'],[38,'Q'],[39,'R']])f[j]=`=SUMIFS('相位SOC复算'!$${c}$7:$${c}$443,'相位SOC复算'!$S$7:$S$443,${i+1})`;
 f[40]=`='相位SOC复算'!J${last}`;f[41]=`=AO${r}-J${r}`;
 ['fx_ron_per_eur','fx_fixing_date','delivery_start_utc','da_contract_id','da_native_resolution_minutes','afrr_order_gate_reason'].forEach((k,j)=>f[42+j]=`=IF(ISBLANK(${ref(k)}),"",${ref(k)})`);
 rows.push(f);
}
build.getRangeByIndexes(6,0,192,headers.length).formulas=rows;
day.getRangeByIndexes(6,0,96,headers.length).formulas=rows.slice(0,96).map((_,i)=>headers.map((_,j)=>`='两日价格与决策'!${col(j)}${7+i}`));
day2.getRangeByIndexes(6,0,96,headers.length).formulas=rows.slice(96).map((_,i)=>headers.map((_,j)=>j===25?'="1月2日执行｜前窗冻结订单"':`='两日价格与决策'!${col(j)}${103+i}`));
console.log('Price, decision and cash tables populated');
for(const [s,n] of [[build,192],[day,96],[day2,96]]){
 const end=6+n;s.getRange(`A7:A${end}`).setNumberFormat('yyyy-mm-dd hh:mm');s.getRange(`B7:AV${end}`).setNumberFormat(fmt);s.getRange(`Z7:Z${end}`).format.columnWidth=35;s.getRange(`AA7:AB${end}`).setNumberFormat('0');s.getRange(`AD7:AF${end}`).setNumberFormat('0.0000%');s.getRange(`AS7:AV${end}`).format.columnWidth=31;s.getRange(`AU7:AU${end}`).setNumberFormat('0');s.getRange(`AR7:AR${end}`).setNumberFormat('yyyy-mm-dd');s.getRange(`AS7:AS${end}`).setNumberFormat('yyyy-mm-dd hh:mm');s.getRange(`B7:H${end}`).format.horizontalAlignment='right';
 s.getRange(`B7:H${end}`).format.fill='#EEF3FA';s.getRange(`I7:P${end}`).format.fill='#F3F5F7';s.getRange(`Q7:W${end}`).format.fill='#EDF4ED';
 s.getRange(`Y7:Y${end}`).conditionalFormats.addCustom(`ABS(Y7)>0.00001`,{fill:'#FBE3E3',font:{color:'#A52828'}});s.getRange(`AP7:AP${end}`).conditionalFormats.addCustom(`ABS(AP7)>0.000001`,{fill:'#FBE3E3',font:{color:'#A52828'}});
 const last=end+2;cell(s,last,1,n===96?'1月1日合计':'两日计划合计（非单日收益）');for(let c=14;c<=23;c++)cell(s,last,c+1,`=SUM(${col(c)}7:${col(c)}${end})`,true);s.getRange(`A${last}:X${last}`).format.font.bold=true;s.getRange(`O${last}:X${last}`).setNumberFormat(fmt);
}
cell(day2,104,1,'1月2日合计');
cell(day2,106,1,'执行事务0001 SHA256');cell(day2,106,2,p.provenance.transaction_0001_payload_sha256);
build.getRange('A103:AV103').format.borders={top:{style:'medium',color:'#213B59'}};
const phHeaders=['模型相位起点｜当地','模型相位终点｜当地','所属15分钟起点','相位 d/u/0','相位时长h','净功率MW','充电MW','放电MW','复算起SOC MWh','复算末SOC MWh','原模型起SOC','原模型末SOC','SOC差异 MWh','复算EFC','原模型EFC','EFC差异','AC充电MWh','AC放电MWh','QH序号'];
base(phase,445,19);title(phase,'两日相位｜SOC与循环复算',['相位为模型假设的下调→上调→空闲顺序，时间是按比例展开的模型时刻。','充电=max(−净功率,0)；放电=max(净功率,0)；SOC逐相连续，未取整或修正原值。']);header(phase,6,phHeaders);
const phRows=p.phases.map((v,i)=>[v.serial_start,v.serial_end,p.serials[v.qh_index],v.phase,v.hours,null,null,null,null,null,v.ein,v.eout,null,null,v.efc,null,null,null,v.qh_index+1]);
phase.getRange('A7:S443').values=phRows;
const phasePower=[],phaseEfc=[],phaseCash=[];
for(let i=0;i<p.phases.length;i++){
 const r=i+7,q=p.phases[i].qh_index+7,ref=c=>`'两日价格与决策'!${c}${q}`;
 const f=[`=IF(D${r}="d",${ref('K')}-${ref('N')},IF(D${r}="u",${ref('K')}+${ref('M')},${ref('K')}))`,`=MAX(-F${r},0)`,`=MAX(F${r},0)`,i?`=J${r-1}`:"='原始输入与口径'!$B$5",`=I${r}+E${r}*(G${r}*'原始输入与口径'!$D$5-H${r}/'原始输入与口径'!$D$5)`];
 phasePower.push(f);phaseEfc.push([`=J${r}-L${r}`,`=E${r}*(G${r}*'原始输入与口径'!$D$5+H${r}/'原始输入与口径'!$D$5)/'原始输入与口径'!$H$5`]);phaseCash.push([`=N${r}-O${r}`,`=E${r}*G${r}`,`=E${r}*H${r}`]);
}
phase.getRange('F7:J443').formulas=phasePower;phase.getRange('M7:N443').formulas=phaseEfc;phase.getRange('P7:R443').formulas=phaseCash;
console.log('Phase formulas populated');
phase.getRange('A7:C443').setNumberFormat('yyyy-mm-dd hh:mm:ss.000');phase.getRange('A1:C443').format.columnWidth=29;phase.getRange('E7:R443').setNumberFormat(fmt);phase.getRange('M7:M443').conditionalFormats.addCustom('ABS(M7)>0.000001',{fill:'#FBE3E3'});phase.getRange('P7:P443').conditionalFormats.addCustom('ABS(P7)>0.0000001',{fill:'#FBE3E3'});
wb.recalculate();
console.log('Recalculated');
const values=build.getRange('A7:AV198').values;
let maxCash=0,maxSoc=0;
for(let i=0;i<192;i++){
 const v=values[i],s=p.saved[i];
 for(const [j,k] of [[8,'ein_mwh'],[9,'eout_mwh'],[10,'da_mw'],[11,'fcr_mw'],[12,'afrr_up_mw'],[13,'afrr_down_mw'],[14,'afrr_up_activation_mwh'],[15,'afrr_down_activation_mwh'],[16,'da_eur'],[17,'fcr_capacity_eur'],[18,'afrr_up_capacity_eur'],[19,'afrr_down_capacity_eur'],[20,'afrr_up_activation_eur'],[21,'afrr_down_activation_eur'],[22,'total_eur']]){if(typeof v[j]!=='number'||Math.abs(v[j]-s[k])>1e-5)throw Error(`Mismatch ${i}/${k}: ${v[j]} / ${s[k]}`)}
 maxCash=Math.max(maxCash,Math.abs(v[24]));maxSoc=Math.max(maxSoc,Math.abs(v[41]));
}
if(maxSoc>1e-6)throw Error('SOC mismatch');
const day2Values=day2.getRange('A7:AV102').values;
for(let i=0;i<96;i++)for(let j=0;j<48;j++)if(j!==25&&day2Values[i][j]!==values[i+96][j])throw Error(`Day 2 mismatch ${i}/${j}`);
if(Math.abs(day2.getRange('W104').values[0][0]-p.saved.slice(96).reduce((a,r)=>a+r.total_eur,0))>1e-6)throw Error('Day 2 total mismatch');
const testI=p.saved.findIndex((r,i)=>i>=96&&Math.abs(r.da_mw)>1),testR=testI+7,testS=testI+9,priceAddress=`${rawCols.da_price_eur_per_mwh}${testS}`;
const old=src.getRange(priceAddress).values[0][0],before=build.getRange(`Q${testR}`).values[0][0];src.getRange(priceAddress).values=[[old+1]];wb.recalculate();const changed=build.getRange(`Q${testR}`).values[0][0];if(Math.abs(changed-before-p.saved[testI].da_mw*.25)>1e-6)throw Error('Cash formula change test failed');src.getRange(priceAddress).values=[[old]];wb.recalculate();
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},summary:'formula scan'});await fs.writeFile(path.join(OUT,'formula_scan.ndjson'),errors.ndjson);
console.log(errors.ndjson);
const inspected=await wb.inspect({kind:'table',range:'两日价格与决策!Q101:Z105',include:'values,formulas',tableMaxRows:5,tableMaxCols:10});await fs.writeFile(path.join(OUT,'inspection.ndjson'),inspected.ndjson);
for(const [s,range,name] of [[day2,'A2:G12','day2_prices'],[day2,'I6:P12','day2_decisions'],[day2,'Q6:Y12','day2_cash'],[day2,'Q98:Y104','day2_total']]){const png=await wb.render({sheetName:s.name,range,scale:1.4,format:'png'});await fs.writeFile(path.join(OUT,name+'.png'),new Uint8Array(await png.arrayBuffer()))}
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(path.join(OUT,'RO_100MW_200MWh_20250101_MILP审计.xlsx'));
await fs.writeFile(path.join(OUT,'validation.json'),JSON.stringify({status:'PASS',marketRows:192,dayRows:96,phaseRows:437,maxCashDifference:maxCash,maxSocDifference:maxSoc,formulaChangeTest:'PASS: DA price +1 changes fixed-dispatch DA cash by signed MW*0.25; restored',day1Cash:values.slice(0,96).reduce((a,r)=>a+r[22],0),day2PlanCash:values.slice(96).reduce((a,r)=>a+r[22],0),provenance:p.provenance},null,2));
console.log(JSON.stringify({output:OUT,maxCash,maxSoc,day1Cash:0,day2PlanCash:p.metrics.plan_cash_eur}));
