"""Write a status-aware research report from the current calibration outputs."""
from pathlib import Path
import json
import pandas as pd

ROOT=Path(__file__).resolve().parent
params=pd.read_csv(ROOT/'monthly_recommended_share_caps.csv')
coverage=pd.read_csv(ROOT/'monthly_data_coverage.csv')
checks=json.loads((ROOT/'validation_summary.json').read_text())

def status(s):
    if s.startswith('disabled'):return '沿用原基线禁用'
    if s.startswith('proxy_next'):return '后月代理，非当月实测'
    if s.startswith('proxy_previous'):return '前月代理，待补证'
    if 'partial_month' in s or 'valid_sample' in s:return '当月部分样本'
    return '当月完整样本'

def mw(a,b):
    if pd.isna(a):return '—'
    return f'{int(a)}' if a==b else f'{int(a)}—{int(b)}'

table=['| 月份 | FCR 建议上限 | FCR 依据 | aFRR 共用建议上限 | aFRR 依据 | aFRR 整数 MW 上限范围 |',
       '|---|---:|---|---:|---|---:|']
for _,r in params.iterrows():
    f='禁用（输入 0）' if r.fcr_status.startswith('disabled') else f'{100*r.fcr_market_share_cap:.4f}%'
    table.append(f'| {r.month} | {f} | {status(r.fcr_status)} | {100*r.afrr_market_share_cap:.4f}% | {status(r.afrr_status)} | {mw(r.afrr_up_cap_min_integer_mw,r.afrr_up_cap_max_integer_mw)} |')

cov=['| 月份 | FCR 产品有效日 / 月天数 | PETROM 披露有效日 | aFRR 上 / 下有效日 | aFRR 上 / 下参考供应商数 |',
     '|---|---:|---:|---:|---:|']
sup=pd.read_csv(ROOT/'monthly_supplier_summary.csv')
for _,r in params.iterrows():
    c=coverage[coverage.month==r.month].set_index('product')
    p=sup[(sup.month==r.month)&(sup['product']=='FCR')&(sup.bsp=='30XROPETROM----4')]
    cov.append(f"| {r.month} | {int(c.loc['FCR','valid_days'])}/{int(c.loc['FCR','expected_days'])} | {int(p.reported_days.iloc[0]) if len(p) else 0} | {int(c.loc['aFRRUp','valid_days'])}/{int(c.loc['aFRRDown','valid_days'])} | {r.afrr_up_peer_count}/{r.afrr_down_peer_count} |")

all_downloaded=checks['all_source_files_downloaded']
missing=checks['expected_source_files']-checks['files_verified']
state='原始附件已全部取得；校准仍须区分产品缺项及代理月份。' if all_downloaded else f'**尚未完成全期实测补齐**：应取得 {checks["expected_source_files"]:,} 份官方附件，已取得并校验 {checks["files_verified"]:,} 份，剩余 {missing} 份受官网连接故障影响。表中代理参数仅为暂行研究建议。'

