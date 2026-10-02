# 第三步第一轮问题与定点修复

2026-10-01，主线程修复，审核只读。第一轮201项冻结清单、轻量快照和原意见不覆盖；四张受影响CSV修复前原版本保存于round1_before_fix/，manifest登记原哈希。原始官方文件不改。未改固定研究基线、旧研究记录或其他国家状态。

| ID | 第一轮问题 | 主线程修复 | 验证/复审状态 |
|---|---|---|---|
| P2-01 | native/joint/negative三表sheet失前导零；joint/negative的小时标签也数值化 | 从20月原始XLS重新提取真实页名/小时标签；研究辅助读取固定sheet、source_hour_label、source_local_hour_end_label为字符串，保留03 bis | 第二轮独立确认关闭；三表分别14,567/14,496/111行按真实member/sheet/row直接回查匹配；非标签文本不变，数值最大浮点差约4.55×10^-13，无实质统计变化 |
| P2-02 | 月×小时画像没有分组样本数 | 增加481组native_row_count及12字段×481组=5,772个*_valid_count；在字典/报告说明MW均值、计数单位和跳过缺值/不补0 | 第二轮独立确认关闭；全部数量和均值复算匹配，旧均值一致；2025-10的03/03 bis=31/1，两个春季3月03=30 |

定点校验[p2_repair_verification.json](../../countries/RO/full_period_20261001/p2_repair_verification.json)的23项检查全部通过；原生14,567小时、607日期、111负技术值行、A联合14,496小时及DST/错日期排除保留。为保证可复现，原件解析、派生统计和最后补充依赖顺序重新执行，完整补充994项检查重跑。只有定位字符串和新增计数改变输出含义，价格/负荷/容量/激活/金额统计与模型禁用边界保持。

第一轮PASS_WITH_RESTRICTIONS带两项未关闭P2；依第二轮实际独立复审关闭，两轮原意见各自保存。第二轮最终P0/P1/P2=0/0/0、记录范围PASS_WITH_RESTRICTIONS，见[原复审结论](../../countries/RO/full_period_20261001/review_round2.md)。U01—U12、DS01—DS12及源异常不是软件修复项，仍保留。整体第三步退出false、全部模型/策略/as-of门禁false。
