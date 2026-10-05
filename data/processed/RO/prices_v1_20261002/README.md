# RO prices v1 数据说明

正式范围：Bucharest当地2025-01-01—2026-08-31，58,364个QH。独立观察日2026-09-01有96个QH。全部CSV为UTF-8 BOM、逗号分隔；空单元格表示未知/不适用，**不表示0**；布尔值为`True/False`。字段类型不得由第一行推断，全空FCR激活列仍为可空数值列。

| 文件 | 内容 |
|---|---|
| [prices_qh_formal_20250101_20260831.csv](prices_qh_formal_20250101_20260831.csv) | 主表：正式期全部价格、来源键、系统激活量、原始三相比例和数据门禁 |
| [prices_qh_observation_20260901.csv](prices_qh_observation_20260901.csv) | 同结构观察日；不计正式期现金或新增年度额度 |
| [da_native_contracts.csv](da_native_contracts.csv) | 正式期+观察日原生DA合同；2025-10-01前源市场日为小时，之后15分钟 |
| [capacity_native_hourly.csv](capacity_native_hourly.csv) | 三产品原生小时统计及研究订单映射，保留均价、需求、满足率、中标容量代理及拍卖ID |
| [activation_price_native_qh.csv](activation_price_native_qh.csv) | 原始QH激活价，字段未翻转符号 |
| [system_activation_energy_native_qh.csv](system_activation_energy_native_qh.csv) | 原始QH系统激活电量MWh，供三相比例计算 |
| [fx_native_reference_rates.csv](fx_native_reference_rates.csv) | 2024—2026已取官方参考汇率原始日期序列，不是整年完整性承诺 |
| [source_registry.csv](source_registry.csv) | 所有入选原件的URL、仓库相对路径、哈希、获取时间，未知发布/修订时间留空 |
| [coverage_monthly.csv](coverage_monthly.csv) | 逐月逐价格序列的覆盖、空缺、范围外、零/负价和极值 |
| [price_missing_in_scope.csv](price_missing_in_scope.csv) | 范围内逐时段价格缺失清单；不包含FCR研究范围外/未建模激活 |
| [afrr_disabled_hour_details.csv](afrr_disabled_hour_details.csv) | 小时扩展后所有禁用QH及其自身/同小时其他QH失效原因 |
| [source_rows_excluded.csv](source_rows_excluded.csv) | 春季DST超出拍卖自身区间的5条原始记录，禁止重复映射到次日 |
| [summary.json](summary.json) / [validation_checks.json](validation_checks.json) | 汇总与主线程逐项校验结果 |
| [dst_gap_recheck.json](dst_gap_recheck.json) | 双向aFRR/FCR秋季DST及6月1日FCR源空值复查 |
| [prior_snapshot_comparison.csv](prior_snapshot_comparison.csv) | 重解析与既有DA/容量表比较，无差异 |
| [release_manifest.json](release_manifest.json) | 本目录数据文件SHA256；README亦随构建纳入，不含清单自身 |

完整研究说明及局限见 [release_report.md](../../../../project/romania_price_release_20261002/release_report.md)，独立审核记录位于同一project目录。

## 主表字段约定