report=rf'''# 罗马尼亚 2025-01 至 2026-08 月度容量份额上限建议

研究日期：2026-10-04。研究对象：100 MW / 200 MWh 独立储能。月界与交付日：Europe/Bucharest。

{state}

已形成 20 个月、FCR 与 aFRR 两项输入的建议表；未修改生产 MILP、既有价格输入及测算结果，未进行独立 Agent 审核。建议值是基于历史供应商组合份额的建模假设，不是官方市场限制，也不是新项目真实中标概率。

## 月度建议表

{chr(10).join(table)}

FCR 在 2025 年 6—12 月的建议份额为 40/116 = 34.48275862%，在 2026 年为 40/128 = 31.25%，均对应 40 MW 研究上限。部分月份借用邻月参数，不能称为当月校准值。

2025 年 1—5 月的 FCR 输入 0 是沿用既有模型缺少 FCR 市场输入时禁用该市场的处理，不代表官方需求为零、市场不存在或项目中标率经统计为零。

表内 aFRR 两个方向共用一个系数，并各自乘当小时需求。2025 年 10 月需求由 200 MW 变为 175 MW，因此同一月度份额对应不同 MW 上限。表中 MW 为当前 1 MW 整数粒度下向下取整结果；原始未取整数值及小数系数见 CSV，实施时应使用完整精度，不能从四位小数百分比反算。

## 规则事实与数据事实

第一方资料为 Transelectrica 官网的 DAMAS 导出附件：`ansContractPurchasedReserves`（逐小时采购）与 `ansTenderResults`（日报）。在已核验重叠时段，Excel 的需求量与项目既有 DAMAS `tenderStatistics` 需求量完全一致。

已有官方需求序列显示：FCR 在 2025 年 6—12 月为 116 MW、2026 年 1—8 月为 128 MW；aFRR 上下调 2025 年 1—9 月各 200 MW、2025 年 10 月在 200/175 MW 之间变化、此后各 175 MW。这些是本期数据观察值，不是永久固定的规则参数。

对每个供应商，先按 EIC 合并同小时的多笔中标，再除以当时的系统需求。BID 编号只在同一张表内去重，不用于跨报表强行配对；不同报表存在 BID 顺序错位。

## 研究解释与明确的建模假设

原 8 月方法的数学口径保持不变：

\[
s_{{F,m}}=Q_{{0.90}}\left(\frac{{Q^{{award}}_{{\mathrm{{PETROM}},F,t}}}}{{D_{{F,t}}}}\right),
\]
\[
u_m=\operatorname{{median}}_b\left[Q_{{0.90}}\left(\frac{{Q^{{award}}_{{b,aU,t}}}}{{D_{{aU,t}}}}\right)\right],\quad
d_m=\operatorname{{median}}_b\left[Q_{{0.90}}\left(\frac{{Q^{{award}}_{{b,aD,t}}}}{{D_{{aD,t}}}}\right)\right],\quad
s_{{A,m}}=\min(u_m,d_m).
\]

P90 使用 NumPy 的线性插值分位数；零中标小时在实际披露的供应商日内保留。供应商整日没有出现的情况不擅自补零。BSP 是资产组合，未按其合格资产规模标准化。选择 PETROM、P90、中位数以及上下调取较小值，均为研究假设。

历史文件覆盖不如 8 月完整，因此新增以下**样本准入假设**，不得误称为官方要求：

1. FCR：固定 PETROM 参照，只有其有效披露小时达到当月日历小时的 80%、且存在正中标小时，才给出当月直接估计。80% 是数据覆盖门槛，不是中标率。
2. aFRR：该产品经两表对账的有效小时须覆盖当月至少 90%；供应商须覆盖全部这些有效小时、且全月至少有一次正中标。完整月份和部分有效月份分开标注。90% 同样是覆盖门槛。
3. 不满足条件的月份，优先暂用最近前一个有效月份；没有前月可用时，使用最近后一个有效月份并明确标记为事后代理。代理参数不填入直接估计字段，参考月份另列。
4. 全部系数都用整月事后数据计算。即使不是代理，也不能作为该月开始时已知的可执行预测输入。回测仍属于事后完美信息研究。

2025 年 6 月 PETROM 只在一个有效日出现，且该日中标量为零，无法用它识别一个新的 100 MW 项目份额；本表暂借 2025 年 7 月的 34.4828%。2025 年 12 月仅有 17 个有效 PETROM 日，不满足 80% 门槛，暂借 11 月。2026 年 4 月已取得的有效 FCR 样本中没有 PETROM，因此 FCR 暂借 3 月。2026 年 4—7 月 aFRR 暂借 3 月的 14.28571429%，这些月份必须优先补证。

该方法的局限是：完整披露供应商筛选存在选择偏差，某些早期月份 aFRR 仅有 3 个合格参考供应商；这不能证明项目规模和报价不影响份额，也不能表示统计置信区间。FCR 的 40 MW 是选择特定同业后的参照，不能认为其他供应商也会获得该容量。

## 覆盖及未解决事项

{chr(10).join(cov)}

产品有效日只计两类报表均具备该产品、供应商集合一致、供应商日量与小时量一致的日期。下载成功但只导出其他服务的文件不会被当成完整数据。完整月份的供应商记录仍可能仅覆盖部分天数。

本轮未取得的附件为 2026-04-26 至 2026-07-31 两类文件，共 97 天、194 份；2026 年 8 月复用上一轮成功下载件。连续失败表现为 HTTPS/TLS 握手被关闭（Python `UNEXPECTED_EOF_WHILE_READING`，系统客户端同样失败）。已暂停批量请求，并试过冷却、单连接重试；未关闭证书验证，未使用 API key 请求公开附件。缺少的确切 URL 见 `pending_source_downloads.csv`。

部分已下载官方附件仅导出一种服务。例如 2025-10-23 的日报只有 FCR，逐小时表只有 aFRR，无法互相对账；不跨日拼接、不用邻日供应商量冒充当日观察。

另外发现，2025-10-26 夏令时切换日的第 25 小时，即本地 23:00、UTC 21:00，三个产品均有本次 Excel 记录，但未出现在现有 `capacity_native_hourly_eur.csv`。该缺口已在既有 `dst_gap_recheck.json` 中记录，原因是当时 DAMAS 统计接口仅给出 24 个价格小时。本次另列 3 行容量差异，补充了需求和供应商数量证据，但不能据此填造缺失价格；**没有修改既有 MILP 输入或自动恢复相关订单**。

## 已执行检查

- {checks['files_verified']:,} 份附件 SHA-256 验证；{checks['days_parsed']} 个交付日解析，致命解析错误为 0。
- {checks['product_days_reconciled']:,} 个产品日、{checks['supplier_days_reconciled']:,} 个供应商产品日完成总量对账。
- 纳入 {checks['market_hours']:,} 个产品小时、{checks['supplier_hours']:,} 个供应商小时；同时检查重复键、非负容量及实际日长。
- {checks['overlapping_native_demand_hours_checked']:,} 个与既有需求输入重叠的小时，需求值全部相同；3 个新增 Excel 小时单独登记。
- 夏令时按实际 23/25 小时处理，不能按每月天数乘 24 强行补齐。
- 空白数量仅在其他已知非负数量恰好覆盖官方总量时推定为零，并保留日志；其余问题不静默插值。
- 自动按表头名称取列。部分日报增加 `OFFERED_POWER` 列，不能把固定第 8 列误读为中标量。表头也可能不在第 8 行。
- 2025-10-23 日报没有中标量列；其 FCR 日量可按 `TOTAL_COST / AVERAGE PRICE` 反推并标注来源方式，但因缺少对应小时表，未纳入份额校准。
- 2026 年 8 月系数重现上一轮结果：FCR 31.25%、aFRR 13.71428571%。本轮没有新增全期 ENTSO-E 核验；上一轮双源核验仅为 2026-08-31。

**已取得子样本的上述核对通过，不等于全期数据完整性审核通过。**

## 拟接入方式

对订单覆盖的每个小时取当月系数及当小时官方需求；订单容量不得超过所有覆盖小时上限的最小值，并继续受功率、资格容量、SOC 和已有物理约束限制。月度系数只改变容量变量上界，不直接乘收入，也不需要增加逐小时二元变量。

FCR 对称容量计一次；aFRR 上下调分别受同一系数乘各自方向需求的限制。现有容量现金系数建议仍保持 100%，避免与份额限制重复叠加。计算收入和激活时均使用实际优化后的中标容量。

## 来源及文件

| 机构与资料 | 文件日期与位置 | 用途 |
|---|---|---|
| Transelectrica / DAMAS，[官方辅助服务资料目录](https://www.transelectrica.ro/ro/web/tel/info-sts) | `ansContractPurchasedReserves`、`ansTenderResults`；交付日期 2025-01-01—2026-08-31。每个文件实际表头行及列名见 `source_schema_inventory.csv`；单份正式发布日期未独立核实 | 供应商中标量、需求量、两表校核 |
| Transelectrica / DAMAS，`tenderStatistics` 公共报表 | 已有项目数据 `data/processed/RO/prices_eur_v1_20261002/capacity_native_hourly_eur.csv`；`demand_mw`、`delivery_start_utc`、`source_key`；[官方平台](https://newmarkets.transelectrica.ro/) | 需求序列的独立重叠核对、完整月份需求范围 |
| ENTSO-E，[Procured Balancing Capacity, GL EB 12.3.F](https://transparencyplatform.zendesk.com/hc/en-us/articles/12826158642068-Procured-Balancing-Capacity-GL-EB-12-3-F) | 更新 2025-08-26；Detailed description / Specification of calculation；既有样本研究 | 仅接受报价的披露，不构成全市场落选报价全集 |

新增文件获取/访问日期为 2026-10-04。所有官方附件 URL 与哈希见 `selected_sources.json` 及不可变 `sources/<获取时间>/receipts.json`；预期完整清单见 `source_inventory.json`。份额无币种；小时容量为 MW，日报汇总为 MW·h 容量时，不是激活电量。本轮没有做汇率换算。

主要交付：

- `monthly_recommended_share_caps.csv`：20 行建议参数、直接估计、代理参考月份、样本状态、需求范围及整数 MW 上限。
- `monthly_supplier_summary.csv`、`monthly_data_coverage.csv`：逐月供应商统计和覆盖率。
- `supplier_hourly_shares.csv.gz`、`supplier_daily_awards.csv`、`market_hourly_demand_and_awards.csv`：可追溯计算底表。
- `pending_source_downloads.csv`、`data_issues.csv`、`zero_inference_log.csv`、`cross_report_bid_number_mismatches.csv`：待补资料和数据处理日志。
- `available_daily_offered_quantities.csv`：部分日报额外披露的报价容量，供后续研究。披露不连续，本次未用来估计中标概率。
- `validation_summary.json`：检查结果和全期尚未下载完成的状态。

网络恢复后，可运行 `download_sources.py` 只补下载缺失文件；完整下载后运行 `analyze_months.py`（默认检查全部 1,216 份齐备），再运行 `write_report.py`。如仍只分析当前样本，必须显式使用 `--available` 并保留未完成状态。脚本仅用于研究数据处理，不改变生产 MILP。
'''
(ROOT/'月度容量份额上限建议.md').write_text(report,encoding='utf-8')
print('Written monthly calibration report; all_source_files_downloaded =',all_downloaded)
