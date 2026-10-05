# RO MILP：取消容量现金折减系数后的现行口径

> 2026-10-05 FCR 默认份额修订：固定为 100/(450+100)=18.181818%，适用于配置内全部月份（含观察月）。该值是用户指定的100MW项目竞争情景，450MW不是经核定的历史FCR合格供给总量，也不是监管份额限制。份额乘系统需求后按现有整数MW约束向下取整：需求128MW时上限23MW，150MW时27MW，并继续受资格、采购量、物理与数据有效性限制。aFRR月度系数不变，现金不再乘该系数。其他项目功率不会自动重算此固定份额，须另配输入。此前完整测算及审核对应旧份额，本修订尚未进行全期收益重算，须使用新输出目录。

2026-10-04，按用户“月度份额上限替代原 60%—100% 参数，不再保留”的决定实施。主线程批准修改 `src/ro_milp/`、`tests/`、README、模型说明导航及本目录和验证输出。原始数据、历史结果和历史审核证据不覆盖。

本说明优先于旧数学文档、旧运行指南及月度份额首版增补中有关容量现金系数的内容；其余物理约束与月度份额机制沿用。审核结论与测试证据见同目录 `review_and_acceptance.md`。

## 数学公式与输入变化

删除 `p_up`、`p_down`、`p_fcr`、`daily_p`，以及原来系数缺失/零值禁用订单的条件。删除现金事后折减 `posthoc` 功能；不再提供 100%/80%/60% 容量现金敏感性入口。旧 M26 及其他公式中的容量现金系数项不再适用于现行实现。

月度市场份额仍通过 [M33](../romania_capacity_share_implementation_20261004/model_and_io_addendum.md) 限制中标 MW：

\[
0\le R_{k,o}\le \min\!\left(\bar R^{old}_{k,o},\left\lfloor\min_{t\in T(o)}s_{k,m(t)}D_{k,t}\right\rfloor\right),\quad R_{k,o}\in\mathbb Z.
\]

其中旧上界只包含功率、资格、历史采购量代理和 FCR 单元等既有上限，不再包含现金系数门禁。FCR 使用独立月份额；aFRR 上、下调使用同一个月份额，分别乘各方向需求。按 Bucharest 当地交付月份选取，份额缺失或订单中任一季度需求无效时禁用完整相关容量订单。

设最细季度时长 \(\Delta t=0.25\) 小时，容量价格单位为 EUR/MW/h，则：

\[
C^{cap}_{k,t}=R_{k,o(t)}\,\pi^{cap}_{k,t}\,\Delta t.
\]

现行每个两日窗口的目标为原六类计划现金之和加窗口期末 SOC 残值（沿用旧模型）：

\[
\max\sum_t\left[\pi^{DA}_t B_t\Delta t+
\sum_{k\in\{F,U,D\}}R_{k,o(t)}\pi^{cap}_{k,t}\Delta t+
\pi^{act,U}_t\alpha^U_tR_{U,o(t)}\Delta t-
\pi^{act,D}_t\alpha^D_tR_{D,o(t)}\Delta t\right]+v_W(E_{W,end}-E_{min}),
\qquad v_W=0.92\max(\overline{\pi^{DA}}_{W,last\ day},0).
\]

残值单价取该窗口最后一个 Bucharest 当地交付日所有有效季度 DA 价格的算术平均，若无有效值则取零。窗口期末残值仅服务滚动规划，在窗口指标中单列 `salvage_eur`；它不作为正式执行收入计入六类现金或累计收益。正式期末 SOC 约束继续生效，观察日规划现金也不计入正式收益。本次未修改残值计算。

无效激活时段仍按原完整订单门禁处理；上式对允许计算的项求和，零容量不要求填补缺失价格。FCR 对称容量只计一次。份额系数不再乘进容量现金、激活电量或激活价格；激活电量根据已受份额约束的中标容量计算。SOC、功率共享、效率、三相、EFC、冻结订单和终端约束不变。取消系数不新增变量、二元变量或约束行。

这意味着取消现金折减功能，并非宣称所有投标必然中标。优化变量仍是研究假设下的中标容量；份额上限限制其规模，不模拟完整竞价曲线或中标概率。

## 运行与输出

从仓库根目录运行，使用已验证依赖环境：

```powershell
python project/run_ro_milp.py run --start 2025-01-01 --end 2026-09-01 --power 100 --hours 2 --output outputs/monthly_share_run
python project/run_ro_milp.py run --capacity-share-file config/capacity_share_monthly.csv --output outputs/custom_share_run
```

上述为全期重算示例，不代表已完成重算。默认启用月度份额；`--capacity-share-mode none` 保留为显式关闭份额限制的对照模式，也不支持旧现金折减。

- `--p-up`、`--p-down`、`--p-fcr`、`--daily-p-file` 和 `posthoc` 均直接报参数错误；旧 Python 配置关键字也直接拒绝，不静默忽略。
- 如需关闭市场，使用 `--market`；项目资格容量仍通过对应资格输入限制。
- 当前 `manifest.json` 配置不再包含四个旧字段，订单记录不再输出 `p`。六类现金、价格、SOC、电量、份额与来源字段保留。
- 代码、配置和数据 hash 继续绑定检查点身份；旧版本结果不能跨版本恢复，需新输出目录。
- 旧 100%/80%/60% 结果、审计及 `solver_snapshot` 仅作历史证据，不代表本版收益。旧敏感性研究脚本不属于当前运行入口。

## 证据类别与保留问题

**规则/数据事实**：需求 MW 沿用已发布 EUR 数据包中的 DAMAS `tenderStatistics` 字段，来源登记见 [月度校准研究](../romania_monthly_share_calibration_20261004/月度容量份额上限建议.md)。本次未采集新数据，未新增官方规则结论。官方站点：[Transelectrica 辅助服务](https://www.transelectrica.ro/ro/web/tel/info-sts)、[DAMAS](https://newmarkets.transelectrica.ro/)。

**研究解释**：份额上限限制中标规模，不能视为历史中标率或监管规定的单一供应商上限。

**建模假设**：月份额校准、代理月份和观察日沿用前次登记；取消现金折减是本次用户决定。完整官方来源的标题、日期、表格位置及获取日期继续以月度研究证据表为准。

仍有 194 份供应商附件缺失和相应代理月份；FCR 激活损耗与额外循环未模拟，价格代理和项目资格等局限保留。仍属于完美信息、价格接受者的条件市场毛现金测算。此次验证是代表窗口和全期输入上界检查，不是 608 天收益重算。
