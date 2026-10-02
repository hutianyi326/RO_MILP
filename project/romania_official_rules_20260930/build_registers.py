"""Build research-only evidence registers. No production model inputs."""
from pathlib import Path
import csv, hashlib, json
ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent
OUT=ROOT/'countries/RO/rules_20260930'
RAW=ROOT/'data/raw/RO/rules/20260930'

# (publication/approval, application, authoritative document location, status)
DETAILS={
'E14':('2021-12-17','分条；2024及2025修订覆盖','Order127/2021及附件1 BSP、附件2 BRP','官方托管PDF；含混合版本，不是完整最新合并版'),
'E15':('2024-05-30','2024-06-01；各章另见art.I','Order18/2024 p1—2 art.I、VI','正式修订令'),
'E16':('2024-08-29','2024-09-01生效；art.I—IV自2024-10-01；art.V自2025-01-01','Order60/2024 p1—3 art.VIII—IX','正式修订令'),
'E17':('2025-03-27','分条2025-04-01/05-01及附带条件','Order9/2025 art.I公式PDF p2—3；起效art.IV—V PDF p4／公报p15','正式修订令；公式和起效原图核对'),
'E18':('2025-04-29','Order124指定条款自2027-01-01','Order14/2025 p1','正式延迟实施令'),
'E19':('2025-03-26批准令公布；PDF另有2025-04-08打印标记','2025-03-26起；后续修订另见E20/E21/E51','Regulamentul din12.03.2025 art.6—10','ANRE官方托管再版；批准令E48'),
'E20':('2025-06-19','按正式公布及过渡条文','Order26/2025 p1—2','正式修订令'),
'E21':('2026-05-25','按正式公布及过渡条文；独立储能担保适用待确认','Order16/2026 art.I—VIII p1—3','正式修订令'),
'E22':('2023-01-19','按Order3/2023及附件','Order3/2023及储能接网技术规范','正式技术规范'),
'E23':('2025-07-10','公布后及网络方实施程序','Order56/2025 art.3—5、7、11','正式方法；与上位法分别记录'),
'E24':('2025-09-30 Rev7封面日期','QH交付自2025-10-01；异常模式另查','PZU操作Rev7 §6.2、6.3.44，p13—22','正式操作程序；封面/实际运行分开'),
'E25':('2025-09-30批准号36；下载路径日期2025-10-01不作为生效日','对应PZU Rev7','Aviz36/2025 p1','正式批准页'),
'E26':('2024-09-09批准号17；Rev5','后续修订与全历史GCT待确认','IDCT/IDA Rev5 §7.1.4、7.5、8.1.1','正式操作程序；不证明全期未变'),
'E27':('2025-09-30 Rev0','历史起止与旧版另查U04','Incasari-Plati PZU/PI Rev0','正式统一现金程序'),
'E28':('2026-07-31程序日期','旧版不可回填；U04','PZU/PI担保程序','当前正式程序'),
'E29':('当前注册压缩包；准确历史公布未标明','历史版本待确认U04/U11','注册程序Rev17及附件','当前官方注册包'),
'E30':('2021-07-21','与后续正式修订配套','Order89/2021及逐产品测试附件','正式技术资格程序'),
'E31':('2023-12-08文件版本；官方页说明自2024-07-01','2024-07-01实施说明；后续版本仍核','PO138 §8.4及产品报价表','官方正式程序链接；无签章DOCX'),
'E32':('2023-12-08文件版本；官方页说明自2024-07-01','同E31；本地/欧盟模式分开','PO240 §8.1.5—6、8.2','官方正式程序链接；无签章DOCX'),
'E33':('2024标题；准确签署与适用日未标明','待可读正式合同U06','FCR合同旧式二进制DOC','原字节已保存；扩展名误识别html；自动文本禁止作证据'),
'E34':('2025-12-22','咨询；不作为正式实施','储能FCR咨询公告p1','咨询稿入口'),
'E35':('2026-02-26更新','接入计划，不是实际投产','PICASSO roadmap p2脚注Transelectrica','正式路线图；非实际go-live'),
'E36':('2026-02-26更新','接入计划，不是实际投产','MARI roadmap p2 Romania行','正式路线图；新日期2026-11原图核对'),
'E37':('2025-09-12','交易2025-09-30、交付2025-10-01','OPCOM QH启动公告正文','正式部署公告'),
'E38':('动态官方登记页；历史公布未标明','逐主体登记日期需项目证据','PRE登记流程','官方操作说明'),
'E39':('官方页注明2024-07-01起实施','2024-07-01及后续','FSE登记说明/协议及技术资格','官方操作说明'),
'E40':('2025-10路线图更新','预计，不是go-live','MARI Romania行','正式历史路线图'),
'E41':('2025-10路线图更新','预计，不是go-live','PICASSO Transelectrica脚注','正式历史路线图'),
'E42':('2026-04-09','确认程序2026-04-07公布','FCR储能正式程序公布公告p1','正式公告'),
'E43':('2026-04-07由E42确认','自正式公开；此前/追溯资格U07','TEL07.51 Ed.I Rev0 §8.10—11、8.18','正式专项技术程序；咨询稿不得替代'),
'E46':('基础2021-12-17；合并历史列至2025-12-18','按逐条历史版本','BSP现行网页 art.56—63、64—69等','政府法规门户；网页核对，非本地下载原件'),
'E48':('2025-03-26','许可条例批准','Order6/2025 p1','正式批准令'),
'E49':('动态公告索引；逐条日期','仅作发现入口和修订记录线索','TSO新闻索引','官方动态入口'),
'E50':('网址列2025；封面精确批准/生效日期未确认','网络方实际执行日期U09','DSO减免程序 §5.1、5.2.1.1 p6—7；p9跨月、p10 §5.3.1表3','官方DSO执行文本；不代表所有网络方'),
'E51':('2025-12-18；签署2025-12-16','2025-12-18','Order80/2025 p1—2 art.I、V','正式修订令；不是aFRR时限改版来源'),
'E52':('基础2021-12-17；合并含2025-12-18','逐条历史及附带条件','BRP art.147—167、187—195、221—227','政府法规门户；网页核对，非本地下载原件'),
'E54':('同E14','同E14','Order127/2021替代官方URL','与E14字节及SHA256相同'),
'E56':('2026-03官方路径；月度报告2025-12','用于制度运行确认，不作决策时输入','ANRE监测 p4及日前/日内章节','正式监管监测报告'),
'E57':('2025年度报告；精确首次公布日未标明','记录历史运行事件；非历史决策输入','OPCOM年度报告 IDA/MNA专题','官方年度报告'),
'E58':('2025-10上旬周报；精确发布日期未标明','2025-10-01交付已实际QH','RSS2025_40_EN p1脚注','官方运行见证；未开展数据样本分析'),
'E59':('2026-08-26','按正式公布','Order55/2026 p1—2','NEMO指定/重新指定修订；非BESS产品收益'),
'E60':('2026-08-26','危机触发及实施程序条件','Order54/2026附件art.1—2','正式消费灵活性规章；不批准通用BESS收入'),
'E61':('2025-07-29','按正式公布及条款','Order58/2025','正式电力市场组织修订；本轮仅外围登记'),
'E62':('2026-05-25','分条过渡，实际项目适用U02','Order15/2026 art.I—VI','正式接网修订'),
'E63':('2024-08-02；以官方目录记录','过渡实施待全文确认U02','Order53/2024','扫描原件取得；本轮仅目录级未作为具体约束依据'),
'E64':('2025-12-19；以官方目录记录','过渡实施待全文确认U02','Order79/2025','扫描原件取得；本轮仅目录级未作为具体约束依据'),
'E65':('2024-11-26','上位法；执行配套程序分别核','OUG134/2024 art.I Law123 art.66³','政府法规门户网页核对；未本地下载原件'),
'E66':('封面2024-11，文件名含2024-10-09；精确批准/部署日未确认','当前官方链接所载；历史部署U05','TEL04.01 Ed.I Rev1：Depunerea ofertelor、Contractarea şi derularea contractelor及Participanţii la licitaţie','官方托管采购程序RAR；原扩展名误判html，解出的DOCX可读'),
'E67':('TEL04.05 Ed.I Rev2；精确批准/部署日期未确认','当前官方链接所载；历史部署U05','采购程序 §8.3、8.4、8.5.3—5，成员PDF p10—11','官方托管采购程序RAR；原扩展名误判html，解出的PDF可读')
}

