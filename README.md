# RO_MILP

> 2026-10-05 已完成FCR固定18.1818%、aFRR原月度份额的100MW/200MWh全期重算：608窗口，毛现金62,101,309.95 EUR，全期独立自动复算PASS（非review agent结论）。[最新结果报告](outputs/fcr_competition_100mw_200mwh_20261005/report/结果展示.md) · [与旧版对比](outputs/fcr_competition_100mw_200mwh_20261005/comparison.csv) · [数值修复及运行说明](project/romania_fcr_competition_run_20261005/scope.md)。最终运行目录为run_v2；run为保留的未完成诊断。

> 2026-10-05 FCR 默认份额修订：固定为 100/(450+100)=18.181818%，适用于配置内全部月份（含观察月）。该值是用户指定的100MW项目竞争情景，450MW不是经核定的历史FCR合格供给总量，也不是监管份额限制。份额乘系统需求后按现有整数MW约束向下取整：需求128MW时上限23MW，150MW时27MW，并继续受资格、采购量、物理与数据有效性限制。aFRR月度系数不变，现金不再乘该系数。其他项目功率不会自动重算此固定份额，须另配输入。本修订已完成全期重算，结果见上方2026-10-05报告；之前的审核记录对应各自历史版本。

> 2026-10-04 现行模型：默认启用月度 FCR/aFRR 系统需求份额上限，已删除原 100%/80%/60% 容量现金折减参数及 posthoc 入口。容量现金直接按中标 MW × 价格 × 时长计算。见 [现行公式与运行指南](project/romania_capacity_share_cleanup_20261004/current_model_and_usage.md) 及 [本版审核记录](project/romania_capacity_share_cleanup_20261004/review_and_acceptance.md)。现行月度份额版已完成608天重算及独立审核PASS：[上一版完整报告](outputs/monthly_share_100mw_200mwh_20261004/report/结果展示.md) · [新版审核记录](project/romania_monthly_share_full_run_20261004/review_and_acceptance.md)。下列100%/80%/60%敏感性仍为历史版本。

罗马尼亚电力市场与独立储能研究，以及已通过独立审核的 MILP 数学模型。仓库更新至 **2026-10-05**，历史研究期间为 **2025-01-01 至 2026-08-31**。

本仓库从原多国研究工作区独立整理，保留罗马尼亚研究、官方原件、数据和审核证据，以及必要的西班牙方法对照。**历史 RO v1.1 EUR 求解器已完成100MW/200MWh、2025年1月至2026年8月完整608天条件测算；结果与ES格式报告均通过独立审核。** [完整测算结果](outputs/full_run_100mw_200mwh_20261002/report_v1/结果展示.md) · [全期审核记录](project/romania_full_run_20261002/review_and_acceptance.md)。结果为条件毛现金，非实际项目净利润。

2026-10-03历史记录：**容量收入系数100%/80%/60%三情景均完成608天独立重优化并通过审核**。[三情景汇总](outputs/capacity_sensitivity_100mw_200mwh_20261002/v3/comparison/三情景敏感性汇总.md) · [敏感性审核记录](project/romania_capacity_sensitivity_20261002/review_and_acceptance.md)。最终共同版本为v3；修复内部数值余量及求解精度，年度经济预算和收益口径不变。原基准作为历史版本保留。

## 当前代码与运行

当前开发分支为 `容量系数`。使用Python 3.12并安装 `requirements.txt`；从仓库根目录执行：

```powershell
python project/run_ro_milp.py preflight
python project/run_ro_milp.py run --start 2025-01-01 --end 2026-09-01 --power 100 --hours 2 --output outputs/new_100mw_200mwh_run
python project/run_tests.py
```

运行输出目录必须新建。恢复运行使用 `--resume`，代码、输入及配置身份必须与原检查点一致。默认读取EUR数据包和 `config/capacity_share_monthly.csv`；FCR为固定18.1818%需求份额，aFRR按原月度供应商P90/中位数方法校准。FCR份额以100MW项目为参考，修改项目功率不会自动重算此份额，应另设份额文件。

默认全期年度循环预算为2025年600 EFC、2026年1—8月399.452054795 EFC。模型只规划两日，没有跨月最优分配循环预算。最新方案2025年11月6日基本耗尽年度预算、2026年7月底基本耗尽当期可交易额度，因此年末/月末收益断层包含预算提前消耗效应，不能全部归因于市场竞争。FCR只计容量机会价值，未计频率激活损耗和循环。

最新运行 `outputs/fcr_competition_100mw_200mwh_20261005/run_v2` 为完整结果；同目录 `run` 为保留的未完成数值诊断。全期毛现金62,101,309.95 EUR，最近12个月301.3862 kEUR/MW。33项回归测试及全期独立自动复算PASS，本轮未执行review agent复核。`src/ro_milp/core.py` 已加入常数相减后小于1e-12的近零约束残差归零处理，相关说明见 [运行与验证记录](project/romania_fcr_competition_run_20261005/scope.md)。