| 字段 / 模式 | 类型、单位与含义 |
|---|---|
| `delivery_start_utc`, `delivery_end_utc` | ISO8601 UTC，左闭右开；前者为主键 |
| `local_time`, `local_date` | Europe/Bucharest，时间含UTC偏移；重复秋季小时不得按无偏移墙钟去重 |
| `duration_hours` | 0.25h；不是激活电量乘数（电量已经是MWh） |
| `period_role` | `FORMAL`或`LOOKAHEAD_ONLY`，两个文件互不重叠 |
| `capacity_hour_start_utc` | 该QH所属UTC整小时；Bucharest整小时与其一一对应，包括DST重复小时 |
| `da_price_eur_per_mwh` | OPCOM原生EUR/MWh，不经过RON换汇 |
| `da_contract_id`, `da_native_resolution_minutes` | 源市场日期+区间序号，及60/15min；小时合同4行共享同一个决策，不是4笔独立DA |
| `fx_fixing_date`, `fx_ron_per_eur` | 严格早于当地交付日期的最近BNR参考日期；数值为1EUR对应RON数量，RON价除以它；仅研究假设 |
| `{fcr,afrr_up,afrr_down}_capacity_price_ron_per_mw_h_candidate` | 原始`averageAcceptedPrice`数值；候选单位RON/(MW·h)，不等于本站实际结算 |
| `{fcr,afrr_up,afrr_down}_capacity_price_eur_per_mw_h_proxy` | 上一行除以研究FX，EUR/(MW·h)；映射QH不除以4，容量现金再乘时长 |
| `{fcr,afrr_up,afrr_down}_accepted_capacity_mw` | `tenderDemand × tenderSatisfiedDemand`系统合同量代理；不是报价总量、本站MW或实际中标概率 |
| `{fcr,afrr_up,afrr_down}_capacity_order_id` | 产品+小时UTC的研究订单键；全小时共用决策为RO v1.1 A04假设，不是API小时粒度单独证明的真实容量合同粒度；源拍卖码另见native表 |
| `{fcr,afrr_up,afrr_down}_activation_price_ron_per_mwh_candidate` | 原字段数值及符号；RON/MWh候选解释。FCR全空。aFRR下调正价为支出、负价为收入的模型现金方向在目标式处理 |
| `{fcr,afrr_up,afrr_down}_activation_price_eur_per_mwh_proxy` | 原生符号价除以研究FX；现金`up_price × up_MWh − down_price × down_MWh`，不再乘0.25 |
| `{fcr,afrr_up,afrr_down}_system_activation_energy_mwh` | 系统QH原始MWh量；aFRR为方向电量幅值，FCR全空且不模拟 |
| `*_source_key` | 连接source_registry；格式`source_id@SHA256前12位`。缺容量小时键为空，已有小时但价空的键仍保留 |
| `*_status` | 见下面状态表。合法零价/负价不自动失效 |
| `alpha_up_raw`, `alpha_down_raw`, `alpha_sum_raw` | 原始比例：各方向系统MWh/(合同MW×0.25)，及两者和；不截尾、不归一化 |
| `alpha_computable` | 两个正分母存在，且两个比值有限；不表示三相条件满足 |
| `alpha_strict_valid` | 可算且各方向≥0、和≤1；没有放宽阈值或把异常替换为0 |
| `afrr_price_inputs_valid` | 两方向容量和激活EUR代理均存在；不等于数量/三相也有效 |
| `afrr_qh_data_valid` | 上述价格门禁与三相门禁均通过 |
| `afrr_hour_data_valid` | 同小时全部4QH均通过；上下调共享该数据门禁 |
| `fcr_qh_data_valid`, `fcr_hour_data_valid` | 不早于2025-06-01，容量价格/FX/严格正系统量存在，按全小时扩展；FCR激活不在此门禁内 |
| `da_contract_data_valid` | 原生DA合同价格和映射经校验后通过；按合同共用 |
| `afrr_qh_failure_reason` | `OK`，或以分号组合`ALPHA_UNCOMPUTABLE`、`ALPHA_OUTSIDE_SIMPLEX`、`REQUIRED_PRICE_MISSING` |
| `afrr_order_gate_reason` | 自身原因；自身有效但同小时其他QH失效时为`OTHER_QH_IN_SAME_HOUR_INVALID` |

## 状态与使用边界

| 状态 | 含义与处理 |
|---|---|
| `PUBLISHED_NATIVE` | 已取得原生DA价格 |
| `PUBLISHED_PROXY` | 已取得用于批准代理的原始数值，不宣称最终电站结算 |
| `SOURCE_PRICE_NULL` / `SOURCE_NULL` | 源记录存在，但相应价格字段空；保留空值 |
| `MISSING_SOURCE_HOUR` / `MISSING_SOURCE` | 所需源区间未取得；保留完整时间网格，不填0 |
| `OUT_OF_RESEARCH_COVERAGE_PRE_2025_06` | FCR1—5月不在本研究容量扩展覆盖内，不是容量收益0 |
| `SOURCE_NULL_NOT_MODELED` | FCR激活字段为空，且已确认不建独立激活现金；不能从aFRR/偏差价格替代 |

容量native表的`average_offered_price_raw`、`tender_price_raw`仅保留原始诊断值，不作为收入字段；`price_scheme`和`tender_code`保留官方标签。激活native表的`fcr_raw/afrr_up_raw/afrr_down_raw`按文件名分别表示价格候选RON/MWh或系统电量MWh，不能混用。原件内容定位为时间区间+产品/方向。

主表数据门禁尚不包含设备资格、场景开关、日p、离散单元能力、名义事件或冻结订单状态。后续模型读取时须继续执行这些约束；已冻结非零订单遇数据失效必须阻断，不能以数据门禁撤销。本站决策电量不得直接等同于系统电量。价格极值保留，完美信息条件现金不是净利润或已实现收入。

复现：从仓库根目录运行`project/romania_price_release_20261002/build_release.py`可由已保存原件重新生成同版本数据。采集脚本复用既有成功回执；需要更新市场快照时应新增版本目录与发布标识，不覆盖原始文件。该数据目录不依赖优化器。
