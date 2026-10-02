# 本轮补充数据字典与使用边界

F为官方原件直接支持；I为研究解释；A为本轮检查假设；U为待确认。所有文件均为2026-10-01事后取得的快照，取得时间不等于历史发布时间。原件、获取回执与哈希逐条见source_receipt_directory.csv。

| 数据 | 原生粒度、时钟、单位 | 缺值、版本与允许用途 |
|---|---|---|
| settlement_native_all_versions_verified.csv | 一条为一个原生PDF日期列×INT行×数据种类×版本；UNIQUE/DEFICIT/SURPLUS为lei/MWh；SYSTEM为MWh（F表头）；保存日期和INT序号，无已批准UTC | 空格、破折号、0及不存在的末尾行分开；557,318个格点包括矩形填充检查。262个矩形提取空值经独立PDFium定点确认后恢复，原始未修复提取另存。只用于版本/字段/覆盖研究 |
| settlement_native_latest_observed.csv / latest_selection.csv | 各月各种类选择本次可见、正文打印日期最新版本（I选择政策）；打印日期不是发布日期，也不是不可修订证明 | VM/VMA及目录标签保留。同打印日按目录观察顺序选择并记录；禁止自动回退早期版本填最新缺值。全期80份，不能命名为已验证终版 |
| settlement_joint_native_ordinals.csv | 日期+原生INT；58,364个候选物理QH为A：Europe/Bucharest日历每日92/96/100数量；不指定UTC顺序 | UNIQUE_ONLY/DUAL_ONLY只是非空结构（I），不代表已验证官方单双价模式或符号。210全价缺失和14其他结构保留；系统量不乘0.25；禁止偏差现金和本站收入 |
| ida_native_publication.csv | 原生选日网页三轮，15min，EUR/MWh、成交/买/卖MW（F表头）；query_date与返回表单日期均保存 | NUMERIC_PAIR、DASH_CELLS、BLANK_CELLS、MIXED分开。IDA3前半日空白只登记原生状态，适用范围需程序核对；不据空白断言没有竞价/取消/零成交。任何MW转MWh如后续采用须乘真实0.25h并先验语义 |
| idct_native_publication_occurrences.csv | 15/60选择器原生网页出现次序，共3,741,324条；15表头为15 min Trades，60表头实际为Hourly/Block Trades；EUR/MWh与MWh（F表头）；caption的Trades concluded in日期原样保存；native_occurrence为每原件从1开始的出现序号 | native_group_ordinal/group_occurrence/declared_rowspan和native_cell_start/end_ordinal可回定位；单元格序号从该数据表的首个表头格起1计数，前8格为表头，三元组定位从type到volume；native_row仅对包在tr中的记录有值，行外td保持空值；native_source_line为原HTML行号。完整单元格流保留重复、块与_XB。60选择器不意味着全为1h，查询日期不证明交付日；不构造trade_id/trade_time，不重复乘时长或相加buy/sell称市场成交額 |
| idct_native_group_audit.csv | 每原件×原生rowspan产品组，共129,792组；声明数、原始数据格数、原生三元组数、输出数、产品组首尾单元格位置分别列示 | 原生数据格数必须为3的整数倍；声明数、原生三元组数和输出数逐组吻合。产品组首格包含产品标签，不同于出现记录的type起点；保留原件中的相同标签，不合并产品组。该检查证明取得的网页被完整提取，不证明网站已发布全部市场数据 |
| intraday_file_round_audit.csv | 每个原件×轮次/产品检查表；表单回显日期、数字对、哈希、页脚分别记录；IDCT额外保存caption日期、全格数、表头8格、数据格数与消费数、rowspan总数、产品组数和行外格数 | 全部数据格应被消费，CSV逐原件数量与rowspan总数吻合。no_published_occurrences=True表示本次取得原件只有表头，不代表零交易。日期回显只证明接受查询；IDA行数与A Europe/Brussels物理日QH比较只作结构检查，未批准跨市场UTC/as-of映射 |
| da_ron_eur_sample_checks.csv | 官方ro原生CSV RON/MWh对同日期en原生EUR/MWh，5天339条原生合同，60/15min混合保留 | 汇率参考日应用为I：交付日D→交易日D−1→严格早于交易日的最近BNR公布日。339条价格在A显示误差界内，成交MW相等；不把5天核验扩展为全市场汇率/现金批准 |
| da_fx_daily_candidate_application.csv | 全期608个源日的候选汇率应用及RON日均（I），不是新增官方RON全期数据 | 不更改BNR官方公布序列，不在原始序列前填周末；仅为检查按市场规则解释映射。以日均再求月均，区别按物理小时加权的月均。未来策略不得使用取得时点的最新历史序列作为当时可见证明 |
| anre_opcom_monthly_cross_checks.csv | ANRE2026-06报告p14，OPCOM CET月GWh和算术均价RON/MWh，18个月；价格复算含上述I汇率 | 月量差严格A≤0.005GWh；17/18通过，2026-01超0.000025GWh；18/18候选月均价在A双重显示误差界内。ANRE重加工OPCOM报送，是第二机构聚合控制，不是独立计量或同UTC逐QH核验 |
| capacity_month_product_coverage_supplement.csv / capacity_dst_observation.csv | 复用已审APIUTC小时、原始5产品，共69,327行；对供方复算按UTC/product匹配 | 2025-10-26每产品24行对物理25小时，不能补零或拉伸；空集合all_duration_one_hour=True是集合逻辑，0行不表示有合同。57,202吻合、12,125未吻合，标签不等于完整法人/EIC |
| fee_timeline.csv | 原文生效日与lei/MWh费率，服务系统、TG、TL、交易费分别；VAT状态与项目适用分列 | 仅可见制度费率，不等于本站充放电实际费用。没有证明历史连续有效的区段保留U；2024文件费率不可默认为整个2025；反向电量/月调整/DSO/税及项目资格待确认 |
| storage_cutoff_ledger.csv | 快照日期、许可/在运/资格、MW/MWh分别 | 未取得真正年末值保持空值。年报2024中的137.2MW/269MWh实际日期为2025-02-01；2025年报494MW为2025-12-05，不能分别当2024/2025年末 |

旧交付的字段名称、数量和单位未知标记保持原样。本轮单位证据写在补充字典和事实登记，不回写旧CSV。容量月报明确lei/hMW；FCR合同价格栏同样为lei/h×MW。FRR程序§8.5.3却印lei/MWh，保留文字冲突，不自行宣布官方笔误。DAMAS平均价与受理报价、容量权重、罚款/实履约账单必须分开。激活量已核为系统MWh，但激活价全部字段分母、结算版本、本站映射和现金仍未批准。
