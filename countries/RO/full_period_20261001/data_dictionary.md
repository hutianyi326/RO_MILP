# 原生与派生字段、时钟、单位及用途

本批次为事后描述研究，所有字段的model/as-of批准均为false。源发布/修订时刻未知则空；retrieved_utc仅为获取时刻。原生文件逐行源ID、哈希、URL及格式见raw_manifest.json；派生统计按对应原生CSV和分组键追溯，文件哈希在审核快照中冻结。

| 文件/字段 | 原始粒度及计量 | 时间/处理 | F、I、A、U及禁止用途 |
|---|---|---|---|
| da_native.csv price_eur_mwh、volume_mw、buy/sell | F：CSV EUR/MWh、MW；2025-10-01前60min后15min | F：源Brussels日，含一个完整边界源日；native_contract_id唯一 | I：energy_mwh=MW×实际合同小时；不能把量当MWh；38,711是研究期源日原生区间数，不是目标QH数 |
| da_qh_descriptive_alignment.csv | I：58,364个目标QH描述映射 | UTC半开目标范围；目标当地时间Bucharest；原生合同ID保留 | 小时价复制4段只作等时长统计；目标映射涉及38,708个不同源合同，边界不等于源月；无QH独立成交自由度 |
| da_monthly_statistics.csv | I：Bucharest目标月时间/成交量加权，分位数/总体标准差 | 同权QH=时长加权；MW×.25得权重 | official_reconciliation采用Brussels源月；不把两种月界差异归为错误 |
| price_windows* | I：每8/16个实际连续QH均价；每日极差及全期重叠窗口 | 日版限同当地日；全期版允许跨日；高低极值先后未约束 | A：2h/4h观察窗口；不乘P/E/效率，不称收入、循环或设备排名 |
| dailyConsumptionOverview.csv grossRealizedConsumption | F：系统实际毛消费MW，QH | F：UTC区间/Bucharest源日；全部58,364个实际数值 | I：电量=MW×.25；grossForecast另列为取得日存储预测；source_last_update不提供历史vintage |
| scheduledExchanges.csv | F：Brussels源日QH，各边界/分量MW | 额外12.31源日补Bucharest首小时；保留80个原始分量列 | I：commercial净进口=五进口−五出口，逐侧min_count=5；非物理流，分量不重复相加 |
| activatedBalancingEnergyOverview.csv | F：QH MWh，方向原名aFRR_Up/Down等 | F：UTC/Bucharest；每字段numeric/null/zero分别计 | I：MWh直接求和；系统量不代表本站；不存在对null补0或乘.25；价格及其最终性未核 |
| capacity_statistics.csv | F：FCR/aFRRUp/Down/mFRRUp/Down需求MW、满足率及LEI统计价，小时 | 仅tender原生交付期内记录；越界保留原件而排除；5个秋季产品日少1h | U：LEI价格分母、帯宽及支付样本；tenderPrice/offer/accept不互代；不换汇、不算支付；价格方案不能覆盖逐报价合同 |
| capacity_provider_native_filtered.csv | F：contractedPower原始供方label、power及timeInterval | 与交付期内容量键多对一相交，564,677个供方行 | I：ΣMW与需求×比例复算；12,125小时未相符，不强制校正；provider不是资源/法人合并映射 |
| capacity_provider_label_shares/concentration.csv | I：仅57,202个供方复算吻合产品小时，ΣMW×h占比；HHI=Σshare²×10000 | 逐月逐产品，实际checked_native_hours分母 | 非完整市场法人集中度，非有效竞争/本站获选概率；不按缺口年化 |
| scada_native_hourly.csv | F：原生medii orare小时平均；MW由同机构字段表交叉支持；13列 | F：日期取F1真实Excel日期，保留03 bis，日均00-24行不计时段 | I：同表R=Consum−Eoliana−Foto；U：prosumer、自用、净/毛、抽蓄和Stocare定义；frecventa的Hz解释未作为市场输入 |
| SCADA provisional UTC及联合表 | A：非DST日Bucharest，01=00:00—01:00；未找到专用时钟定义 | 三DST日原生23/25/23小时保留独立统计但排除UTC联合；2026-07-17错日期排除；14,496小时联合 | 时钟只是假设字段，非官方直接UTC；不批准模型；小时价由实际4QH加权平均，不以SCADA月图补分时 |
| SCADA月度统计observed_mwh | I：原生数字小时平均×1h求和，spring/autumn保留真实23/25小时行 | 2026-07只有30个有效源日期；不补日/按比例年化 | 非完整全国发电/消费总量，保留负值和缺口，不能强制与年报净量相同 |
| scada_hourly_profiles.csv | I：月×原生小时标签的MW字段均值；native_row_count为原生行数，*_valid_count为各字段非缺值数量（次） | 481组，保留01/03 bis等原标签；均值按字段跳过缺值，不填0、不按普通小时行数重加权 | 12个MW字段含派生残余需求；当前各字段有效数均等于组内行数。2025-10的03有31行、03 bis有1行；两个春季3月的03各30行，不作同等样本支持比较 |
| installed_2026_source_cells.csv | F：Sheet1 Pi licenta ANRE/P netă/Rpp/Pd，Stocare Pi/Pg/Pc/E原名原单位 | Sheet1及Stocare01.09.2026；Prosumatori01.08.2026分别记录 | 定义页解释发电许可/净功率等，未将储能Pg/Pc擅自改为Pn/Pd；Pi不证明商业在运/可用SOC，聚合E非设备可用能量 |
| intraday_monthly_aggregate.csv | F：20月PDF p2日内总MWh、EUR/MWh加权价及EUR金额 | 只有官方月标签，没有逐轮/成交时刻 | 不拆IDA1/2/3，不插值逐时，不代表可即时成交 |
| bnr_reference_rates.csv | F：Cube公布日期、EUR Rate数值，RON/EUR；2025 http、2026 https命名空间 | 413个公布日期，无周末/假日填充；保留源数值与哈希 | BNR说明每银行日13h后更新非准确发布时间；U：市场结算采用日，非强制账务汇率 |
| official_settlement_cost_samples.csv | F：Jan2025 VM/VMA/更正、Aug2026 VM，各2,976QH；四列lei金额 | 保留源区间00:00—00:14的inclusive终点标签，不用于QH价格对齐；Data非publication | I：金额关系与修订复算；U：实际公开时点、终版状态；不是缺额/余量LEI/MWh单价，不除量造价 |
| deterministic_event_cards / event_context_qh.csv | I：统一首次全期极值/最长连续段；UTC，前后12h | 正激活run被零/null/断档切断；事件副本用event_kind区分同一源QH | 不是追加交易记录；“最长系统aFRR run”非本站履约，过程相关非因果 |

核算假设A-money：公开价四舍五入误差≤0.005EUR/MWh、公开量误差≤0.05MW，则价格×量的绝对误差上界按Σh×(|v|×0.005+|p|×0.05+0.00025)，再加官方金额显示0.005EUR。该上界用于研究内部控制，不是官方认可误差或结算规则。月成交量允许0.05MWh官方0.1MWh显示误差。全部20月匹配记录附实际差额，不能只存“PASS”。

空值语义：源null/“-”不作0；缺行不插值；合法不提供段、未有数字和API失败分别登记。数值0保持源0，但不把显示0.0断言为物理精确零。异常原件不覆盖，修订时另存版本。连续交集仅作描述，未知支付/历史规则不因字段齐全而解除限制。

原件定位保真：member、sheet、row及source_hour_label按原件保存；sheet、小时标签及派生source_local_hour_end_label贯穿读取和回写时固定为字符串，不能丢失01—09前导零或03 bis。逐行member/sheet/row直接回查XLS的标签和日期校验见[p2_repair_verification.json](p2_repair_verification.json)。第一轮受影响的三表及原小时画像已另存原版本，旧审核快照未覆盖。
