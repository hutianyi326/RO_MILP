# 样本数据字典与缺失处理

字典用于本轮研究表，不是已批准的生产输入合同。源字段名保留；本轮不批准国家模型配置。机构、URL、获取日期、原件和哈希见source_catalog.csv；publication_time和revision_time未知保持空，绝不填交付起点。

## 公共键和时间

| 字段 | 含义/单位 | 使用要求 |
|---|---|---|
| source_id / raw_file_hash | 回执ID / SHA256 | 匹配raw_manifest；重试新ID，失败回执不删 |
| source_market_date / date | 来源选择的市场日标签 | DA/商业计划CET/CEST，系统/招标EET/EEST；IDCT是交易发生日期标签 |
| source_interval | 原生合同/区间连续编号 | DA pre2025-10-01为小时，之后15分钟；92/96/100按真实日长 |
| delivery_start_utc / delivery_end_utc | 半开区间[start,end)，ISO8601 UTC | API显式字段直接保留；DA按原生日期+编号推导I；区间时长真值，不用当地墙钟相减 |
| local_time / utc_offset | UTC起点转Europe/Bucharest的带偏移显示 / +0200或+0300 | 秋季重复当地小时用UTC区分；不能用不带偏移的local_time当唯一键 |
| duration_hours | (UTC end-start)/3600 | MW×该时长→MWh；价格本身不乘时长成为另一价格 |
| publication_time / revision_time | 记录公开时刻/历史修订时刻 | 目前未知空；元数据全局更新、文档创建、记录lastUpdate分开保留，不作替代 |
| quality_flag | 样本使用限制 | EX_POST_SNAPSHOT、NOT_ASOF_APPROVED、缺值、非提供段、描述性、非BNR等 |

主键按各表定义：DA为source市场日+原生区间；IDA为来源日+轮次+原生QH区间；系统长表为report+UTC起止+product_direction；容量为tender+product_direction+UTC；曲线为源series+side+resolution+Pos+SeqNr。不同供方、方向、报告不可共用单一时间戳去重。没有完整交付日的IDCT不构造UTC键。

## 各源的字段、单位和价格定义

