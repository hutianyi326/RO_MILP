# RO MILP v0.1 实现说明

> 2026-10-04 现行口径：已删除 p_up/p_down/p_fcr、daily_p 及 posthoc 现金折减入口，仅保留月度份额约束。本文旧现金系数公式和命令仅作历史记录，现行公式、运行方式及审核见 [取消旧系数后的说明](../romania_capacity_share_cleanup_20261004/current_model_and_usage.md)。

2026-10-02。本轮实现RO数学v1.1 M01—M32及P01—P07，使用已经生成的全EUR数据。主线程执行实现，独立reviewer只读审核。审核结论和最终测试范围见同目录`review_and_acceptance.md`，不可由“程序正常退出”代替审核结论。

## 文件与数学映射

| 模块 | 职责 | 数学对应 |
|---|---|---|
| `src/ro_milp/config.py` | 项目参数、当地日历、整数FCR单元还原 | M01—M07、M08、P03 |
| `inputs.py` | EUR来源哈希、原生DA与UTC时标、严格三相/整小时门禁、固定年度预算 | M10—M12、M23 |
| `core.py` | 稀疏矩阵、原生订单、事件余量、两日求解、全部目标现金与残值 | M03—M24、P01—P07 |
| `audit.py` | 从订单和输入独立回放事件、相位、SOC、FCR缓冲、现金和EFC | M30 |
| `rolling.py` | 首日执行、次日订单冻结、原子事务链、恢复、输出及事后敏感性 | M09、M25—M29、M31—M32 |
| `cli.py`、`project/run_ro_milp.py` | 参数入口、输入检查、运行/恢复/事后现金敏感性 | 已批准输入输出规范 |
| `tests/test_model.py`、`project/run_tests.py` | 边界、等价、审计拒绝和恢复故障回归 | P08—P10、M30 |
| `validate_representative.py` | 真实数据代表窗口验证 | 实现验收，不等于全期收益验证 |

参考本工作区ES MILP的输入、单窗、滚动、账本与验证分层，未复制其IDA、容量计价单位、下调符号和缺失处理。原GitHub参考为<https://github.com/hutianyi326/ES_MILP>；本轮可读的本地ES实现用于结构参考。

## 使用

从仓库根目录，在Python 3.12环境安装`requirements.txt`后执行。当前工作区已有父目录`.venv-es-milp`运行时，已用于测试，无需为本轮再次安装依赖。输入路径默认相对本仓库定位，与当前终端所在目录无关。

```powershell
python project/run_ro_milp.py preflight
python project/run_tests.py --report outputs/tests.json
python project/run_ro_milp.py run --start 2025-01-01 --end 2026-09-01 --hours 2 --output outputs/ro_2h_p100
```

最后一条是完整正式期命令示例，不表示本轮已经执行全期。日期按Bucharest当地午夜解释，`end`不含；必须具备完整次日观察网格。首次运行要求全新输出目录，防止覆盖已有结果。

```powershell
python project/run_ro_milp.py run --start 2025-01-01 --end 2026-09-01 --hours 4 --p-up 0.8 --p-down 0.8 --p-fcr 0.8 --time-limit 60 --gap 0.0001 --output outputs/ro_4h_p80 --max-windows 10
python project/run_ro_milp.py run --start 2025-01-01 --end 2026-09-01 --hours 4 --p-up 0.8 --p-down 0.8 --p-fcr 0.8 --time-limit 60 --gap 0.0001 --output outputs/ro_4h_p80 --resume
python project/run_ro_milp.py posthoc --source outputs/ro_2h_p100 --p-up 0.8 --p-down 0.8 --p-fcr 0.8 --output outputs/ro_2h_posthoc80
```

四种市场：`DA`、`DA+aFRR`、`DA+FCR`、`DA+aFRR+FCR`。`--power`为MW，`--hours`为2或4。`--qualification-up/down/fcr`显式设置资格研究上限；`--fcr-unit-caps`接受每研究单元不超过20MW的列表。默认按ceil(P/20)均分，不代表真实项目认证。

`--daily-p-file`接受JSON：`{"2025-01-01":{"u":1,"d":0.8,"F":null}}`。一旦提供非空日表，缺日、缺值不回退到标量，缺日/空值对应方向的新订单为0；已有非零冻结承诺冲突则阻断。上例只演示一日，正式运行应提供整个正式及观察期。p为容量现金外生系数，不折减实际占用功率或激活电量。

`--budget-file`接受按年份固定的EFC额度JSON，不随市场、H、p变化。默认共同比较组按DA有效覆盖生成；本包全正式期为2025年600、2026年399.452054795 EFC。短样本会按短样本天数重新确定额度，不能把多个独立短样本收益拼成完整滚动结果。

