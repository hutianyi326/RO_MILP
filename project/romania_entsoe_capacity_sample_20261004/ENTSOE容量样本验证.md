# 罗马尼亚 ENTSO-E 容量报价与签约容量样本验证

验证日：2026-10-04。交付日：2026-08-31，Europe/Bucharest；对应 UTC 区间为 `[2026-08-30 21:00, 2026-08-31 21:00)`。本次为单日接口和字段验证，不代表全历史覆盖审核通过。未修改生产 MILP、既有输入或测算结果。

## 结论

用户提供的 ENTSO-E API key 可用。已从官方 REST API 取得 FCR/aFRR 逐报价容量与价格，以及实际签约容量和均价，保存四个成功响应的原始 ZIP 与脱敏请求记录。无需为了这两个数据项另行申请 API 接口。是否适合全期稳定定时获取，仍需验证完整历史覆盖、分页、重试和限流。

本样本取得 21 条报价序列 × 24 小时 = 504 条记录；三类签约产品 × 24 小时 = 72 条记录。全部签约容量与 Transelectrica/DAMAS 供应商逐时明细相等；全部 API 数值与此前网页详情提取值相等。

| 指标 | FCR 对称 | aFRR 向上 | aFRR 向下 |
|---|---:|---:|---:|
| 系统需求 MW，来自 DAMAS | 128 | 175 | 175 |
| ENTSO-E 报价序列条数 | 3 | 10 | 8 |
| 已披露报价容量逐时均值 MW | 115.75 | 231.0833 | 260.5417 |
| 已披露报价容量逐时范围 MW | 95—133 | 208—305 | 186—292 |
| 实际签约容量逐时均值 MW | 115.75 | 175 | 175 |
| 签约量总和/披露报价量总和 | 100% | 75.7303% | 67.1678% |
| 与 DAMAS 精确签约容量的最大偏差 MW | 0 | 0 | 0 |
| 既有 `需求×满足比例` 估计量的最大偏差 MW | 0.12 | 0 | 0 |

以上比例仅描述该日披露样本，不是单个储能项目的中标概率，不是项目占系统需求的份额，也不是已验证的全市场中标率。

## 一、官方规则事实

1. **GL EB 12.3.F** 的定义是获选报价的申报容量与申报价格。可分割报价披露的是最大申报量，可能高于实际采购量；官方定义不保证披露所有落选报价。[S1]
2. **TR 17.1.B&C** 披露实际签约量及均价/边际价。对称 FCR 的 x MW 同时提供上下各 x MW 的能力，只对应一份容量价格，不能将两方向收入相加。[S2]
3. 本次 API 数据明确给出 `RON`、`MAW`、`PT60M`、`curveType=A03`；网页价格表头为 `RON/MW/ISP`，详情 ISP 为一小时。因此本样本归一单位为 RON/MW/h，不能把 `Daily` 合同类型误读为“价格按整日计”。[S3、S4]
4. A03 为分段常值表示；省略不变时点不等于缺失。解析时只在同一已发布 Period 内延续至下一变化点/区间结束；显式缺失值不得用前值代替。[S5]
5. 本样本产品类型为 `Local`。平台罗马尼亚说明提示：自 2024-07-01 起一部分历史标作 Standard 的数据应理解为 Local；后续全量提取不能仅按 Standard 标签过滤。[S3、S4]

## 二、经验证的地址与请求参数

官方接口：`https://web-api.tp.entsoe.eu/api`。鉴权 `securityToken` 从用户指定本地文件在内存读取，未复制密钥文件、未把密钥写入请求日志或报告。

共同时间参数：`periodStart=202608302100`、`periodEnd=202608312100`，均为 UTC。

| 数据 | 已验证参数 |
|---|---|
| FCR 获选报价申报量/价 | `documentType=A15`，`processType=A52`，`area_Domain=10YRO-TEL------P` |
| aFRR 获选报价申报量/价 | `documentType=A15`，`processType=A51`，`area_Domain=10YRO-TEL------P` |
| FCR 实际签约量及价格 | `documentType=A81`，`businessType=B95`，`processType=A52`，`type_MarketAgreement.type=A01`，`controlArea_Domain=10YRO-TEL------P` |
| aFRR 实际签约量及价格 | `documentType=A81`，`businessType=B95`，`processType=A51`，`type_MarketAgreement.type=A01`，`controlArea_Domain=10YRO-TEL------P` |

