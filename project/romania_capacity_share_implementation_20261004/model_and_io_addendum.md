# RO MILP 月度容量份额扩展：数学与输入输出说明

> 2026-10-04 现行口径：已删除 p_up/p_down/p_fcr、daily_p 及 posthoc 现金折减入口，仅保留月度份额约束。本文旧现金系数公式和命令仅作历史记录，现行公式、运行方式及审核见 [取消旧系数后的说明](../romania_capacity_share_cleanup_20261004/current_model_and_usage.md)。

2026-10-04。用户授权将上一轮月度建议系数写入 MILP。主线程批准修改本仓库 `src/ro_milp/`、`config/`、`tests/`、本研究目录和相应验证输出目录。原始资料、已发布 EUR 输入包、旧历史结果与旧审核记录保留不变。

本增补为 M01—M32、P01—P10 的新增假设及约束，不继承旧版独立审核的 PASS 结论。当前通过主线程测试及程序独立语义回放，未调用独立 review Agent，也未重跑 608 天收益。

## 事实、研究解释与假设

**官方数据事实**：系统需求取现有经哈希核验的 `capacity_native_hourly_eur.csv` 中 `demand_mw`，来源为 Transelectrica/DAMAS `tenderStatistics`。它与 `accepted_capacity_mw` 不同，后者继续作为旧版 A11 的历史采购量研究上限，并继续用于激活三相比值；不将需求量代入三相分母。

**研究解释**：项目占系统需求的份额不等于其报价中标概率。份额约束限制中标 MW，而原有 `p_up/p_down/p_fcr` 系数仅作用于容量现金。

**A17｜用户采用的月度份额假设**：逐月使用 [月度建议表](../romania_monthly_share_calibration_20261004/monthly_recommended_share_caps.csv) 的完整精度系数。FCR 取 PETROM 参照，aFRR 按各方向供应商 P90 中位数取较小值；覆盖门槛、缺失月份代理及其局限见 [研究报告](../romania_monthly_share_calibration_20261004/月度容量份额上限建议.md)。用户此次要求写入模型视为采用这版建议参数，未将代理值改称实测值。

**A18｜观察月边界假设**：2026-09-01 只供最后两日规划，明确采用 2026 年 8 月的 FCR 31.25%、aFRR 24/175。参数文件将 2026-09 标为 `LOOKAHEAD_ONLY`；不得以此参数行启动 9 月正式执行。其他未列月份没有隐含向前填充。

**A19｜缺失处理及粒度**：没有当月份额或订单覆盖的任一季度缺少有效正需求时，禁用完整容量订单，不改用实际采购量冒充需求，不影响其他有效产品。容量整数粒度仍为 1 MW。

## M33｜份额容量上界

设订单覆盖季度集合为 \(T(o)\)，\(m(t)\) 为 Bucharest 交付月份，\(D_{k,t}\) 为官方需求 MW，\(\bar R^{old}_{k,o}\) 为原模型根据额定功率、资格容量、实际采购量代理及 FCR 单元上限计算的整数上界，则：

\[
\bar R_{F,o}=\min\left\{\bar R^{old}_{F,o},
\left\lfloor\min_{t\in T(o)}s_{F,m(t)}D_{F,t}\right\rfloor\right\},
\]
\[
\bar R_{aU,o}=\min\left\{\bar R^{old}_{aU,o},
\left\lfloor\min_{t\in T(o)}s_{A,m(t)}D_{aU,t}\right\rfloor\right\},\qquad
\bar R_{aD,o}=\min\left\{\bar R^{old}_{aD,o},
\left\lfloor\min_{t\in T(o)}s_{A,m(t)}D_{aD,t}\right\rfloor\right\}.
\]

\[
0\le R_{k,o}\le\bar R_{k,o},\quad R_{k,o}\in\mathbb Z.
\]

当前为小时订单，四个季度均采用对应当地月份的系数。DST 重复小时以 UTC 订单键区分，月界不能按 UTC 日期判断。

实现只在份额乘积取整前加 `1e-9 MW`，防止如 24/175 × 175 的浮点表示误差导致错取 23 MW；不对其他物理上限加该容差。原有有效性门禁、p=0 禁用行为、功率共享、SOC、效率、激活、循环预算、订单冻结与终端约束继续适用。

目标函数与结算公式保持原结构：容量现金 = **优化后的中标 MW × 价格 × 时长 × 原现金系数 p**。不再乘份额系数。激活电量和物理占用也使用同一优化后的中标量。

## 性能

紧凑模型直接收紧现有整数容量列的上界，不新增决策变量、二元变量或约束行；零上界仍可常数化。reference 模型继续用原有 FCR 聚合上界行。符号表达式的边界缩小后，部分二元变量还可能被消除，但不保证求解时间必然减少。

