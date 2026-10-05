# 罗马尼亚价格数据包 v1：2025-01-01—2026-08-31

发布日期：2026-10-02。审核状态：**独立审核PASS，未关闭P0/P1/P2均为0，主线程验收通过。** 本次交付为价格与辅助输入数据，不含MILP求解器或收益测算。

## 1 使用结论

数据已整理到 [价格数据目录](../../data/processed/RO/prices_v1_20261002/README.md)，可供已确认的RO v1.1条件研究模型读取。**DA完整；aFRR存在少量原始缺口及三相异常；FCR容量从6月7日起有数值价格，独立FCR激活价未获得。** 必须使用随包提供的数据有效标记，不得把空值填零后当成全市场完整输入。

正式期按Europe/Bucharest当地日，608天、58,364个15分钟时段；UTC为`[2024-12-31T22:00Z, 2026-08-31T21:00Z)`。另附当地2026-09-01的96个观察时段，支持既定“两日规划、首日执行”的末窗口，不能计入正式期现金或追加正式年度EFC额度。

| 价格系列 | 数值覆盖QH | 缺失及适用范围 | 本版用途 |
|---|---:|---|---|
| DA日前电价 | 58,364 / 58,364 | 无缺口 | 原生EUR/MWh；保留小时/15分钟合同ID |
| FCR容量价 | 43,292 / 43,872（6月起范围） | 6月1—6日576个QH源字段空；秋季DST缺4个QH；1—5月14,492个QH不在FCR研究覆盖内 | RON/(MW·h)候选均价及EUR代理；有效10,823小时 |
| aFRR上调容量价 | 58,360 / 58,364 | 秋季DST缺4个QH | 平均接受价代理 |
| aFRR下调容量价 | 58,360 / 58,364 | 同上 | 平均接受价代理 |
| aFRR上调激活价 | 58,363 / 58,364 | 2026-08-22当地03:45源字段空 | 保留原始符号，RON/MWh候选及EUR代理 |
| aFRR下调激活价 | 58,363 / 58,364 | 同一个QH源字段空 | 保留原始符号，不预先取负 |
| FCR独立激活价 | 0 / 58,364 | 本接口`fcr`字段全为空；观察日也为空 | 不纳入已确认FCR容量机会价值模型，不填零 |

价格数值覆盖以QH计量，不是可独立下单的合同数。容量源小时均价映射到四个QH，不除以4；收益计算再乘0.25小时。FCR第一条数值价格为当地2025-06-07 00:00，不将6月前六天的空值解释成真实零收益或某一种已证实业务原因。

## 2 下载、重建及核验

F：DA采用OPCOM公开原生CSV；容量采用Transelectrica DAMAS II `tenderStatistics`；激活价格采用`marginalPricesOverview`；辅助系统激活电量采用`activatedBalancingEnergyOverview`。原币保留，BNR官方参考汇率单列。每个输入通过`source_key`连接 [来源登记](../../data/processed/RO/prices_v1_20261002/source_registry.csv) 的完整URL、原件位置、SHA256、实际获取时间及未知的发布/修订时间。

本轮补取20个月激活价、观察日价量与容量、三个接口元数据及容量缺口复查，共30个入选请求；此前一份相同DST复查快照仍保留在原始目录但不重复作为输入。正式DA、容量、系统激活电量复用已留存快照并从原件重新解析。**这是可追溯的组合事后快照，不是全部来源在同一时刻下载，也不是历史事前数据集。** 复用数据的访问日期保持原值，不改成本轮日期。

已执行原件哈希、分页总数、错误对象、完整UTC网格、唯一键、15分钟/小时区间、DA原生序号、小时映射、FX严格前日、原始表重算一致性及缺失传播检查。完整机器结果在 [validation_checks.json](../../data/processed/RO/prices_v1_20261002/validation_checks.json)。原生DA/容量/电量与前轮表格比较无数值差异；新价格逐行保留负价、零价和极值，不插值、不截尾。

I：春季DST容量源文件有5条超出所属拍卖交付区间的记录，沿用已审处理排除并登记于 [source_rows_excluded.csv](../../data/processed/RO/prices_v1_20261002/source_rows_excluded.csv)，避免与次日订单重复。秋季缺口是当地2025-10-26 23:00—24:00（UTC21:00—22:00），FCR和双向aFRR均缺；官方详情复查仍未补齐。6月1日FCR详情亦复查仍为空。源系统上/下调激活电量缺口分别45/46个QH，保留不填。

本版原始aFRR上调价格最小−1,175.617、最大57,524.978 RON/MWh，下调最小−8,001、最大45,777 RON/MWh。这里只报告原件数值；极值被保留不代表其最终结算性质已确认。样本月份统计见 [coverage_monthly.csv](../../data/processed/RO/prices_v1_20261002/coverage_monthly.csv)。

## 3 MILP数据门禁

沿用RO v1.1 M10—M11，不改已审核数学口径：