主敏感性必须独立重优化。`posthoc`仅对uniform p=1的已审核轨迹修改三项容量现金，保留DA、激活、功率、SOC与EFC；明确标记不重新优化。首版事后工具仅接受统一三产品系数，逐日情景可经run重优化。

## 求解与结果

默认SciPy/HiGHS：30秒单窗、相对gap 1e-4、presolve启用。状态0/1也须有有限可行解且通过矩阵检查、整数回整和独立审计才能提交。状态1的可行解允许提交，输出原始gap与加回固定现金后的目标尺度gap，不声明精确最优。无可行解、审计或提交失败返回BLOCKED，保留已提交历史，CLI非零退出。

2026-10-03敏感性修订：HiGHS primal/mip feasibility tolerance设为1e-8；首次status2时可在原30秒剩余时间内对相同模型关闭presolve重试，逐次状态/耗时写入metrics。内部EFC保守guard由固定1e-6改为min(1e-6,A/2)，A为扣除原终端留存后的经济余额；允许额度A−guard不超原年度预算。这是内部数值政策修订，不是原矩阵等价变换；冻结订单、SOC和独立审计容差未放宽。详见[修订范围与诊断](../romania_capacity_sensitivity_20261002/scope.md)。恢复旧运行时必须使用其原代码快照；新旧代码身份不同，不能跨版本接续账本。

核心默认紧凑表示；`--formulation reference`保留相位独立C/D和二元以及逐FCR单元整数，以供等价测试。相同表达式分组仅共享功率逻辑，不合并相位SOC边界。负价下仍保留必要互斥。参考版和紧凑版均消元首日固定订单，因此实测参考变量数不应冒充数学表中未消元的2,688/2,832。

每个输出目录包括：

- `manifest.json`：正式期、输入/代码/参数哈希、年度预算、依赖版本、输入证据。
- `windows/0000.json`等：不可覆盖的每日原子事务，含正式执行轨迹、今日关闸的次日订单、初日零订单、检查指标及下一状态。SHA链连接窗口；恢复验证状态连续与输入代码一致性。
- `checkpoint.json`：派生缓存；恢复以不可变事务链为准，不以缓存单独续算。
- `executed_qh.csv`、`executed_phases.csv`：仅正式执行，不含次日计划或观察日现金；原源缺失标记保留。
- `committed_orders.csv`：包括显式零订单、FCR单元向量、关闸/结果/交付时间和有效性原因。末日提交的观察日订单属于未来承诺，不进入正式现金。
- `window_metrics.csv`：变量/二元/整数/行/非零、build/solve/audit耗时、节点、incumbent/bound/gap、规划现金及残值。规划金额不得与执行金额相加。
- `monthly_cash_eur.csv`、`annual_efc.csv`、`summary.json`、`report.md`：六项EUR现金、kEUR/MW、预算/执行EFC和状态；不做年度外推。
- `failure_*.json`：失败原因；失败窗口不增加执行现金或预算消耗。

原子发布依赖支持硬链接的本地文件系统（当前NTFS已验证）；不支持时明确失败，不退化为可覆盖历史。中断后的`.tmp`文件不进入恢复链，可人工清理。代码升级、数据或参数变更禁止沿用旧检查点；另开目录。

## 来源、分层与限制

**规则事实**：市场证据沿用已审核研究及数据包中的OPCOM、Transelectrica/DAMAS、BNR等官方原件，本轮未增加市场规则。详见`data/processed/RO/prices_eur_v1_20261002/source_registry.csv`及数据README。此前原币RON字段已按Bucharest交付日匹配的严格前序BNR参考日换为EUR，求解器不重复换汇。

**研究解释**：容量/激活代理价格可用于本版条件现金比较，不能自动等同本站真实结算；名义时表不构成历史信息可见性的证据。输入哈希和物理审计证明可复算性及实现自洽，不证明外部字段最终性。

**建模假设**：名义D−1容量09/10点和DA13/14点、小时容量订单、研究资格/单元、三相顺序、p系数、FCR静态缓冲、EFC终端留存与残值均沿用数学基线。首日已关闸但无账本订单为0。完美信息条件毛现金不是实盘收益、净利润或已认证的全时域理论上界。

求解实现来源：SciPy官方`scipy.optimize.milp`文档（无发布日期，访问2026-10-02）：<https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html>，Parameters/Returns/Notes，确认最小化接口、整数约束、time_limit、mip_rel_gap、HiGHS及状态含义。代码对最大化现金取负，并在bound/gap中还原固定目标常数。

未解决现实数据和履约问题保持原研究状态：源价格缺口、代理字段单位/最终结算语义、真实历史关闸与合同、项目资格和FCR频率轨迹。实现按已批准假设处理，不把review PASS解释为这些现实问题已关闭。本轮不包含预测信息集、净收益成本层或608天完整历史收益验收。