官方来源沿用OPCOM、Transelectrica/DAMAS、BNR及研究证据表。本版本属于事后完美信息条件毛现金测算；历史报告、审计和审核文件保留各自版本口径。

## 从这里开始

| 阅读内容 | 文件 |
|---|---|
| 历史容量系数100%/80%/60%敏感性 | [三情景汇总与对比图](outputs/capacity_sensitivity_100mw_200mwh_20261002/v3/comparison/三情景敏感性汇总.md) · [独立审核PASS](project/romania_capacity_sensitivity_20261002/review_and_acceptance.md) |
| 100%情景随机单日审计 | [2025-11-26完整输入、订单、SOC及收入计算](outputs/random_day_audit_p100_20261003/随机单日独立审计.md) · [固定抽样范围](project/romania_random_day_audit_20261003/scope.md) |
| 100MW/200MWh完整608天结果 | [ES格式结果展示及9张图](outputs/full_run_100mw_200mwh_20261002/report_v1/结果展示.md) · [独立审核PASS](project/romania_full_run_20261002/review_and_acceptance.md) |
| 运行入口与使用说明 | [现行运行指南](project/romania_capacity_share_cleanup_20261004/current_model_and_usage.md) · [入口](project/run_ro_milp.py) |
| 实现验证、变量及求解统计 | [验证报告](project/romania_implementation_20261002/validation_report.md) · [独立实现审核](project/romania_implementation_20261002/review_and_acceptance.md) |
| 全EUR价格输入（Bucharest交付日换汇） | [EUR数据v1与单位核查](data/processed/RO/prices_eur_v1_20261002/README.md) |
| 2025-01—2026-08价格数据包及观察日 | [价格与数据门禁说明](data/processed/RO/prices_v1_20261002/README.md) · [完整性报告](project/romania_price_release_20261002/release_report.md) |
| 价格数据完整性独立审核 | [数据发布PASS及已披露缺口](project/romania_price_release_20261002/review_and_acceptance.md) |
| 当前数学模型 RO v1.1 | [MILP 数学说明](project/romania_milp_20261002/romania_milp_mathematical_formulation.md) |
| 变量数量与等价求解优化 | [性能数学附录](project/romania_milp_20261002/variable_count_and_performance.md) |
| 二次独立审核 | [性能及规模复核 PASS](project/romania_milp_20261002/review_second_performance.md) |
| 初次数学审核 | [数学审核与验收](project/romania_milp_20261002/review_and_acceptance.md) |
| 策略与假设 | [假设登记](project/romania_milp_20261002/strategy_and_assumptions.md) |
| 用户确认的计算口径 | [西班牙对照与确认记录](project/romania_milp_method_confirmation_20261002.md) |
| 最近一轮 aFRR 深入研究 | [价量、容量报价和激活异常报告](project/romania_afrr_deepresearch_20261002/research_report.md) |
| 官方规则与全期研究 | [阶段资料导航](docs/research_index.md) |

## 已固定的研究口径

- 独立储能 P 参数化，参考 100 MW，比较 2h/4h 直流名义容量。
- SOC 5%—95%，正式期初末 SOC 5%，单向效率 92%；年度 600 EFC 基准按固定共同比较覆盖折算。
- 完美信息、价格接受者、两日规划、首日执行，保持订单冻结和 SOC 连续。
- 市场为 DA、aFRR 和 FCR 容量机会价值；不纳入 IDA、连续日内、mFRR、RR 或偏差套利。
- 容量收入采用明确标注的价格代理；月度份额约束限制中标 MW，现金不再叠加任何旧容量收入折减系数。份额是研究假设，不是历史中标概率。
- aFRR 使用严格有效三相，超限/缺失不归一化；关闭覆盖异常时段的完整 aFRR 订单，保留其他有效市场。
- FCR 从 2025 年 6 月起有数据的订单启用，预留对称功率及 30 分钟静态能量缓冲；暂不模拟频率激活电量、损耗、恢复交易和额外循环。
- 结果指标为条件市场毛现金，不是扣除全部费用、税、资本开支后的净利润，也不是实盘可执行预测。

这些是已确认的研究假设和范围，不代表具体项目资格、真实报价成交或最终结算已经核实。官方事实、研究解释和模型假设在文档中分别标注。

## 模型和性能状态

M01—M32 定义原始经济和物理语义，现行容量现金公式以本版取消旧系数说明为准、M26 停用，并增加月度份额约束 M33；P01—P10 规定有证明条件的紧凑表示：冻结首日常数化、同质 FCR 单元整数投影、相同净功率表达式共享、单正部变量、稀疏 SOC 和重复行删除。