最终 A81 响应已经同时包含 quantity 和 procurement_Price.amount。最初使用旧 A81/A89 参数组合得到 400，属于参数不匹配，不能解释为样本缺失。失败请求及其不含密钥的官方错误响应保留在 sources 中，成功响应另存新目录，未覆盖原始文件。

网页入口：

- [Procured Capacity](https://transparency.entsoe.eu/balancing/capacity/procuredCapacity)
- [Volumes and Prices of the Contracted Balancing Reserves](https://transparency.entsoe.eu/balancing/capacity/volumesAndPricesContracted)

网页选择 UTC 单日可能返回跨界的相邻交付日合同，必须再按实际交付区间过滤。本次 API 查询精确覆盖 Bucharest 当地交付日。

## 三、价格交叉核对与解释

ENTSO-E 三类产品的 72 个逐时平均价格与既有 DAMAS `averageAcceptedPrice` 一致，浮点误差不超过 5e-16 RON/MW/h。本次 API 本身保留两位小数，原始文件的价值在于可追溯与机器读取，并没有增加价格小数精度。

但这些“Average”价格不等于供应商实际中标量加权价格：

| 价格口径，RON/MW/h | FCR | aFRR 向上 | aFRR 向下 |
|---|---:|---:|---:|
| ENTSO-E/DAMAS 逐时平均价格的全天时间均值 | 346.6700 | 36.1167 | 2.0717 |
| DAMAS 供应商成交结果全天中标容量时数加权均价 | 338.7581 | 36.8386 | 2.1802 |

FCR 三家报价分别为 345、380、315 RON/MW/h，算术均值四舍五入为 346.67；结合供应商逐时中标量计算的全天加权值为 338.7581。该日现有均价比加权均价高约 2.34%。这说明“平台均价=某一项目可获得的 pay-as-bid 报价”仍然是建模假设；改用 ENTSO-E 的同名均价不会自动消除该假设。上述单日差异不能外推为全期收益修正比例。

aFRR 价格对照为全天口径，不能把每日供应商平均价直接回填到每一个小时。后续若要重建逐时成交加权价格，需把报价明细与供应商实际中标量可靠关联。

欧元换算沿用已确认口径：按 Bucharest 当地交付日关联汇率。2026-08-31 对应既有汇率记录 `fx_fixing_date=2026-08-28`、`5.2584 RON/EUR`；本次所有 EUR 价格 = RON 价格 / 5.2584。汇率取值是复用现有已提取表，本轮未重新审计汇率来源与发布时点。

## 四、对市场份额约束的意义

**研究解释：**该源能补充已披露报价的价量形状，并提供比 `需求×满足比例` 更精确的签约量；它仍不能单独确定本项目的市场份额或中标概率。API TimeSeries mRID 是响应内序列编号，未发现 BSP 身份字段，不得当作跨日供应商 ID。

**保持的建模假设：**拟议份额约束仍使用 `R_FCR,t ≤ s_FCR × D_FCR,t`，`R_aFRR↑/↓,t ≤ s_aFRR × D_aFRR↑/↓,t`，并与项目资质/功率/SOC 约束共同生效。D 应取官方系统需求，不能换成 ENTSO-E 已签约量或获选报价容量之和。s 是待校准的项目份额上限，不把 75.73%/67.17% 直接写入模型。

建议后续以 DAMAS 带供应商身份的采购明细估计各供应商实际份额分布，以 ENTSO-E 获选报价明细校验价格及竞争容量。若要按项目报价模拟完整竞价出清，仍需验证完整落选报价覆盖、关联规则和报价可分割性；本次单日样本尚不能证明满足这些条件。历史份额用于完美信息研究可作事后情景，若用于可执行策略须遵守当时已发布信息的限制。

## 五、文件、检查及未关闭问题

- `sources/20261004T140214Z/bids_FCR.zip`、`bids_aFRR.zip`：两个成功 A15 原始响应。
- `sources/20261004T140636Z/contracted_FCR_v6.zip`、`contracted_aFRR_v6.zip`：两个成功 A81 原始响应。
- 各获取目录的 `receipts.json`：时间目录、参数、状态、文件大小与 SHA256，均不含密钥。
- `entsoe_observed_series.json`：此前网页详情的人工转录结构化值；已由 API 全量逐点校验。
- `entsoe_bid_hourly_20260831.csv`：504 行，含 RON/EUR 报价、MW、来源和匿名样本编号。
- `capacity_hourly_comparison_20260831.csv`：72 行，含需求、精确签约量、披露申报量、旧估计误差、均价与汇率。
- `validation_summary.json`、`validate_sample.py`：验证结果及可重复的本地解析核对。
- `download_api_sample.py`：最终已验证四组参数的采集脚本；不含密钥，运行时从仓库外指定路径读取。

检查通过：A03 展开与 24 小时边界、504/72 行唯一性、API 与网页值逐点相等、72/72 签约量与供应商合计一致、每日采购总量一致、72 行汇率关联完整。未运行 MILP。没有对本轮文件执行 git add/commit/push。

未关闭：全期覆盖与稳定下载验证；是否有被定义之外额外披露的落选/未采购时段报价、其完整性；跨源匿名报价与 BSP 的可靠对应；项目份额系数最终取值；均价和项目 pay-as-bid 报价的建模选择。未请求独立审核，本轮为主 Agent 样本验证。

## 官方证据登记

以下访问日期均为 2026-10-04。

| 编号 | 机构、标题、日期 | 定位与来源 |
|---|---|---|
| S1 | ENTSO-E，Procured Balancing Capacity [GL EB 12.3.F]，更新 2025-08-26 | Detailed description、Specification of calculation；[官方说明](https://transparencyplatform.zendesk.com/hc/en-us/articles/12826158642068-Procured-Balancing-Capacity-GL-EB-12-3-F) |
| S2 | ENTSO-E，Amount and Prices Paid of Balancing Reserves Under Contract [17.1.B&C]，更新 2025-08-26 | Detailed description、Specification of calculation、Comments；[官方说明](https://transparencyplatform.zendesk.com/hc/en-us/articles/12826309684756-Amount-and-Prices-Paid-of-Balancing-Reserves-Under-Contract-17-1-B-C) |
| S3 | ENTSO-E，罗马尼亚 2026-08-31 A15 原始响应，生成 2026-10-04 | sources/20261004T140214Z 两 ZIP 内 XML；area_Domain、TimeSeries、Period、Point；来源 https://web-api.tp.entsoe.eu/api，脱敏参数见 receipts.json |
| S4 | ENTSO-E，罗马尼亚 2026-08-31 A81 原始响应，生成 2026-10-04 | sources/20261004T140636Z 两 ZIP 内 XML；采购时间为 2026-08-28；TimeSeries/Period/Point；来源同上 |
| S5 | ENTSO-E，CurveType=A01 vs CurveType=A03，更新 2024-12-27；Query Response，更新 2025-12-09 | [A03 说明及示例](https://transparencyplatform.zendesk.com/hc/en-us/articles/30262342482961-CurveType-A01-vs-CurveType-A03)；[UTC 与区间说明](https://transparencyplatform.zendesk.com/hc/en-us/articles/15727773247124-Query-Response) |
| S6 | Transelectrica，ANS Contract Purchased Reserves，交付日 2026-08-31；页面未列独立发布日期 | Sheet 1，第 8 行表头，FCR/aFRR 明细；[原始供应商采购文件](https://www.transelectrica.ro/documents/10179/23693070/ansContractPurchasedReserves_31.08.2026.xlsx/3f4f16fe-98e3-42da-95c6-529266cbf603) |
| S7 | Transelectrica，ANS Tender Results，交付日 2026-08-31；页面未列独立发布日期 | Sheet 1，第 8 行表头，各服务供应商行与 Grand Total；[原始成交结果](https://www.transelectrica.ro/documents/10179/23693070/ansTenderResults_31.08.2026.xlsx/9ee778dd-9dfd-412c-8e48-5f0662a89774) |

S6/S7 原始文件复用 `../romania_external_benchmark_20261004/sources/` 的不可变下载件。

## 后续整月供应商校准

已补齐 2026 年 8 月 DAMAS 31 份逐小时采购表与 31 份日报，并与本报告 8 月 31 日 ENTSO-E 实际采购量交叉核对。详见 [DAMAS 供应商份额校准](supplier_calibration_aug2026/DAMAS供应商份额校准.md)。该补充提出 FCR / aFRR 两项份额上限的初版情景，不代表生产 MILP 已修改或新项目真实中标率已确定。

2025-01 至 2026-08 的扩展结果见 [月度容量份额上限建议](../romania_monthly_share_calibration_20261004/月度容量份额上限建议.md)。截至本轮，已验证 1,022 份附件，另有 194 份受连接故障影响未取得；扩展表明确区分当月样本、邻月代理和原基线禁用状态，不代表全期实测校准已完成。
