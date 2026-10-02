# 罗马尼亚 aFRR 补充研究范围与证据目录

研究日期：2026-10-02。范围为用户本轮要求的一个月激活收入样本、容量总报价量来源搜索、50 个不可计算季度及另 1,739 个比例超限季度的原因和偏差。研究期为 2025-01 至 2026-08，IDA 不进入 MILP。

主线程执行研究，并批准本轮新增 `project/romania_afrr_deepresearch_20261002/` 与 `data/raw/RO/afrr_deepresearch/20261002/`。旧研究、原件、国家状态、模型和生产代码不改写。新下载按获取回执和 SHA256 保存，不覆盖失败回执或旧版原件。最初下载因本地网络沙箱拒绝失败；允许网络的后续下载另存 `_NET` 批次，不将此类失败计为官网无数据。

F 表示官方原件事实，I 表示研究计算或解释，A 表示可选建模假设，U 表示未确认事项。下载成功只表示本次请求成功；不表示接口 SLA、全历史最终性或当时可见性。

## 本次访问的官方资料

所有以下资料访问日为 2026-10-02；精确 UTC 获取时间、请求 URL、原件位置和哈希见各 `requests_*_results.json` 及原件 `receipt.json`。未标发布日期的页面不以访问日代替发布日期。

| 来源 ID | 机构和文件 | 发布或适用时间 | 证据位置和链接 |
|---|---|---|---|
| S01 | Transelectrica DAMAS II Marginal prices overview | 交付 2025-08；首次发布时间、修订时间未给出 | `marginalPricesOverview_2025-08_NET` 原件 `itemList[].timeInterval/aFRR_Up/aFRR_Down`；[公共报表页面](https://newmarkets.transelectrica.ro/uu-webkit-maing02/00121011300000000000000000000100/marginalPricesOverview) |
| S02 | Transelectrica DAMAS II Activated balancing energy overview | 交付 2025-08 及复查日；首次发布未知 | `activatedBalancingEnergyOverview_2025-08_NET`、`ACT_RECHECK_*`；[公共报表页面](https://newmarkets.transelectrica.ro/uu-webkit-maing02/00121011300000000000000000000100/activatedBalancingEnergyOverview) |
| S03 | Transelectrica DAMAS II Tender statistics detail | 310_2025 对应 2025-08-15，469_2025 对应 2025-10-26，90_2026 对应 2026-02-15 | `tenderServiceList[].tenderStatistics.timeIntervalList`、`contractedPower`；[已实测详情接口](https://newmarkets.transelectrica.ro/usy-durom-publicreportg01/00121002500000000000000000000100/publicReport/tenderStatisticsDetail?tenderCode=469_2025) |
| S04 | Transelectrica Piata centralizata de servicii de sistem Informatii | 公告按各交付日；页面首次发布时间未给出 | [官方目录](https://www.transelectrica.ro/ro/web/tel/info-sts)；本轮从等价 `/web/tel/295` 取得目录与原始附件链接 |
| S05 | Transelectrica ANS Tender Results 五个 Excel | 2025-08-01、15、31，2025-10-26，2026-02-15 | 每份 `Sheet 1!A3:I8` 的元数据和字段；逐产品 Grand Total 行定位见 `capacity_excel_crosschecks.csv`；[8 月 15 日原件](https://www.transelectrica.ro/documents/10179/19555508/ansTenderResults_15.08.2025.xlsx/b00c60f6-e2c4-43ae-922d-d6d9363ff5df)、[秋季 DST 原件](https://www.transelectrica.ro/documents/10179/20076622/ansTenderResults_26.10.2025.xlsx/65b2c7e9-2a49-4e7e-a644-17988d769eed) |
| S06 | Transelectrica Model XML pentru transmiterea ofertelor de capacitate de echilibrare | 模板未标发布日期 | [ANS_bids.xml](https://www.transelectrica.ro/documents/10179/38928/ANS_bids.xml/f2539b9f-80b3-4c29-b27d-eb06a968888f)；`ReserveBidDocument`、占位符、`TS/P/I`；报送模板不是历史报价数据 |
| S07 | ENTSO-E Procured Balancing Capacity GL EB 12.3.F | 官方帮助页更新 2025-08-26 | [详细定义](https://transparencyplatform.zendesk.com/hc/en-us/articles/12826158642068-Procured-Balancing-Capacity-GL-EB-12-3-F)；Detailed description 和 Specification of calculation，accepted offers 范围及部分接受例子 |
| S08 | ENTSO-E Balancing energy bids GL EB 12.3.B&C | 官方帮助页更新 2025-08-26 | [详细定义](https://transparencyplatform.zendesk.com/hc/en-us/articles/12826669342996-Balancing-energy-bids-GL-EB-12-3-B-C)；产品、报价量 MW、能量价格及报价范围；这是能量报价，不是容量报价 |
| S09 | 罗马尼亚司法部 Portal Legislativ，ANRE 127/2021 附件规则合并网页 | 原规章 2021-12-08；页面包括 2024 修订说明；不宣称完整覆盖所有后续修订 | [法规原文](https://legislatie.just.ro/Public/DetaliiDocument/280280)；Art.38–39（有合同和无合同能量报价）、Art.63（本地报价币种/分母）、Art.90–93（结算和支付方向）。本地直连失败，官方全文经联网浏览工具成功读取；不可把失败回执称为本地完整法规原件 |
| S10 | Transelectrica 托管 DUROM WebService Interface 参与者指南 | 文档版权页 2023；修订记录另存，文件 URL 非发布日期证明 | [官方 DOCX](https://www.transelectrica.ro/documents/10191/16424922/DUROM-Web_+Services_v01.02_Participanti_22.docx/01d4e2f4-a785-41e8-a87e-1c5540094c85)；Transfer Technology、Web Service Security、Data Flows for Data Download；用户权限认证不等于全市场数据权限 |
| S11 | Transelectrica Monitorizarea funcţionării pieţelor，TEL-07.V OS-DN/265 | 批准封面 2019-04-11；历史流程线索，不替代 2025—2026 最新规则 | [官方 PDF](https://www.transelectrica.ro/documents/10179/146982/Procedura%2Bmp.pdf/33aa6994-f1ef-4ff7-8f88-bb499815d77e)；PDF p7 §8.1.4(a)(b)记录逐日逐时容量报价与合同量分别供内部监测；公开汇总及商业敏感信息处理段 |
| S12 | Transelectrica DAMAS II 匿名公共网站配置与页面定义 | 当前公开页面快照；配置更新时间不是交易数据发布时间 | 从官方首页实际引用的 `userGate.js` 发现只读 `loadWebsite` / `loadWebPage`；`DAMAS_PUBLIC_WEBSITE_CONFIG` 的 `routes`、`websiteStructure.itemMap`，`PAGE_*` 页面定义；没有据此声称未列出的接口绝不存在 |

## 复用的已审资料

1. `countries/RO/full_period_20261001/raw_manifest.json` 所列 20 个月容量和激活原件，共 40 份，本轮独立按原件复算并验证哈希。原件访问时间仍保留 2026-09-30，不改成本轮日期。
2. `countries/RO/full_period_20261001/capacity_statistics.csv`、`capacity_provider_sum_checks.csv`、`activatedBalancingEnergyOverview.csv`：作为诊断对象，不直接批准为模型输入。
3. `countries/ES/MILP/research/spain_milp_mathematical_spec_2026-09-16.md` v2.0/v2.1：三相及仅折减容量收入的中标率敏感性口径。
4. E67：Transelectrica FRR/RR 容量采购程序 TEL 04.05 Rev2，PDF p12–13 §8.7–8.8，及 §9.1.10。原始 URL、日期、哈希在 `countries/RO/rules_20260930/sources.csv` 的 E67 行。公开采购结果不等于所有有效报价曲线。
5. [2025 年 8 月 STS 月报](https://www.transelectrica.ro/documents/10179/18723178/2025-08-STS-Raport.pdf/1c2cc5bf-e0f5-48ff-bc12-2019c164623c)：第 5 页容量和可用调节能量统计、后续日价格表；月度汇总不可替代小时容量报价分母。报告期不是发布日期。

## 获取方式

公开 JSON 基础路径为 `https://newmarkets.transelectrica.ro/usy-durom-publicreportg01/00121002500000000000000000000100/publicReport/`。

8 月样本使用 `marginalPricesOverview` 和 `activatedBalancingEnergyOverview`，GET 参数：`timeInterval.from=2025-07-31T21:00:00Z`、`timeInterval.to=2025-08-31T21:00:00Z`、`pageInfo.pageSize=3000`、`pageInfo.pageIndex=0`。两个响应的 `pageInfo.total=2976`，元数据报告 `timeZone=EET` 和 `maxPageSize=10000`。实际时间索引用 Europe/Bucharest 和 UTC，不把 EET 字面当全年固定 UTC+2。

逐日容量 Excel 的路径带文件库编号和 UUID，应从官方目录提取，不仅替换日期猜测 URL。样本虽可匿名下载，接口服务稳定性、历史版本、发布时刻和全体数据授权仍不由本次成功保证。
