# 取消旧容量现金系数：独立审核与主线程验收

日期：2026-10-04。分支：`容量系数`。用户授权删除原 60%—100% 系数并交独立 review Agent 审核。

**最终 PASS；未关闭 P0=0、P1=0、P2=0。主线程验收本次旧容量收入系数删除及月度份额整合。** 本结论不代表已完成新版 608 天收益测算，不重新授予原研究数据完整性结论。

## 独立审核

审核角色：`research_reviewer`，`gpt-6-astra / medium`；Agent：`/root/capacity_income_removal_review`。职责为只读审核，无下级委派，未直接修改交付。

首轮结论为范围内 PASS，附 2 项非阻断 P2。审核员独立复跑 31 项测试，全部通过（33.168 秒）。主线程修复后交同一审核员二次复核；最终意见：

> 最终 PASS。P0=0、P1=0、P2=0；首轮两项 P2 均关闭。

| 问题 | 修复及二次复核 |
|---|---|
| 现行公式未写窗口末 SOC 残值 | 现行说明补全目标和残值价格公式、无价取零、残值及观察日计划现金不计入正式收益；与 `core.py`、`audit.py` 一致。未改变原数值逻辑。 |
| manifest 仍写旧模型版本 | `rolling.py` 的 specification 标识 M33、取消旧现金系数、M26 停用和现行说明日期；新增断言，三个真实窗口 manifest 均确认新描述。 |

审核确认旧参数/门禁/posthoc 不再存在于生产路径；目标、现金回放及物理激活共享同一中标容量；Bucharest 月份、需求和采购量语义、缺失门禁、整数取整、观察月、冻结与恢复身份符合说明。

审核员独立计算的最终生产代码 SHA256：

`fcc1efda3bd2458daafba581b0894741497405235d98ec79e9bf6f7fa20aca5b`

与 r2 单元测试、真实验证汇总、三个真实窗口 manifest 全部一致。二次审核核查 r2 证据和修复内容，未再次重复全部测试，也未由审核员另行求解真实窗口。

## 最终验证证据

- [r2 单元测试](../../outputs/capacity_share_cleanup_20261004/r2/unit_tests.json)：31/31 PASS，43.391 秒。包含删除参数/API/CLI 拒绝、无旧输出字段、恢复身份、直接容量现金、份额门禁、审计、compact/reference 等价与规模检查。
- [r2 真实数据验证](../../outputs/capacity_share_cleanup_20261004/r2/real/real_validation.json)：43,845 个容量订单上界检查 PASS；三组 100 MW / 200 MWh 滚动结果均 COMPLETE、内置独立语义回放 PASS。
- 月界窗口 192 个执行季度，最大 443 变量 / 68 二元；冬令时窗口 196 季度，最大 901 / 243；期末观察日窗口 192 季度，最大 860 / 232。合计 580 季度，规模与取消系数前的月度份额版一致。
- `git diff --check` 通过；生产 `src/ro_milp/` 搜索旧系数、旧门禁与 posthoc 无匹配。
- r1 证据作为首轮版本保留；最终验收对应 r2，不混用源码 hash。

## 文件变更

本轮修改：`src/ro_milp/config.py`、`core.py`、`audit.py`、`cli.py`、`rolling.py`、`shares.py`；`tests/test_model.py`、`test_capacity_shares.py`；README 和旧数学、旧输入输出、旧运行指南、月度份额首版增补的现行导航。

本轮新增：`tests/test_removed_income_factors.py`、本目录 [现行模型与运行说明](current_model_and_usage.md)、本审核记录，以及 `outputs/capacity_share_cleanup_20261004/r1/`、`r2/` 验证记录。月份额 CSV 未修改，旧历史结果与求解器快照保留。本轮没有执行 Git 暂存、提交或推送。

## 来源、假设与未关闭研究事项

官方来源沿用现有 Transelectrica/DAMAS `tenderStatistics`、`ansContractPurchasedReserves`、`ansTenderResults` 登记；本次无新下载或官方规则认定。字段、原件和来源定位见 [月度研究](../romania_monthly_share_calibration_20261004/月度容量份额上限建议.md)。

需求和供应商原始数据属于数据事实；用供应商分布解释份额属于研究解释；月份额、代理月份及取消旧收入折减属于建模假设/用户决定，不是监管上限或真实中标概率。

194 份附件缺失、代理月份、单份发布日期未独立核实，以及 FCR 激活损耗/额外循环、价格代理、项目资格等旧研究局限仍保留。旧 100%/80%/60% 报告不自动成为新版结果；本次未重跑完整 608 天。