def publisher(url):
 if 'anre.ro' in url:return 'ANRE'
 if 'opcom.ro' in url:return 'OPCOM'
 if 'legislatie.just.ro' in url:return 'Romanian Ministry of Justice / Portal Legislativ（发布ANRE/政府法规）'
 if 'transelectrica.ro' in url:return 'Transelectrica'
 if 'distributieoltenia.ro' in url:return 'Distributie Oltenia'
 if 'entsoe' in url or 'eepublicdownloads' in url:return 'ENTSO-E'
 return '待核'

rows={}
for f in sorted(WORK.glob('sources_batch[1-6].json')):
 for row in json.loads(f.read_text(encoding='utf-8-sig')):rows[row['id']]=row
rows['E65']={'id':'E65','title':'OUG134/2024 amendments to Law123/2012 storage definitions and exemptions','url':'https://legislatie.just.ro/Public/FormaPrintabila/00000G2DQ7RI2D3EJ451USLG3UOCNC9E'}

sources=[]
for sid,row in sorted(rows.items(),key=lambda x:int(x[0][1:])):
 mfile=RAW/sid/'metadata.json'
 meta=json.loads(mfile.read_text(encoding='utf8')) if mfile.exists() else {}
 dates=DETAILS.get(sid,('官方网页历史日期未标明','未作为已确认历史参数','来源入口或备选法规链接','发现/备选入口'))
 web=sid in {'E46','E52','E65'}
 sources.append(dict(source_id=f'RO-S{int(sid[1:]):03}',evidence_id=sid,publisher=publisher(row['url']),document_title=row['title'],publication_or_approval_date=dates[0],effective_or_operational_date=dates[1],url=row['url'],location=dates[2],access_date='2026-09-30',formal_status=dates[3],acquisition_status='ORIGINAL_DOWNLOADED' if meta else ('WEB_VERIFIED_ONLY' if web else 'NOT_DOWNLOADED_OR_UNUSED'),original_path=meta.get('path',''),sha256=meta.get('sha256',''),retrieved_utc=meta.get('retrieved_utc',''),derived_path=f'project/romania_official_rules_20260930/extracted/{sid}.txt' if meta else ('project/romania_official_rules_20260930/extracted/legal_web_details.json' if web else ''),notes='二进制DOC，自动提取禁用' if sid=='E33' else ('扫描件OCR为派生文本；关键数值需原图' if meta and meta.get('extracted_characters',9999)<500 else '')))

