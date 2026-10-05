# 容量收入系数敏感性：100MW/200MWh

正式期间：2025-01-01至2026-08-31；三情景p_up=p_down=p_fcr分别为100%、80%、60%，独立重新优化。p是外生容量现金系数，非实测中标概率；不缩减功率、SOC及激活义务。

最终交付位置为`v3/`：同一代码、输入、预算和时间范围下的三组完整运行。各情景`p*_run`存逐日账本及原始结果，`p*_report`存ES格式图表和表格；`comparison/三情景敏感性汇总.md`为汇总入口。最终验收见[任务审核记录](../../project/romania_capacity_sensitivity_20261002/review_and_acceptance.md)。

根目录`p80_run`是旧代码完成运行，`p60_run`为首次阻断；`v2/`中100%和80%完成，60%在342窗阻断，均为诊断历史，不作为最终三情景比较。原p100历史基准在相邻`full_run_100mw_200mwh_20261002/`保留。

`retry_diagnostic.json`记录首次presolve重试验证；`precision_diagnostic.json`记录仅提高精度仍失败；`guard_diagnostic.json`记录自适应内部数值余量修订后48窗连续跨年PASS；`v3_unit_tests.json`记录19项测试PASS。原始负右端矩阵和失败状态作为诊断证据保留。

全期输入均来自已审EUR包，来源OPCOM、Transelectrica/DAMAS及BNR。本轮未改变原始数据，也未重新换汇。数值政策、官方事实/建模假设边界见[scope](../../project/romania_capacity_sensitivity_20261002/scope.md)。未覆盖真实项目结算、项目资格和FCR频率激活损耗。
