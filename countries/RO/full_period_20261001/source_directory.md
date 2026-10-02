# 官方来源、地址和获取说明

访问日期必须按每条原件retrieved_utc保存。本地执行日2026-10-01（Asia/Shanghai），本轮新增原件实际UTC获取日为2026-09-30，不能把批次日期冒充UTC获取日或官方发布日期。以下网页若未声明公布/生效日，统一保留“未标明”；报告期/截面日期是内容适用期，不等于发布时间。字段定义和历史规则引用沿用已审证据，不新增无证据市场规则。

| 来源机构/ID | 官方文件或页面标题、适用期 | 地址和证据位置 | 使用/发布限制 |
|---|---|---|---|
| OPCOM / DA日期ID | Mcp and Traded Volume，2025-01—2026-08原生源日及相邻边界 | [原生CSV示例](https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv/01/02/2025/en?resolution=60)，路由/dd/mm/yyyy/en?resolution=60或15；表头及Romania逐区间行，ROPEX日汇总另列 | 逐文件全URL/哈希在manifest；源时钟Brussels、单位EUR/MWh/MW；首次发布时间未知 |
| OPCOM / MONTH_yyyy-mm | Monthly Market Report，各20个报告月 | [正式目录](https://www.opcom.ro/tranzactii-rezultate/en/22)，每月直链在manifest；PDF p2 DA/Intraday当前月比较表及加权headline | 月报公布日期未标明；仅报告月；不做逐时填补。6页视觉证据含3份月报p2 |
| OPCOM / OPCOM_IDA_CURRENT_PROBE | Rezultate licitatii IDA公开模板 | [官方结果页](https://www.opcom.ro/rapoarte-ida-rezultate-licitatii/en)，IDA1/2/3列及“-” | GET复核是模板，不是选日POST或完整历史请求；不能凭无数字判断没有交易 |
| Transelectrica / tenderStatistics年月 | DAMAS II Public Reports / Tender statistics | [公共平台](https://newmarkets.transelectrica.ro/)，后台/publicReport/tenderStatistics；itemList/tenderCode/timeInterval/serviceCode/tenderStatistics/timeIntervalList及contractedPower | FCR及FRR字段定义复用已审样本证据；LEI分母待核；无修订链 |
| Transelectrica / activatedBalancingEnergyOverview年月 | Activated balancing energy | 同一官方平台/publicReport/activatedBalancingEnergyOverview；itemList的timeInterval和产品方向字段 | QH MWh系统量，非本站实交；价格非本报告确认输入 |
| Transelectrica / dailyConsumptionOverview年月 | Daily consumption overview | 同一官方平台/publicReport/dailyConsumptionOverview；grossRealizedConsumption/grossForecastConsumption/lastUpdate | QH MW实际毛值/取得日存储预测分列，lastUpdate非publication/vintage |
| Transelectrica / scheduledExchanges年月、边界日 | Scheduled exchanges | 同一官方平台/publicReport/scheduledExchanges；itemList/timeInterval、huro等各子字段 | QH MW，源日Brussels；仅commercial用于净计划计算 |
| Transelectrica / TSO_PRODUCTION_CATALOG | Production，页面标最新更新01.09.2026 | [正式生产页](https://www.transelectrica.ro/ro/web/tel/productie)，第17项小时平均出力及archive，第20项装机 | 更新文字非每个历史档案发布时间；各附件内部日期另核 |
| Transelectrica / TSO_GENERATION_ARCHIVE | Consum SEN-SCADA官方历史档案 | [档案直链](https://www.transelectrica.ro/documents/10179/45094/7productie17a1.rar/744eae9f-5f6b-445d-b895-5d494823f3c7)，ZIP成员2025/2026月XLS；F1日期、A2粒度、B—M字段、实际小时行 | URL.rar实际ZIP；20月成员哈希见scada_archive_members.csv；prosumer/净毛/小时UTC定义待核 |
| Transelectrica / TSO_GENERATION_CURRENT | 当前Consum SEN-SCADA表 | [当前直链](https://www.transelectrica.ro/documents/10179/45094/7productie17/fb9e938a-5577-469a-8008-52161ac8b7f5)，实际2026-09工作表 | 不在目标交付期内，未拼入1—8月；原件OLE XLS |
| Transelectrica / TSO_SCADA_UNIT_REFERENCE | SENGrafic字段单位 | [官方字段表](https://www.transelectrica.ro/en/widget/web/tel/sen-grafic/-/SENGrafic_WAR_SENGraficportlet)，Consum/Productie/各技术/Sold [MW]表头 | 页正文定义图中瞬时值，不能代替medii orare；仅作同机构单位交叉证据，非不同机构出力核验 |
| Transelectrica / TSO_INSTALLED_2026_0 | Situatia capacitatii instalate及Stocare/Prosumatori/Definitii | [官方装机XLS](https://www.transelectrica.ro/documents/10179/45094/7productie23.xls/4ed0d546-a1b7-4bde-a25f-656057902e3d)，Sheet1 A3/E—H15；Stocare A5/D—G63；Prosumatori A1；Definitii B4/8/15/22/29 | Sheet1/Stocare01.09.2026，Prosumatori01.08.2026；Pg/Pc原名保留，不视为Pn/Pd；许可与在运不混同 |
| Transelectrica / TSO_Q1_2026 | Raport trimestrial Ianuarie-Martie 2026 | [Q1正式PDF](https://www.transelectrica.ro/documents/10179/22616687/Raport_ASF_T1_2026_RO.pdf/4174a663-c542-4b89-90d1-646b6bb5114a)，p24/印刷p22储能01.04.2026和物理GWh图 | 599MW/1129.7MWh是截面，非QH；实际发布日期本轮未直接核定，不用截面日期代替 |
| Transelectrica / TSO_H1_2026 | Raport semestrial Ianuarie-Iunie 2026 | [H1正式PDF](https://www.transelectrica.ro/documents/10179/23486252/Raport_ASF_S1_2026_RO.pdf/1e22931a-8b1b-4f2f-bf8a-01c70cd49711)，p23—24/印刷p19—20，01.07.2026装机/储能及物理GWh图 | 924.43MW/1762.50MWh；May/June部分经营数据初步；实际发布日期未直接核定，财务日历不替代实际发布事件 |
| Transelectrica / 已审TSO_ANNUAL_2025 | Raport Anual 2025 | 已审raw_manifest列正式URL及哈希；PDF p63表12/13、p64表14/储能段 | 2023/24/25净量、粗装机、12.05储能和01.01prosumer有不同日期和覆盖；来源定位复用，不改原记录 |
| Transelectrica / TSO_FINAL_SETTLEMENT、SETTLEMENT_SAMPLE_1—4 | Rezultate decontare piata de echilibrare；Anexa2 CosturiEfectivePerID_EchSEN | [正式目录](https://www.transelectrica.ro/web/tel/rezultate-decontare-piata-de-echilibrare)，表头Luna de decontare/Tipul decontării/Data finalizării；附件p1字段和全部31页逐QH | Jan2025 VM完成27.02.2025、VMA14.03.2025、更正15.01.2026；Aug2026VM21.09.2026。日期非publication；单位lei金额，不是最终偏差单价 |
| BNR / BNR_XML_CATALOG、BNR_FX_2025/2026 | Dedicated XML exchange-rate server instructions及年度序列 | [官方说明](https://curs.bnr.ro/)，[2025 XML](https://curs.bnr.ro/files/xml/years/nbrfxrates2025.xml)、[2026 XML](https://curs.bnr.ro/files/xml/years/nbrfxrates2026.xml)，Body/Cube date、EUR Rate | 官方HTTPS443/TLS1.2，银行日13h后更新、建议本地缓存；参考值不强制用于交易/账务。Cube日期不是精确发布时间 |

DAMAS后台公共基础地址：`https://newmarkets.transelectrica.ro/usy-durom-publicreportg01/00121002500000000000000000000100/publicReport/`。本轮以`timeInterval.from/to` UTC、`pageInfo.pageSize=3000`、`pageIndex=0`分月请求；逐批返回itemList数和pageInfo.total重新核对，不能假设今后无需翻页。访问为官方公开GET，无注册令牌，无伪造凭证。正式合同/参与接口及最终偏差失败route不能称已验证API。

全部月报、系统报告、DA及版本附件直链不在正文重复数百次，逐条保存于raw_manifest.json，可从源ID追到请求和原件。旧页面下载失败、新地址找到与实际取到序列分别记录，未重写2026-09-30样本失败事实；本轮未发送机构消息、注册API账号或承诺服务稳定性。已验证公共方式可持续作为定期增量获取候选，但没有创建定时任务。