# Rule ID, subject, fact, source IDs, exact location, applicability, limitations.
RULES=[
('001','机构','ANRE监管、Transelectrica调度/平衡、NEMO组织现货，PRE承担组合偏差','E38|E39|E14|E26','官方登记页；BSP art.1—6；IDCT §7.1.7—10','研究期主要职责；逐主体登记另核','U10|U11'),
('002','NEMO','BRM是另一NEMO，耦合日前2024-11-19、IDCT2024-05-22、IDA2025-08-05运行','E56','PDF p4，现货章节','列明实际事件','U11'),
('003','技术准入','接网规范、法人登记和逐产品资格是不同条件','E22|E30|E39','Order3/2023；Order89/2021；FSE登记页','分别按适用版本和项目资格','U02|U07'),
('004','历史FCR','FCR容量第IX章自2025-06-01适用','E15','PDF p1 art.I(2)修改Order127 art.7(4)','2025-06-01起；此前U05','U05'),
('005','版本控制','ANRE托管Order127 PDF有旧容量条款，需由修订令覆盖，不可当统一现行版','E14|E15|E54','E14 p15 art.161—162对照E15 p1；原件同SHA','条款级版本核对','U03|U05'),
('006','许可阈值','最大出口>1MW授权要求与总功率<1MW商业许可例外不等价；独立储能列单独许可种类','E19|E48','条例art.6—7、10(1)(i)、10(3)(b)；批准令p1','2025-03-26新条例及后续修订','U01|U02'),
('007','许可修订','2025/2026有材料、期限和担保修订，具体项目过渡另查','E20|E21','Order26；Order16 art.I新增19¹及art.II—VIII','分别公布2025-06-19、2026-05-25','U02'),
('008','试运行','Order80对临时PRE、PE测试期间报价及试运行电量支付作特别规定；400RON不是商业储能普通上限','E51','PDF p1—2 art.I修改BRP136—142¹；art.V','2025-12-18；此前Order60文本另核','U01|U02'),
('009','FCR程序','TEL07.51正式储能FCR程序2026-04-07公布；2025-12-22为咨询','E34|E42|E43','E42 p1；E43封面、§8；E34 p1','正式公开日；历史过渡未知','U07'),
('010','日前粒度','日前交易2025-09-30启动QH，2025-10-01交付15分钟；之前小时','E37|E58','启动公告正文；E58 p1脚注','以交付日2025-10-01分段','U04'),
('011','日前关门','PZU Rev7正常耦合报价关门12:00市场CET；解耦另行公告','E24','§6.3.44 PDF p22','Rev7；旧版逐条另核','U04'),
('012','日前订单','Rev7允许15/30/60分钟报价，最小0.1MW；本地RON报价转换耦合EUR','E24','§6.2、6.3；PDF p13—22','Rev7及适用日','U04'),
('013','IDA时表','IDA1 D-1 15:00；IDA2 D-1 22:00全天；IDA3 D10:00覆盖市场12—24','E26','§8.1.1 PDF p26','Rev5市场CET含DST','U04'),
('014','IDC时表','Rev5 IDCT次日合同D-1 15:00开放，T−60分钟关闭','E26','§7.1.4 PDF p17','仅此版本；不作未核全期常数','U04'),
('015','IDC报价','EUR报价两位小数，MW一位小数，最小0.1MW，正零负价格，RON现金收付','E26','§6.21 p17；§7.5 p21','Rev5；价限历史另核','U04'),
('016','市场时钟','交易CET市场时钟包含欧洲夏令时，市场日与罗马尼亚民用日不同；DST92/100QH','E26|E58','§2.3、6.19—20 p17；E58脚注','按实际日期时区转换','U04'),
('017','IDA事件','OPCOM IDA启动2024-06-13；边界整合2025-03-18；MNA IDA2025-08-05','E57','IDA/MNA章节及商业实施专题','各事件不同，不合并','U04|U11'),
('018','现货现金','统一现金程序仍分PZU/IDCT/IDA、负价及月度调整；担保是支付能力条件','E27|E28|E29','现金Rev0各市场章节；担保程序；注册包','当前程序与旧版历史分开','U04|U09|U11'),
('019','容量数量','平衡容量最少/步长1MW，采购菜单含QH/1h/4h/一天，不代表实际所有块启用','E14|E67','BSP art.150表7、152—153，PDF p15；E67 §8.3—5','第VII章适用2024-09-01起；实际公告另核','U05|U06'),
('020','容量定价','平衡容量升价/同价时间排序，边际笔可部分接受；每笔按接受报价支付','E15','PDF p1 修改BSP161—162','Order18生效2024-06-01；容量专章2024-09-01','U05|U06'),
('021','FCR定价','FCR升价/时间排序，最后补足一笔不能部分接受；按接受报价支付','E15','PDF p1 修改BSP213—214','FCR第IX章2025-06-01起','U05|U06'),
('022','容量履约','中标容量对应能量报价义务；无容量合同也可按条件报价；可用性确认及不可用处罚','E14','BSP39、165、167、173、177；182—186','容量条文按各章日期；具体合同另核','U05|U06|U07'),
('023','FCR方向','FCR对称；最低每方向1MW；单方向R与总带宽2R须区分','E14|E43|E66','BSP202、204；TEL07.51 §8.11(b) p12；E66报价章节','第IX章及认证程序相应日期；报价程序历史部署另核','U05|U06|U07'),
('024','FCR技术','储能认证每方向1—20MW整数；响应≤2秒开始，15秒50%、30秒100%；30分钟测试/SOC与15分钟检查各有语境','E43','§8.10—11 p11—12；§8.18 p15','2026-04-07正式公开；历史过渡另核','U07'),
('025','aFRR时限','完全激活7.5分钟至2025-12-17；2025-12-18起5分钟；1MW最小/步长、15分钟有效','E14|E46','BSP art.62表5 PDF p9；门户同表','产品表明确分段；非Order80改写','U07|U08'),
('026','mFRR/RR技术','mFRR FAT12.5分钟、至少1MW、最小满请求交付5分钟，可直接/计划；RR FAT30分钟、至少1MW','E14|E31','BSP56、59—61表1—4；PO138产品表','按合格产品；不推定项目资格','U07'),
('027','能量关门','本地RR T−50；mFRR/aFRR T−25分钟','E31|E14','PO138 §8.4；BSP42、69','2024-07-01实施说明；现货及容量时表另列','U04|U05'),
('028','激活和价格','标准产品按承诺能量及适用边际价格；本地RON、欧盟EUR；方向/负价决定付款方向','E14|E32','BSP61/63价格表、64—65、90—93；PO240 §8.2','本地与欧盟、标准与拥塞交易分开','U08|U10'),
('029','EU路线图','2026-02-26 MARI罗马尼亚新计划2026-11，PICASSO预计2027-04；不是实际go-live','E35|E36','均PDF p2 Romania/Transelectrica行和脚注','路线图更新日；实际事件U08','U08'),
('030','电量桥接','净合约含PE承诺量及规定FCR电量；净计量减净合约确定PRE偏差','E52|E14','当前门户BRP147—158、167；E14 BSP237—238及BRP基础条款对照','按PRE/ID；历史完整版本及跨PRE转移另记','U03|U10'),
('031','偏差版本','Order9初始/最终价格修改自2025-04-01；估算价格修改自2025-05-01','E17','art.IV规定art.I(4)—(6)起效；PDF p4／公报p15；art171附带条件art.V同页','分条日期；旧版U03','U03'),
('032','最终单/双价','最终单价要满足art.195系统条件，另有缺额/盈余双价及价格限界','E17','修改BRP195 PDF p2—3；公式原图','2025-04-01起修改；旧版另核','U03'),
('033','月度调整','PRE偏差与月度额外中性化/调整费用分开，不能只保留估算价×本站偏差','E14|E52','BRP221—227及VM/VMA、更正章节','最终公布版本用于事后结算，非决策时信息','U03|U10'),
('034','FCR电量','FCR激活能量按规定计算并进入PRE净合约；这两条不提供独立能量现金支付价格','E14','BSP第IX章237—238 PDF p19；容量罚则239—240另列','第IX章适用及具体合同另核，不套FRR边际价','U05|U06|U07'),
('035','费用上位法','Law123 art.66³列储能TL/配电/系统服务及绿证/联产贡献减免','E65','OUG134/2024 art.I新66³','2024-11-26公布；执行配套另查','U09'),
('036','费用方法','Order56减免针对存储后返送合格电量；DSO独立储能按月Eex−Ei，期末存量后月返送可产生负计费调整电量','E23|E50','Order56 art.3—5、7、11；DSO §5.2.1.1 p6—7、p9跨月、p10 §5.3.1表3','方法2025-07-10公布；DSO实际执行日期、费率及项目另核','U09'),
('037','其他费用','Order56列举不能证明TG、CfD、VAT、税/商业费用都为零','E23','art.4—5费用范围对照','适用性待查，未设模型零值','U09'),
('038','新增消费机制','Order54仅特定可调度消费等对象及危机场景；参加平衡服务终端客户有排除','E60','附件art.1—2 PDF p1—2','2026-08-26公布；触发与实施另核','U12'),
('039','未来规则','Order14将Order124指定条款应用延至2027-01-01，不回填研究期','E18','art.I PDF p1','研究期不提前应用；art171交叉条件U03','U03'),
('040','FCR采购字段和条件','FCR报价数量为每方向MW、价格lei/hMW；有限能量资源维持30分钟；供方需PRE登记及EIC等条件','E66','TEL04.01 Ed.I Rev1：Depunerea ofertelor、Contractarea şi derularea contractelor、Participanţii la licitaţie','当前官方托管程序；全历史部署及项目资格不由此批准','U05|U06|U07'),
('041','容量采购事件及单位','容量程序要求公告列明开关门及结果时刻；FRR/RR §8.5.3报价文字仍为lei/MWh','E66|E67','FCR Determinarea cantităţilor、报价章节；E67 §8.4.2、8.5.3 成员PDF p11','当前操作文本；实际历史事件与FRR/RR现金单位另核','U05|U06'),
]
lookup={r['evidence_id']:r for r in sources}
rules=[]
for rid,subject,fact,sids,loc,app,unresolved in RULES:
 ss=[lookup[x] for x in sids.split('|')]
 rules.append(dict(rule_id='RO-R'+rid,layer='F',topic=subject,rule_fact=fact,evidence_ids=sids,publishers=' | '.join(s['publisher'] for s in ss),document_titles=' | '.join(s['document_title'] for s in ss),publication_or_approval_dates=' | '.join(s['publication_or_approval_date'] for s in ss),effective_or_operational_scope=app,urls=' | '.join(s['url'] for s in ss),locations=loc,access_date='2026-09-30',confirmation_status='VERIFIED_WITH_STATED_SCOPE',unresolved_ids=unresolved,modeling_approved='false'))
for filename,data in [('sources.csv',sources),('rule_register.csv',rules)]:
 with (OUT/filename).open('w',encoding='utf-8-sig',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
(WORK/'register_build_receipt.json').write_text(json.dumps({'sources':len(sources),'rules':len(rules),'originals':sum(s['acquisition_status']=='ORIGINAL_DOWNLOADED' for s in sources),'web_only':sum(s['acquisition_status']=='WEB_VERIFIED_ONLY' for s in sources)},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'sources':len(sources),'rules':len(rules),'originals':sum(s['acquisition_status']=='ORIGINAL_DOWNLOADED' for s in sources)},ensure_ascii=False))
