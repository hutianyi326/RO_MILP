# 公开页面与下载路线实测记录

访问日期2026-09-30。此记录是主线程观察I；对应HTTP原件、公开响应及非敏感参数以source_catalog.csv和raw_manifest.json为准。未保存账号凭据，未申请/发送外部询问。

| 页面 | 实测及定位 | 不能推导的结论 |
|---|---|---|
| https://www.opcom.ro/grafice-ip-raportPIP-si-volumTranzactionat/en | S001日期和粒度选择、CSV/XML公开导出；resolution=60/15按原生合同 | 未测20个月全部日期；不是实时下单接口 |
| https://www.opcom.ro/rapoarte-ida-rezultate-licitatii/en | 七日POST的ziua_eng值逐一核验；2025-10-01 IDA2有46段数字价量，buy字段“-”；其余20轮日无数字价格 | 局部数值不证明三轮完整；“-”不填0，不推历史没有拍卖 |
| https://www.opcom.ro/rapoarte-pi-rezultate-pi/en | 选择2026-08-31、tip=15，Trades concluded in、Price €/MWh、Volume MWh | 没有完整交付日期或trade_time；不能保证时点成交 |
| https://www.opcom.ro/rapoarte-pzu-curbe-agregate/en | CURVES_2026-08-31已选日期；两个Download按钮onclick明确给出pdf_curbe与order_book的官方URL | XML创建时刻不是公开时刻；不是机组身份表 |
| https://newmarkets.transelectrica.ro/ | 浏览器可打开公共区；UI导出等待未得到文件。公开页资源清单暴露匿名GET报表路线，实际取回JSON | 这些是页面后台路线，不宣称官方稳定/文档化API；没有因此取得批量服务授权或接口SLA |
| DAMAS tenderStatistics?code=488_2026、484_2026 | Demand[MW]、Satisfied demand[%]、Average accepted price[LEI]；Pay as bid；FCR与FRR；事件显示EET/EEST，可对UTC字段 | LEI缺价格分母；满足率可超过100%；法人中标记录不等于单资源资格 |
| DAMAS activatedBalancingEnergyOverview | 产品上下调字段，数量表头[MWh]，本地EET/EEST交付时段 | 系统报告激活不是本站交付；无最终账单证明 |
| DAMAS marginalPricesOverview | aFRR/mFRRscheduled/direct/RR方向表，价格[LEI] | 未将分母自填为MWh；与偏差价分开 |
| DAMAS dailyConsumptionOverview | Gross forecasted consumption[MW]、Gross realized consumption[MW]，Last update，EET/EEST | lastUpdate不证明实际值在预测发布时已经知道；无历史vintage |
| DAMAS scheduledExchanges | 五个边界的双向商业计划；表头[MW]；metadata.timeZone=CET，其他上述主要报表为EET | 不是物理潮流或可用输电容量；汇总与分项不相加 |
| DAMAS finalImbalancePrices | 页面出现标题，组件加载日志提示指定依赖版本不存在，未出现数字表；一次同名公开候选route返回404；metadata成功但旧更新时间 | 不证明必须登录；不证明平台不存在数据；元数据不当价格样本 |
| https://www.transelectrica.ro/web/tel/rezultate-decontare-piata-de-echilibrare | 首轮送审后从规则E08原件明确链接发现；两次取数分别超时/HTTP520，web读取亦超时 | 没有响应数字原件，不判历史无数据；记录发现依据与失败，不归因登录权限 |
| https://transparency.entsoe.eu/ | 公开欢迎页显示条件确认入口，本轮未确认、未登录、未导出、未提供API token | 仅登记取得正式出口的条件；未判定全部公共数据不可得 |
| BNR XML目录 | 原候选链接落到首页HTML；新目录HTTP可读但无数值XML样本，浏览器请求未完成 | HTTP200不等于取到汇率；不关闭D14 |

POST使用临时匿名会话的公开CSRF字段，回执不记token、cookie或凭据。公开表单页面原文可能带匿名CSRF字段；这不是账户授权，不能据此访问账户区。浏览器只用于公开页面，数字样本以保存的官方响应供审核。
