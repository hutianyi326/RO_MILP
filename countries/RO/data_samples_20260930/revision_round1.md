# 首轮问题修订与第二轮新增证据

2026-09-30，主线程。首轮结论FAIL，P1-01；首轮原件不覆盖，原审核交付保存在project/romania_data_samples_20260930/round1_snapshot/。

| 问题 | 修订 | 自查证据/结果 | 是否关闭 |
|---|---|---|---|
| P1-01 IDA状态及事实错误 | 逐列保留price/volume/buy/sell及缺值；price_valid/volume_valid/buy_valid/sell_valid；46个价量对改VALID_PRICE_VOLUME，买量“-”保留；每轮coverage动态EMPTY/PARTIAL/COMPLETE，清单按来源统计真实数字；正文/D03/DS02/UI/字典改局部46段 | ida_checks.json；IDA_2025-10-01 manifest numeric=46、by_auction={1:0,2:46,3:0}；coverage IDA2 numeric/valid_pair=46/96；区间23能量0.800MWh、84.74400EUR；30项新增检查通过 | 主线程已修，等待独立复核 |

199回执/177原件是首轮197/177加两次后续正式结算栏目实测：TSO_SETTLEMENT_RESULTS（35秒超时）、TSO_SETTLEMENT_RESULTS_R1（HTTP520），均没有数字原件；不得列为成功取数，DS01未关闭。该URL从既有E08正式平衡市场原件的“Rezultate Decontare Piata de Echilibrare”链接发现，不是再次猜接口。UI记录、来源目录及正文同步登记。web工具读取也超时，但不计为有本地回执的199次之一。

报告检查总数由7857变7887；首轮7857项检查存在IDA标签盲点，明确保留FAIL，不将新检查倒填首轮。其他原件、DA/月报/容量/系统/曲线和基线没有修改。DS02只调整已取得样本程度，仍保留其他轮日、50缺段、缺字段原因、历史发布、全期/可成交限制。

other_country_state_at_review_start.json仅保存首轮当前的非RO文本；后续状态修订对照此起点，不宣称证明本轮任务开始以前未改。运行依赖版本在runtime_versions.json；新增检查、数值、状态及修订文件一起列入review_round2_manifest.json。