- 原始激活比例：`系统激活MWh / (系统已接受容量MW × 0.25h)`。系统合同容量代理为`tenderDemand × tenderSatisfiedDemand`，不是本站中标量，也不是全部报价量。
- 50个QH的比例不可计算，另1,739个QH比例和超过1；原始比例保持原状，不归一化。新发现的激活价空值落在既有不可计算QH中，因此没有额外增加原始三相失效数。
- 两方向价格、数量、比例任一失败，关闭覆盖该QH的整个小时的双向新aFRR订单。1,789个原始失效QH扩展为**1,216个禁用小时、4,864个QH**；其余**13,375小时、53,500个QH（91.6661%）**通过数据门禁。不能把此前97.02%的比例可用率当成最终订单可用率。
- DA仍可覆盖完整正式期，aFRR失效不删掉时间行、不重置SOC、不关闭其他有效市场。FCR仅10,823个有效小时进入容量扩展。
- 观察日所有已纳入模型的价格均有值，FCR24小时有数据；aFRR三相门禁通过22小时、另外2小时禁用。FCR激活仍为空。

这些是**数据门禁**，不是电站实际资格、情景开关、逐日p系数或冻结承诺检查的替代品。后续实现仍须应用M03/M07/M09：若已有非零冻结订单与缺失冲突，应阻断相应轮次，不能用关闭新订单抹去旧义务。未获得真实报价分母，p=1/0.8/0.6仍为用户批准的外生容量现金敏感性，不放入数据表冒充观测中标率。

## 4 事实、解释与假设边界

F：官网原始价格、价量空值、区间、接口字段和BNR参考汇率属于可复核的来源事实；2025-10-01交付起DA改15分钟由OPCOM公告支持。

I：UTC/QH对齐、来源空值与缺小时区分、覆盖统计、合同量乘积和三相比值为本次处理结果。

A：容量`averageAcceptedPrice`按RON/(MW·h)候选解释、激活字段按RON/MWh候选解释并用于条件研究代理；不是本站pay-as-bid发票或已确认最终价。所有RON价除以“交付Bucharest当地日期之前最近的BNR参考值”形成EUR代理。这是批准的研究换汇假设，不是实际结算换汇规则，也不证明精确发布时刻已知。

A：容量以整小时研究订单共用决策，属于RO v1.1 A04假设；API小时统计粒度本身不证明真实历史容量合同粒度。FCR仅容量机会价值，静态30分钟能量缓冲，不模拟频率激活电量、损耗或额外循环；DA+aFRR继续严格三相。成果允许完善后续输入输出规范及MILP实现，不批准现实交易、净收益或全期所有市场的无缺失结算测算。

## 5 官方来源及定位

| 机构 / 资料 | 发布或适用时间 | 定位、访问与支持范围 |
|---|---|---|
| OPCOM，《Mcp and Traded Volume》原生CSV | 源市场日2024-12-31至2026-09-01，首发时间未给 | `Romania`行的序号和价格列；访问时间逐件见source_registry；[接口示例](https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv/01/09/2026/en?resolution=15) |
| OPCOM，15分钟产品公告 | 发布2025-09-12；交付生效2025-10-01 | 正文；此前2026-10-02已取证，[官方公告](https://www.opcom.ro/anunturi-stiri-comunicate-tip/ro/1425/1) |
| Transelectrica，DAMAS II公共容量统计与详情 | 交付日见原件；首次发布/修订未知 | `itemList[].tenderServiceList[].tenderStatistics.timeIntervalList[]`的`averageAcceptedPrice/tenderDemand/tenderSatisfiedDemand`；[接口](https://newmarkets.transelectrica.ro/usy-durom-publicreportg01/00121002500000000000000000000100/publicReport/tenderStatistics)；访问逐件登记 |
| Transelectrica，Marginal prices overview / Activated balancing energy overview | 正式期及2026-09-01；首次发布未知 | `itemList[].timeInterval/aFRR_Up/aFRR_Down/fcr`，`pageInfo`；[价格页面](https://newmarkets.transelectrica.ro/uu-webkit-maing02/00121011300000000000000000000100/marginalPricesOverview)；价格新取2026-10-02，电量复用日期见登记 |
| Transelectrica，2025年8月STS监测报告 | 报告期2025-08；发布日期未知 | PDF p4/5/8：FCR日采购、lei/hMW、算术均价与加权价区分；前轮2026-10-02取证，[官方PDF](https://www.transelectrica.ro/documents/10179/18723178/2025-08-STS-Raport.pdf/1c2cc5bf-e0f5-48ff-bc12-2019c164623c) |
| ANRE，127/2021附件合并规则 | 基础文本2021-12-08；对应历史合并版本 | Art.39、63、91—93，能量报价范围/单位/方向的候选依据；前轮2026-10-02访问，[官方法规](https://legislatie.just.ro/Public/DetaliiDocument/280280)；不据此宣称全历史最终现金口径 |
| BNR，年度官方汇率XML | 2024/2025/2026年度`Cube@date` | `Rate@currency=EUR`；原件访问逐件登记，[2025原件](https://curs.bnr.ro/files/xml/years/nbrfxrates2025.xml)；前一发布日期使用是A，不是F |

完整既有规则证据与版本限制见 [RO v1.1 §20](../romania_milp_20261002/romania_milp_mathematical_formulation.md)。本包关闭“尚未下载全期aFRR激活价格和观察日”的采集事项；没有关闭源缺失、字段最终性、真实容量总报价量、资格、历史事件时表、FCR真实频率轨迹及费用问题。原数学文档保留其当时版本，不回写历史结论。

## 6 独立审核

由`research_reviewer`（gpt-6-astra / medium）只读核对，主线程修复并验收，最终PASS。已独立复核682份原件哈希、原生价量与宽表、FX和Decimal三相/小时门禁。正式结论与两项问题闭环见 [审核与验收记录](review_and_acceptance.md)；主线程158,621项自动检查全部通过，独立检查不以自动结果替代。
