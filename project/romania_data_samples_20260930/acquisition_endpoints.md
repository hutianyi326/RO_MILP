# 罗马尼亚各市场数据获取地址与接口实测汇总

整理日期2026-09-30。本文件汇总已审核样本的地址和非敏感参数，不是新增数据可用性研究。F为本轮实际请求/官方页面观察，I为复用模板。成功仅表示对应样本成功，不证明20个月全期、接口长期稳定、所有字段有效或历史当时可见。精确请求、结果、时间和原件哈希见[来源目录](../../countries/RO/data_samples_20260930/source_catalog.csv)和[原件清单](../../countries/RO/data_samples_20260930/raw_manifest.json)。

## 1. OPCOM现货市场

| 市场/数据 | 官方地址或模板 | 方法/参数 | 本轮实测 |
|---|---|---|---|
| 日前DA网页 | https://www.opcom.ro/grafice-ip-raportPIP-si-volumTranzactionat/en | 日期/粒度选择 | 成功 |
| DA原生CSV | `https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv/{DD}/{MM}/{YYYY}/en?resolution={60或15}` | GET；2025-10-01以前60、之后15 | 96日成功，含三个整月；保留原生粒度，不用60替代切换后的15 |
| DA XML | `https://www.opcom.ro/rapoarte-pzu-raportPIP-export-xml/{DD}/{MM}/{YYYY}/en?resolution=15` | GET | 2025-10-26成功，与同源CSV100区间一致；不是独立机构交叉核验 |
| IDA逐轮结果 | https://www.opcom.ro/rapoarte-ida-rezultate-licitatii/en | POST公开日期表单，详下 | 7日3轮模板；2025-10-01 IDA2有46个价量对，其余轮日无数字价格；部分成功 |
| IDCT连续日内 | https://www.opcom.ro/rapoarte-pi-rezultate-pi/en | POST公开日期表单，另加tip=15 | 2026-08-31 PT15成功143行；缺成交时刻、ID和完整交付日 |
| 聚合报价曲线页面 | https://www.opcom.ro/rapoarte-pzu-curbe-agregate/en | POST日期day/month/year；页面Download给出XML/PDF | 2026-08-31成功 |
| 曲线XML | `https://www.opcom.ro/order_book/curbe_agregate_RO_{YYYYMMDD}.xml` | GET；模板来自选定日期页面的实际下载按钮 | 一日成功；混合15/30/60分钟、供需曲线及块订单；无机组技术身份 |
| 曲线PDF | `https://www.opcom.ro/pdf_curbe/curbe_agregate_RO_{YYYYMMDD}.pdf` | GET | 一日96页图成功 |
| 月报目录 | https://www.opcom.ro/tranzactii-rezultate/en/22 | GET目录及明确列出的PDF | 2025-01、2025-10、2026-08已获取 |
| 月报PDF样本 | https://www.opcom.ro/uploads/doc/rapoarte/lunar/R_2510_EN.pdf | GET；`R_{YYMM}_EN.pdf`是已见命名模式，其他月份仍须核目录/响应 | 十月成功，用于同源对账，不作逐QH插值 |