| 正常两日、三相全存在的规模上界 | 小时 DA | 15 分钟 DA |
|---|---:|---:|
| 未做本轮缩减的变量 | 2,688 | 2,832 |
| 紧凑表示变量 | 528 | 1,032 |
| 其中符号二元变量 | 72 | 288 |
| 核心约束行 | 1,225 | 2,017 |

数学模型和性能附录均获独立 `research_reviewer`（gpt-6-astra / medium）审核 PASS，未关闭 P0/P1/P2 为 0。上述数字原为数学上界；当前合成全有效三相测试已实际生成528/1,032变量和1,225/2,017行，并与reference验证目标等价。真实27窗最大901变量、244二元。变量缩减不保证耗时下降，本次两组合成对照未观察到提速；详见[实测报告](project/romania_implementation_20261002/validation_report.md)。

## 仓库结构

- `countries/RO/`：官方规则、样本验证、全期描述、缺口补查、研究图表和数据表。
- `project/romania*/`：阶段研究过程、来源清单、既有采集/验证工具、审核记录及 MILP 文档。
- `src/ro_milp/`、`tests/`：EUR输入、MILP内核、独立审计、滚动账本、CLI与回归测试；`requirements.txt`记录已测试依赖。
- `outputs/implementation_validation_20261002/`：代表运行及验证证据，最终版本见v3导航。
- `outputs/full_run_100mw_200mwh_20261002/`：100MW/200MWh完整608天求解、独立复算、ES格式图表及CSV。
- `outputs/capacity_sensitivity_100mw_200mwh_20261002/v3/`：100%/80%/60%同版本全期运行、三组ES报告及汇总；父目录保留数值修复证据和旧阻断运行。
- `data/raw/RO/`：已取得的罗马尼亚官方原件和获取回执，保持原始内容与来源追溯。
- `data/processed/RO/prices_v1_20261002/`：正式期与独立观察日价格、原始粒度表、数据门禁、缺失和来源清单。
- `countries/ES/MILP/research/`：两份必要的西班牙 v2.0/v2.1 方法对照文档，不是西班牙完整项目。
- `packaging/`：文件映射、源/仓库 SHA256、压缩说明、缓存与重复快照排除清单，以及打包验证记录。
- `docs/`：研究阅读导航和数据恢复说明。

保留原相对目录，便于已有研究脚本和来源记录定位。个别历史回执含原工作区绝对路径，它们是当时的证据记录，不应当作本机运行配置。原 MILP v1.0 快照保留在模型目录的 `archive/`，其相对链接按原文件所在目录解释。

## 大表和可追溯性

少量大型 CSV/JSON 以无损 `.gz` 保存，避免超过普通 Git 文件限制。对应未压缩文件路径、原始大小和 SHA256 见 [压缩文件目录](packaging/compressed_files.json)，逐文件来源/仓库校验值见 [源文件清单](packaging/source_manifest.json)。

如需运行依赖原文件名的研究脚本，先把 `.gz` 解压到同目录，恢复原 `.csv` 或 `.json` 文件，再核验原始 SHA256。恢复后的大表已加入 `.gitignore`，不再次提交。详见 [数据恢复与审计说明](docs/data_and_provenance.md)。未压缩复制的来源文件保持逐字节一致；本次整理不修改旧研究结论或原始证据。

不纳入环境、缓存、凭证文件和重复审核提交快照；被排除的文件和原因逐项记录在 [排除清单](packaging/excluded_files.json)。官方原始 ZIP/RAR 等证据附件不因属于压缩格式而删除。

## 研究边界与下一阶段

全期aFRR激活价格及观察日已在价格v1中提取；源空值与三相异常保留并逐小时禁用相关订单。FCR容量数值价实际从2025-06-07起，独立FCR激活价未取得。尚未关闭字段语义与最终性、完整有效容量报价分母、真实历史事件/合同、实际项目资格和FCR频率轨迹。没有以取得完整曲线或真实项目发票为条件研究数学模型的先决要求。

较早阶段报告中的“未批准模型”“门禁 false”是当时的历史状态，原文保留；最新用户确认和数学阶段结论以本页指向的 2026-10-02 方法与 v1.1 审核记录为准。数学审核不追溯关闭早期现实业务或数据缺口。

已完成输入输出规范、数据适配、实现验证及100MW/200MWh完整历史条件测算和独立验收，含100%/80%/60%容量收入系数敏感性。上述为历史成果；当前版本取消旧 p 系数，月度份额版及其他时长或市场组合需另开情景运行，不能沿用旧结果。运行示例和恢复规则见现行指南；求解器默认只读取校验过的EUR输入包。

## 官方来源与使用说明

主要第一方来源为 Transelectrica/DAMAS、OPCOM、ANRE、BNR 和 ENTSO-E。文档的证据表保存机构、标题、版本/适用日期、URL、章节和访问日。

官方原件及第三方资料的权利属于相应机构；收录和来源引用不代表赋予额外再分发许可。本仓库未为第三方材料附加统一开源许可证。研究结论及模型假设以标注范围为准。
