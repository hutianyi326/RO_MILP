# 罗马尼亚研究数据获取与官方来源清单

日期：2026-09-30。历史目标期：2025-01-01至2026-08-31。配套[研究基线](romania_research_plan_20260930.md)。本轮完成官方入口发现和部分页面内容核对，尚未下载历史原始文件到data/raw/RO，也未验证全期覆盖或批量接口。

状态必须区分“入口发现”“页面内容已读”“样本已落盘”“全期已获取”“语义及质量通过”。本表前两种状态不能等同于后面三种。

## 1. 优先级与下载清单

P0为研究及基础建模必需；P1为多市场模型或完整基本面研究必需；P2为增强解释或可执行策略扩展。优先级不表示已确认该产品存在容量报酬或储能可参与。

| ID/优先级 | 数据或文件 | 要找的字段和原始粒度 | 官方来源/获取路线 | 用途、缺口处理 |
|---|---|---|---|---|
| D01 P0 | 市场和储能法规 | 许可、BSP/BRP、预认证、订单、GCT、持续性、计量、结算、处罚、费用；PDF/网页各历史版本 | ANRE [RO-S09]，OPCOM规则，Transelectrica程序；正式法规原文优先 | 每项规则记录公布、生效、实施时间；新闻仅作线索，正式附件未取到则待确认 |
| D02 P0 | 日前价格和成交量 | 交付起止、价格、币种、MWh/MW、市场状态、原生MTU | OPCOM PZU结果 [RO-S02]；ENTSO-E同口径交叉校验 | 历史期按粒度切换分段；小时成交决策与QH物理层映射，不能产生虚构QH自由度 |
| D03 P1 | IDA逐轮价量 | 拍卖轮次、交付合同、价格、量、报价关门、结果发布、取消/回退 | OPCOM IDA结果 [RO-S03] | 逐轮保留，不能用一个全日日内均价替代多次决策；缺某轮只关闭对应可用交易 |
| D04 P2 | 连续日内成交与报价深度 | 成交时间、交付时间、期限、价格、量、买卖、订单/成交ID；如有则盘口及其时间戳 | OPCOM ID Trades [RO-S04]及正式数据服务 | 公开页面已见价量，不代表拥有全期订单簿；仅有成交均价时做描述统计或显式成交假设 |
| D05 P0联合市场 | 备用容量需求、报价与中标 | 产品、方向、拍卖ID、交付块、需求MW、申报MW、中标MW、各类价格及单位、支付机制 | Transelectrica DAMAS II公共招标 [RO-S07/14] | 先核FCR/aFRR/mFRR映射；区分最高/最低/均价/边际价/逐报价支付，不以均价替代真实清算规则 |
| D06 P0联合市场 | 平衡能量激活与价格 | 产品、方向、激活MWh或平均MW、计价周期、价格、可用/报价容量、需求、结算版本 | DAMAS II [RO-S07]，ENTSO-E平衡栏目作交叉验证 | 明确请求、接受、实际激活和结算量；有价无量不能计算本站激活收益 |
| D07 P0 | 不平衡结算 | 结算时段、系统不平衡量、价格、方向/符号、初版/修订/最终状态 | Transelectrica BRP/PRE结算与DAMAS II；必要时核OPCOM历史结算职责 | 不把aFRR边际价格当偏差价；缺最终价格时只能给有明确限制的口径 |
| D08 P0 | 实际总负荷 | 原生15/30/60分钟、MW、净/毛、区域、修订 | ENTSO-E Total Load、Transelectrica；入口 [RO-S07/12] | 保留原生分辨率；小时值映射到QH只作恒定功率假设并标记 |
| D09 P0 | 分技术实际发电 | 核、煤/褐煤、燃气、水电、抽蓄发电与抽水、风、光、生物质及其他；MW/MWh | ENTSO-E Actual Generation per Production Type、Transelectrica [RO-S12/13] | 核对净/毛、分布式和自发自用覆盖；缺失不当0，不把计划值当实发 |
| D10 P1 | 装机与储能规模 | 2023/2024/2025年末、2026最新可得截面；分技术MW、储能MW/MWh及在运状态 | Transelectrica年报 [RO-S13]、ANRE统计、ENTSO-E装机 | 许可/规划容量不能当已投运；2026不冒充完整年度；支持最新ES第7章深度 |
| D11 P1 | 跨境物理与商业交换 | 按边界方向、时间、MW；物理流、计划、NTC/ATC分别记录 | ENTSO-E，Transelectrica边界/NTC入口，OPCOM ATC [RO-S01/12] | 净进口符号和区域一致；拥塞分析按耦合机制版本，物理流不替代商业计划 |
| D12 P1 | 市场年报/月报 | 现货与平衡价量规模、活跃主体数、装机和负荷统计 | OPCOM统计菜单、ANRE监测、Transelectrica [RO-S01/09/13] | 用于总量对账，不把月均价补成逐时价格，也不将多市场重复交易量相加成用电量 |
| D13 P0费用 | 费率与免征规则 | 交易费、网络输配费、系统服务费、回送/损耗/自用电、固定费、VAT口径、生效期 | ANRE、OPCOM、Transelectrica/适用DSO [RO-S08/09] | 正式费率表及适用规则一起取；聚合合同未获得则参数化，不能默认真实为0 |
| D14 P0换算 | EUR/RON汇率 | 日期、报价方向、单位、发布日、非工作日适用规则 | 罗马尼亚央行BNR官方历史汇率；本轮仅定位月报候选[RO-S15] | 不用当前汇率倒算全历史；区分账务结算汇率与研究展示换算，时间序列待取得 |
| D15 P1 | 注册名册与主体关系 | DSO、BSP/FSE、BRP/PRE、聚合商、合格资源、EIC、有效日期 | ANRE/Transelectrica正式名册、ENTSO-E EIC | 代码数、法人、注册资格、活跃主体、资源数量分列；未找到全名册则不声称完整 |
| D16 P2 | 预测与发布时点 | 负荷、风光日前/日内预测，原始发布时点与修订；历史预测价格另行构造 | ENTSO-E和Transelectrica预测栏目 | 为可执行策略准备；事后最终预测不能冒充决策时可见版本 |
| D17 P2 | 水文、检修、天气及燃料成本 | 水库/来水、机组停运、气价/碳价、天气、时间与单位 | TSO/ENTSO-E及对应官方机构，具体接口待发现 | 用于异常价格解释/预测；燃料代理不等于真实定价机组证据 |
| D18 P2 | 聚合报价曲线与边际身份 | 价量档位、接受状态、产品、技术/资源标识及历史映射 | OPCOM Aggregated Curves [RO-S01]；详细报价和身份映射可得性待确认 | 聚合曲线不足以识别某台机组；缺身份时保留残余负荷解释，不强行复制ES setter研究 |
| D19 P0参数 | 储能工程及合同参数 | P、E、AC/DC、可用SOC、效率、辅助用电、并网限额、可用率、退化、循环、合同分成 | 用户项目资料或明确登记的情景假设 | 先符号化P，2h/4h保持同口径；制造商或合同数据不冒充市场法定要求 |