DA可点击的成功样本：[2025-01-15小时CSV](https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv/15/01/2025/en?resolution=60)、[2025-10-01 QH CSV](https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv/01/10/2025/en?resolution=15)、[2026-08-31曲线XML](https://www.opcom.ro/order_book/curbe_agregate_RO_20260831.xml)。

IDA表单示例（日期格式MM/DD/YYYY）：

```json
{"ziua_eng":"10/01/2025","action":"trading_for","limba":"en","buton":"Refresh"}
```

IDCT示例：

```json
{"ziua_eng":"08/31/2026","action":"trading_for","limba":"en","buton":"Refresh","tip":"15"}
```

本轮取数先GET页面取得临时匿名表单会话与公开CSRF字段，再POST。实际下载辅助材料为fetch_public.ps1及requests_days.json/requests_retries.json。回执不保存CSRF token/cookie/账户凭据，不把该流程写成可免除账号授权的API。HTML空值“-”不当0；POST成功不表示字段完整。

## 2. Transelectrica / DAMAS II

公共网页入口：[DAMAS II](https://newmarkets.transelectrica.ro/)。以下地址是本轮公开页面后台实际使用的匿名GET路线，返回JSON；**没有取得正式API文档或服务稳定性承诺**。官方UI导出本轮未取得文件，这些JSON请求成功作为样本证据保留。

共同地址前缀：

```text
https://newmarkets.transelectrica.ro/usy-durom-publicreportg01/00121002500000000000000000000100/publicReport/
```

| 市场/数据 | 前缀后的接口路径 | 请求参数 | 本轮结果/限制 |
|---|---|---|---|
| FCR/aFRR/mFRR容量招标列表 | `tenderStatistics` | timeInterval.from、timeInterval.to、pageInfo.pageSize | 七日成功；可能返回相邻交付日，按招标UTC交付期再次筛选并去重 |
| 招标详情/逐服务统计 | `tenderStatisticsDetail` | tenderCode，如488_2026、484_2026 | 成功；提供需求、满足率、统计价格、供方及事件；DST和价格分母仍有未决 |
| 系统激活能量 | `activatedBalancingEnergyOverview` | 同一组时间范围/分页参数 | 七日成功，QH/MWh；产品/方向null保留，不映射本站 |
| 平衡能量边际价格 | `marginalPricesOverview` | 同上 | 七日成功；UI仅LEI，运行维度及最终性待核，绝非偏差价格 |
| 毛负荷实际/预测 | `dailyConsumptionOverview` | 同上 | 七日成功，QH/MW；最新预测不是历史vintage |
| 跨境商业交换计划 | `scheduledExchanges` | 同上，但来源日按CET/CEST构造 | 七日成功，QH/MW；不是物理潮流或NTC/ATC |
| 报表元数据 | `metadata/get` | reportCode，如tenderStatistics、dailyConsumptionOverview、scheduledExchanges | 已用样本成功，返回timeZone/maxPageSize/global lastUpdate；不等于取得观测或历史版本 |

时间序列实际GET示例（2026-08-31 Bucharest日对应2026-08-30 21:00Z至31日21:00Z）：

```text
activatedBalancingEnergyOverview?timeInterval.from=2026-08-30T21%3A00%3A00Z&timeInterval.to=2026-08-31T21%3A00%3A00Z&pageInfo.pageSize=3000
```

成功详情样本：[FCR 488_2026](https://newmarkets.transelectrica.ro/usy-durom-publicreportg01/00121002500000000000000000000100/publicReport/tenderStatisticsDetail?tenderCode=488_2026)、[FRR 484_2026](https://newmarkets.transelectrica.ro/usy-durom-publicreportg01/00121002500000000000000000000100/publicReport/tenderStatisticsDetail?tenderCode=484_2026)。

参数必须按来源时钟转换UTC，不能统一使用当地日期字符串：容量/激活/边际价/毛负荷为EET/EEST，scheduledExchanges为CET/CEST；春秋DST是真23/25小时日。本轮各系统报告样本返回条数与pageInfo.total一致；全期需要重新核分页、最大范围、重复/修订和字段变更，本轮没有验证全期翻页流程。

## 3. 尚未验证成功的核心出口

| 数据 | 本轮地址/动作 | 结果及下一步 |
|---|---|---|
| 最终偏差价 | DAMAS UI finalImbalancePrices；单次候选后台路径`finalImbalancePrices` | UI组件失败，候选route404；**不能列为成功或确定API**，global metadata成功也没有价格 |
| 正式结算结果 | https://www.transelectrica.ro/web/tel/rezultate-decontare-piata-de-echilibrare | 从既有E08明确链接发现，两次HTTP取数超时/520，未得原件；继续官方出口取数，不推历史无数据 |
| 原生分技术出力/物理流/NTC等 | https://transparency.entsoe.eu/ | 本轮仅入口；未导出或验证正式API访问及RO请求参数。没有API token，不把候选代码填为已验证 |
| BNR历史账务汇率 | https://www.bnr.ro/23988-cursurile-pietei-valutare-in-format-xml | 目录可读但未取得数值XML；旧候选地址重定向首页，不当成功汇率出口 |
| 历史气象/停运/燃料 | ANM/TSO/ENTSO-E已定位入口 | 没有完成原生历史序列出口验证；不能列为已确认API |

## 4. 汇率展示与结构/费用资料

ECB已成功GET日度RON/EUR参考汇率：

```text
https://data-api.ecb.europa.eu/service/data/EXR/D.RON.EUR.SP00.A?startPeriod=2026-08-01&endPeriod=2026-08-31&format=csvdata
```

三个代表月共66工作日值。只用于研究展示，不替BNR结算汇率，不前填周末。[ECB参考用途说明](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html)。

年度装机/发电结构：[TSO 2025报告目录](https://www.transelectrica.ro/ro/web/tel/rapoarte-2025)；ANRE控制资料：[2025-12市场监测PDF](https://anre.ro/wp-content/uploads/2026/03/Monit-dec25-cu-eticheta.pdf)；现行费率：[OPCOM 2026 NEMO表](https://www.opcom.ro/uploads/doc/FPA/1Lg_eng_Procedure%20NEMO.pdf)。这些是PDF/网页资料地址，不能当原生时序API或全期历史费率。

## 5. 精确请求文件对应关系

| 用途 | 已保存请求文件 |
|---|---|
| DA/IDA/IDCT边界日 | requests_days.json、requests_retries.json；三个整月DA程序见fetch_months.py |
| 容量/激活 | requests_damas.json、requests_balance_samples.json、requests_supplement.json |
| 能量边际价/毛负荷 | requests_prices_load.json、requests_retry_final.json |
| 商业交换/年报/监测 | requests_exchanges_reports.json、requests_retry_final.json |
| 最终偏差失败及后续正式结算入口 | requests_final_probe.json、requests_settlement_followup.json、requests_settlement_retry.json |
| ECB/曲线/费率 | requests_ecb.json、requests_last_sources.json |

所有文件在本汇总同目录。raw_manifest/source_catalog给每一次实际请求的非敏感参数与结果，不能只拿API路径名称判“该市场数据已经齐全”。本汇总是既有证据的便读索引，不修改三轮审核、原件、已批准范围或国家状态，未运行新取数、测试或收益测算。