| 原字段/研究字段 | 数量与价格含义 | 币种、时钟、缺失和限制 |
|---|---|---|
| DA price → price_eur_mwh | CSV首行公布market clearing price；EUR/MWh | OPCOM，CET/CEST；负值、真0保留；最新导出历史修订未核 |
| DA volume / buy / sell → source_volume_mw / source_buy_mw / source_sell_mw | 区间功率MW；三列分存 | 不是三个独立可加电量；max关系为样本观察I |
| DA energy_mwh | source_volume_mw×duration_hours，派生I | 预切换一小时、后0.25小时；不存在从小时价格制造QH自由度 |
| ROPEX_DAM_Base Quantity | 日汇总字段标MWh | 10月1日SQ01异常，保留原值，不作当日物理量；其他日允许公布一位小数舍入 |
| XML ClearedEnergy | 原元素无独立单位；100段值与CSV MW相等 | 按同源比对解释，不因名字当MWh或第二机构验证 |
| IDA price/volume/buy/sell | 表头EUR/MWh、MW及日汇总MWh；逐字段有效性 | IDA2单日46段价量有效，buy为“-”保留缺失；电量：volume_MW×0.25 h→MWh；价量乘积：price_EUR/MWh×energy_MWh→EUR。其余样本无数字价格。IDA3前半日不提供，后48段为空值，不填0 |
| IDCT Price / Volume / buy,sell | 单笔成交行EUR/MWh、MWh、表显买卖侧 | 已是MWh，金额不再乘0.25；trade_time/ID空，合同标签不含全日期，描述性 |
| tenderDemand | 每产品方向小时需求MW | EET/EEST；FCR语义须结合E66对称带宽，本站报价另审 |
| tenderSatisfiedDemand | 源比例；UI显示百分数 | 1.039→103.9%仅显示换算；不要直接当103.9倍需求；比例精度无法反推精确中标MW |
| priceScheme | 招标支付机制文字Pay as bid | 平均价不是本站报价/实际发票，不套统一清算 |
| tenderPrice / averageOfferedPrice / averageAcceptedPrice | 不同统计价格；各原字段分存 | UI仅LEI，币种RON，计费分母未完备；正式程序不同字段另对照；禁止金额化 |
| contractedPower | service对象内逐供方/合同结构 | 研究JSON完整保留，未用需求×满足率构造精确中标量；供方法人不是单站资格 |
| activityTimingList | tenderPublishedTime、biddingOpenTime、biddingCloseTime、tenderEvaluatedTime、tenderResultsPublishedTime等原事件 | 当前招标记录的显式UTC时刻为F；不能证明该条值历史当时发布且从未修订 |
| activatedBalancingEnergyOverview: fcr,aFRR_Up,aFRR_Down,mFRR_Up,mFRR_Down,rr_Up,rr_Down | 系统“Activated Balancing Energy”报表MWh | QH、EET/EEST；报表量不等于经审计最终单站结算量；null保留，真0保留，上下不相抵后声称没有激活 |
| marginalPricesOverview: aFRR_Up/Down、mFRR_Up/Down_Scheduled/Direct、rr_Up/Down | 产品方向边际价格报表 | UI仅LEI，分母及终版未知；RON保留，不转EUR，不等于PRE偏差价；mFRR量字段不具相同细分 |
| grossForecastConsumption / grossRealizedConsumption | 毛预测/毛实际MW；各自独立 | QH、EET/EEST；净/毛区别保留。预测vintage未知；lastUpdate不成为实际值可见时点 |
| scheduledExchanges: huro/rohu/mdro/romd/roua/uaro/bgro/robg/rors/rsro | 商业交换计划，按原边界方向存MW | QH、CET/CEST；不是物理流。未构造统一净进口数列或从代码推历史EIC资格 |
| above yearly/monthly/dayAhead/intraday/emergencyHelp/longTerm/commercial/operational | 时间期限/计划组成与汇总字段分别保存 | 同一边界汇总与分项不叠加。null是N/A，0是真0；数值+完整日期不等于当时计划vintage |
| FX OBS_VALUE / TIME_PERIOD | 1 EUR兑换RON；ECB日参考值 | RON/EUR、业务日期；三个月66值，不前填周末；非BNR，不作为交易/结算汇率 |
| curve Qty / PriceAmount / SeqNr / Pos | MW曲线坐标 / EUR/MWh / 点序号 / 原生合同区间序号 | XML MAW/EUR/MWH；15/30/60分钟分开；坐标不是独立成交量，不求和；30行示例非全曲线输出，完整原件保留 |
| curve DocumentVersion / CreationDateTime | 文档版本1 / 创建时间 | 不是公布时刻。区域/订单ID不提供机组燃料身份；102块订单未完整解释接受语义 |
| annual_structure_samples source_value | 原官方年度TWh或截面MW | 不转成原生QH；保留净/毛、许可、试运、prosumer脚注及真实截面时刻。显示0.0为源精度，不推真实无生产 |
| fee_table source_value / normalized_value | 源“26.268”“43.776”“0,125” / 数值26268、43776、0.125 | 管理费RON/主体/年与交易费RON/MWh；标点数值转换I；不当2025历史参数；VAT未填实际税率 |

缺值处理统一：JSON null、HTML“-”和空白留缺失；真0和负值保留；不提供产品单列NOT_OFFERED。HTTP200目录和错误内容不当数字获取成功；获取失败不当历史缺失。多版本获取一律新建原件，当前快照不称最终结算或当时版本。

## 输出表的覆盖含义

coverage_matrix.csv为逐日期×报告/产品/字段的预期、结构实际和有效数字数。actual有模板/结构行不代表numeric有效；IDA实际是全日模板、IDA3 expected是适用48段，二者分母不同已经说明。容量actual只计交付期内行，SQ02记录原件24行及越界/缺失。system_series_samples.csv有64796长表字段行，**不是64796个独立交付区间**；每份报告七日共668个QH。原文件行数、价量表行数、长表行数分别报告，不混用覆盖率。

源异常与处理错误分开：source_anomalies.csv有SQ01一条和SQ02十四条；它们不是“自动检查失败被忽略”。检查验证的是明确选择、异常登记及不补造行为，不证明源数据符合正确市场交付时长。模型联结还需要规则/支付/项目依赖，不能只检查行数。
