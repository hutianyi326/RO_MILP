# 抓取入口补充与定期获取评估

全部是官方HTTPS入口（通常443），未发现需另申请专属端口才可取本轮数据。下表是已实际测试的取数方式；“可以定期获取”是基于本次测试的I判断，不是服务级别或历史完整性保证。来源单位和日期风险见字典。

| 数据 | 官方地址/方式 | 参数与已测试结果 | 还缺什么 |
|---|---|---|---|
| 正式偏差价格/系统量 | https://www.transelectrica.ro/web/tel/rezultate-decontare-piata-de-echilibrare → 官网附件GET | 191个版本，4种×20月；逐文件URL/UUID和哈希见版本目录。一个http://documents畸形链接按同UUID官网主机推导取得，原链接/推导I均留档 | 原件缺行、时钟/模式/终版和历史发布；重复抓目录后按内容哈希新增版本，不覆盖旧版 |
| IDA三轮 | https://www.opcom.ro/rapoarte-ida-rezultate-licitatii/en 匿名GET→POST | ziua_eng=MM/DD/YYYY，action=trading_for，limba=en，buton=Refresh，_token由公开表单提取；公开匿名cookie会话，三轮表头和原生数字/破折号核验 | HTTP成功不能算数字齐全；需交易所完整出口或官方空表解释、发布及取消/回退 |
| 连续日内 | https://www.opcom.ro/rapoarte-pi-rezultate-pi/en 同上POST | 再加tip=15或60；608日×2产品查询，MWh与EUR/MWh、出现次序保留 | 无成交时间/ID与盘口；选日回显非全部成交证明，不构造身份或虚拟盘口 |
| 日前原生RON | https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv/DD/MM/YYYY/ro?resolution=60 或15 | 与en路由对照，60min/QH边界按原生日期；5天339合同比较通过显示界 | 未另抓全期RON原件，全期换算仅候选解释，其他市场FX未关闭 |
| BNR | https://curs.bnr.ro/files/xml/years/nbrfxrates2024.xml 及2025/2026 | GET官方年XML，Cube日期/EUR；2024补Jan2025边界 | BNR参考价不等于全部市场结算汇率；官方原始序列不前填 |
| 费用/采购规则 | https://www.transelectrica.ro/ro/web/tel/tarife；https://www.transelectrica.ro/ro/web/tel/piata-serviciilor-tehnologice-de-sistem；https://www.opcom.ro/anunturi-stiri-fpa/ro/10 | 官网PDF/RAR/Word；按魔数识别，不按后缀猜格式；文件名含空格URL编码后GET成功，最初失败回执保留 | 程序单位冲突、2025完整费率/项目适用链仍缺 |
| ANRE核对 | https://anre.ro/despre/rapoarte/ → 官方月报PDF | 2026-06p14提供18个月控制；机构重加工OPCOM报送 | 同UTC独立原生数据、目录未见Jul/Aug26不能认定资料永不提供 |
| 跨境物理流/容量候选 | https://transparency.entsoe.eu/transmission/physicalFlows；帮助中心How to get security token?/Request Endpoint；官方REST地址https://web-api.tp.entsoe.eu/api | 官方帮助中心原HTML已取得；旧token PDF形状地址实际返回HTML应用壳，另列源异常。只读网页观察，无RO数值/账户/REST调用测试 | REST权限是明确后续候选；取得授权后先按EIC/产品/方向/UTC做样本验证，不把模板参数写成可用接口 |

容量/系统激活公共API的已实测具体命令与参数沿用旧project/romania_data_samples_20260930/acquisition_endpoints.md，本轮没有另造未测试API。容量公开统计价的分母/算术平均证据有补充，仍不是本站实付。

研究采集上限每批3个并行请求、每次25秒超时、最多3次，回执永久记录失败和重试，原件新增保存。常规增量获取应先检查目录/最新日期，只下载新增或改变的版本，并核日期、单位、数字覆盖、空值、DST及哈希；来源变动或持续缺数必须报错，不能继续输出“完整”。本轮没有创建定时任务、申请账号、采购接口或发送外部消息。