D05—D06为拟纳入平衡收益模型的必要条件；若只做日前基准，仍必须在报告中说明这些市场未被验证，不能将缺失数据计为零收入来推断其经济性。

## 2. 官方入口及证据登记

本表访问日期统一为2026-09-30。无公布日期的动态页面记录“未标明”，不得以抓取日期替代生效日。下列少量直接事实仅支持入口与研究切片，不能代替正式法规逐条核验。

| 来源ID | 机构、标题和URL | 公布/生效信息与定位 | 本轮证据状态 |
|---|---|---|---|
| RO-S01 | OPCOM，[Trades – Results](https://www.opcom.ro/tranzactii-rezultate/en/21) | 动态目录，日期未标明；Day-Ahead / Intra-day / Reports菜单 | 内容已读；可定位DA、IDA、IDCT、曲线和统计入口 |
| RO-S02 | OPCOM，[PZU: Raport PIP si Volum Tranzactionat](https://www.opcom.ro/grafice-ip-raportPIP-si-volumTranzactionat/en) | 动态结果页，按交付日查询；标题及结果区 | 页面已打开；全期下载、字段及历史可用性待抽样 |
| RO-S03 | OPCOM，[Rezultate licitatii IDA](https://www.opcom.ro/rapoarte-ida-rezultate-licitatii/en) | 动态结果页；IDA结果区 | 页面已打开；历史轮次和导出待验 |
| RO-S04 | OPCOM，[ID Trades](https://www.opcom.ro/rapoarte-pi-rezultate-pi/en) | 动态结果页；“Trades concluded”表格，列有Price €/MWh、Volume MWh | 内容已读；所见页面不能证明20个月全量或完整成交时戳 |
| RO-S05 | OPCOM，[Produsele de 15 minute vor fi introduse pe piața de energie electrică pentru ziua următoare](https://www.opcom.ro/anunturi-stiri-comunicate-tip/ro/1425/1) | 公布2025-09-12；正文首段安排2025-09-30交易、2025-10-01交付切换 | 内容已读；这是实施前公告，结合下一项实施后资料使用 |
| RO-S06 | OPCOM，[WEEKLY REPORT 29.09.2025–05.10.2025](https://ns1.opcom.ro/uploads/doc/rapoarte/saptaminal/RSS_2025_40_EN.pdf) | 报告期如标题，单独发布日期未核；第1页DA部分“Beginning with delivery day October 1, 2025”脚注；同页另注明DAM以CET小时交易 | PDF文本已读，支持15分钟切换；需区分源市场时钟和本研究Bucharest展示日；原文件尚未落盘 |
| RO-S07 | Transelectrica，[Daily Reports](https://www.transelectrica.ro/en/web/tel/rapoarte-zilnice) | 日期未标明；页底Daily Reports说明：2024-07-01起转至DAMAS II | 内容已读；[DAMAS II公共入口](https://newmarkets.transelectrica.ro/)为后续重点 |
| RO-S08 | ANRE，[储能回送电量免除重复收费公告](https://anre.ro/comunicat-de-presa-anre-elimina-dublarea-tarifelor-pentru-energia-electrica-stocata-si-reintrodusa-in-retea/) | 公布2025-07-08；“Ce prevede reglementarea”和“Important”段 | 内容已读；回送与损耗/自用边界明确，正式法规及生效日待取得 |
| RO-S09 | ANRE，[Energie electrică](https://anre.ro/participanti-la-piata-de-energie/persoane-juridice/energie-electrica/) | 动态法规目录；Licențe/Autorizări、127/2021及修订、213/2020及修订等条目 | 目录已读；逐法规附件和历史版本待核，目录日期不一致时以正式文本为准 |
| RO-S10 | ENTSO-E，[PICASSO](https://www.entsoe.eu/network_codes/eb/picasso/) | 动态项目页；平台介绍、Accession roadmap和相关文件 | 页面已读；RO实际接入及暂停时间仍待独立证据 |
| RO-S11 | ENTSO-E，[MARI](https://www.entsoe.eu/network_codes/eb/mari/) | 动态项目页；平台介绍与接入资料 | 页面已读；项目成员不等于已投运 |
| RO-S12 | ENTSO-E，[Electricity Market Transparency](https://www.entsoe.eu/data/transparency-platform/) | 动态介绍页；发电、负荷、输电、平衡数据与透明度平台入口 | 内容已读；进入[透明度平台](https://transparency.entsoe.eu/)后再验证RO区域、权限和下载；本轮未测API |
| RO-S13 | Transelectrica，[Rapoarte 2025](https://www.transelectrica.ro/ro/web/tel/rapoarte-2025) | 2025报告目录；具体年报标题、发布日期和表页待下载核验 | 检索定位，尚未作年报数据事实引用 |
| RO-S14 | Transelectrica，[DAMAS Ancillary Services Tender Statistics示例](https://newmarkets.transelectrica.ro/uu-webkit-maing02/00121011300000000000000000000100/tenderStatistics?code=452_2025) | 动态招标详情；code仅作已发现样本，不推导产品/日期 | 页面打开但无可读明细；需浏览器公共导出或官方文档化数据接口再试 |
| RO-S15 | BNR，[BULETIN LUNAR 2025年1月候选月报](https://www.bnr.ro/uploads/2025-03-07buletinlunarnr.012025_documentpdf_545_1741348451.pdf) | 检索到日度汇率章节；发布日期、页码与全期下载待核 | 仅候选线索，不是已验收汇率时序来源 |

正式研究须在每条RO-R规则中补全：机构、原文标题、公布日、生效日、URL、本地原件、章节/条款/页码、原文摘录与中文释义、适用产品/主体/时间、访问日期和审核状态。不得仅给机构主页。

## 3. 样本优先与批量路线

第一批样本建议包括：2025-01-15、2025-03-30夏令时开始、2025-09-30与10-01日前产品切换、2025-10-26夏令时结束、2026-03-29夏令时开始、2026-08-31期末日。上述样本是数据验证设计，实际规则切换还要根据RO-01结果补充；负价与强激活样本在检索后按真实记录挑选。

每个样本先验证DA、IDA、备用容量、激活和偏差的字段与交付时段能否对齐。合格后先取2025年1月、2025年10月、2026年8月三个整月，再扩大到20个月。基本面可以独立获取，但必须单列其覆盖，不能以基本面齐全证明联合市场输入齐全。

下载方式依次考虑：官方公开导出文件、官方文档化API、公共网页结果。遇到登录、付费或权限限制登记所需条件；不把网页可浏览等同于批量授权或接口可用。凭据不写入报告、下载日志或原始响应文件。当前未发送机构询问或申请邮件。

## 4. 保存与字段标准

原始目录建议：data/raw/RO/<publisher>/<dataset>/<retrieved_utc>/。下载不覆盖同名历史文件；修订版新建批次。每批保存manifest，至少包含source_id、原始URL/非敏感请求参数、获取UTC时刻、文件名、SHA256、字节数、原始时间范围、记录数、单位、币种、区域、版本/修订、获取状态及解析状态。

清洗层候选位置为data/processed/RO。每条时序保留：delivery_start_utc、delivery_end_utc、local_time、utc_offset、duration_hours、market/product/direction、value、unit、currency、publication_time、revision_time、source_id、raw_file_hash、quality_flag。容量拍卖另存投标/结果时刻、交付块；交易数据另存trade_time；信息可用时点未知不能填成交付起点。

仅在币种、单位、区域、方向、版本和时间一致时做联结。保留source_value与normalized_value；兑换价和官方原价不可覆盖。以RON为报价/支付的产品和以EUR发布的产品分别核验。

## 5. 数据质量与不可替代规则

1. 时间：UTC键唯一，按真实时长构造当地日预期时段；QH日可为92/96/100段，不统一补成96段。原始CET/CEST不能直接当Bucharest时间。
2. 分辨率：保留小时合同与QH执行层映射；价格复制到四个QH仅是结算映射，不能增加交易自由度；MWh聚合用加总，MW/价格按适用定义加权。
3. 单位：容量价若为RON/(MW·h)需乘交付小时；若为RON/MW/交付块则按块结算，不能再重复乘小时。以字段定义为准。
4. 方向：用手算例验证买卖、上/下调、负价格和偏差符号；净进口为自定义标准时保留原始符号及转换证据。
5. 版本：初步、修订、最终分别保存；历史信息模型只能读当时已发布版本，最终版本用于事后结算。
6. 缺失：不将缺失价格、激活量或容量填0；不能用月均插补成“实际”逐时数据；联合样本取所需字段交集，分模块披露排除区间。
7. 对账：分时价量汇总与官方月报比较，分别解释成交量加权价/算术均价、买卖重复记录、净/毛和计量口径差异。
8. 单站映射：系统总激活量不等于本站激活；容量需求/总报价比不等于单站中标率。公开数据不足时使用明确假设与敏感性，不作为规则。
9. 覆盖：报告预期/实际/有效时段、连续可用区间、完整日数、各月覆盖及数据修订。缺失期不按比例年化，也不把数据缺口当储能停运。
10. 权限与来源：未实测接口、未下载全期、未确认字段统一标记未验证；不以第三方图表覆盖官方空白。

## 6. 下载阶段的交付判据

必须提供原始manifest、数据字典、版本时间线、覆盖矩阵、缺失清单、典型日对账和可用于各模型模块的区间表。每个数据项注明“可支持描述统计/可支持完美信息条件测算/可支持当时信息决策”中的哪一层；三者不能自动互推。