## 参数与需求输入

运行默认读取仓库 [config/capacity_share_monthly.csv](../../config/capacity_share_monthly.csv)，共 20 个正式月份及 1 个观察月份。文件保留 FCR/aFRR 小数份额、各自来源状态、参考月份和作用范围。它是可修改的研究输入，不把系数散落在模型公式中。

- 默认 `Config.capacity_share_mode='monthly'`；CLI 同样默认 monthly。
- `--capacity-share-file PATH` 可替换月度 CSV。重复月份、非规范月份、非有限值、超出 [0,1]、缺少来源状态或错误范围均拒绝。
- `--capacity-share-mode none` 显式关闭新增份额约束，用于复现旧经济口径；不得同时提供自定义份额文件。
- 原有现金系数默认仍为 100%。需要 80%/60% 现金敏感性时仍可显式传入，但这与份额限制叠加，而不是替代份额限制。

`Quarter` 新增 `demand_u/demand_d/demand_f`。输入适配器按 UTC 小时和产品连接需求，与正式/观察价格文件分开读取；原生需求文件必须出现在既有 release manifest 中，且字节哈希匹配。缺失需求保持空值，不能用采购量补齐。需求文件成为运行输入 hash 的组成部分。

使用方式（从仓库根目录）：

```powershell
# 默认启用本版月度系数；本命令示例不代表已执行全期重算。
python project/run_ro_milp.py run --start 2025-01-01 --end 2026-09-01 --power 100 --hours 2 --output outputs/share_cap_full_run

# 自定义输入仍使用相同校验和约束。
python project/run_ro_milp.py run --capacity-share-file config/capacity_share_monthly.csv --output outputs/share_cap_custom

# 显式关闭份额限制，仅用于旧口径对照。
python project/run_ro_milp.py run --capacity-share-mode none --output outputs/legacy_share_off
```

## 输出与恢复

`committed_orders.csv` 和逐日 JSON 新增：`capacity_share_mode`、`capacity_share_month`、`capacity_share_coefficient`、`capacity_share_status`、`capacity_share_reference_month`、`capacity_share_scope`、`system_demand_min_mw`、`share_limit_mw`；`upper` 为叠加全部门禁后的最终整数上界。

`executed_qh.csv` 对 FCR/aFRR 上下调分别增加份额系数、来源状态、需求 MW、份额形成的未取整 MW 上限及最终 `upper`。原有价格、SOC、电量和六类现金字段不变。

`manifest.json` 保存完整系数表、运行模式、输入及代码 hash；`summary.json` 增加系数表 hash 和代理月份提示。模型内 `audit_window` 从原始需求及配置独立重算上界，检查订单容量、输出上界、份额及来源元数据，再回放 SOC、激活电量及现金。

改变系数、代码或输入后不可恢复旧检查点；应使用新输出目录。已有历史收益输出没有被覆盖。

## 检查与保留问题

- 原 v1.1 回归测试显式使用 `capacity_share_mode='none'`，保留原经济口径及变量规模对照；新增测试覆盖默认月表、需求与采购量分离、Bucharest 月界、取整、缺月/缺需求、代理、观察日、审计拒绝超额和恢复身份校验。
- 真实输入检查覆盖正式期与观察日 43,845 个容量订单上界。
- 三组 100 MW / 200 MWh 实际数据滚动验证：2025-01-31—02-01、2025-10-25—10-26、2026-08-30—08-31，共 580 个正式执行季度，另有各窗口观察计划。均通过内置独立语义回放；不代表 608 天收益重算完成。
- 原研究仍有 194 份附件待下载；2026 年 4—7 月 aFRR 等代理月份的证据状态保持原样。加入约束不等于确认真实中标概率，也未消除 FCR 激活损耗、价格接受者假设及项目资格等旧局限。
- 已知 2025-10-26 最后一个容量小时的原价格缺口仍按旧门禁处理，不因本次份额输入而启用。

验证原件见 [测试报告](../../outputs/capacity_share_implementation_20261004/final/unit_tests.json) 和 [真实数据验证](../../outputs/capacity_share_implementation_20261004/final/real_validation.json)。使用既有 `.venv-es-milp` 的已固定依赖环境。

官方来源延续上一轮登记：[Transelectrica 辅助服务目录](https://www.transelectrica.ro/ro/web/tel/info-sts)、[DAMAS 公共平台](https://newmarkets.transelectrica.ro/)。交付区间、文件标题、表头位置、获取日期和 URL/SHA-256 见 [月度研究证据](../romania_monthly_share_calibration_20261004/月度容量份额上限建议.md)。本次仅实现已登记数据和用户选择的假设，没有新增市场规则结论。
