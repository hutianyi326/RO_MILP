# 独立审核任务

用户2026-09-30指定：主线程执行罗马尼亚官方规则步骤1，随后review Agent使用astra/high。本次以通用角色显式gpt-6-astra/high担任只读research_reviewer，不使用固定medium的内置角色；禁止任何下级Agent，max_depth=1。

审查countries/RO/research.md、countries/RO/rules_20260930中的sources.csv、rule_register.csv、historical_rule_timeline.md、settlement_examples.md、open_questions.md、acceptance.md，结合project/romania_official_rules_20260930/authorization.md、baseline/四份冻结文件、verification.json和raw官方原件。提取/OCR在extracted/，原图在rendered/，PDF文件页与公报页需区分。

审核对象是工作明细1.1—1.8的有限范围规则交付，不是全国完整研究、数据、MILP或全20个月规则已闭合。逐项判断：关键事实是否有第一方证据与位置；历史版本/起效/实际运行是否混淆；许可1MW阈值、FCR对称带宽/测试/罚则、aFRR7.5→5分钟、容量支付/单位、现货GCT/时区/IDA事件、PE承诺与PRE偏差、最终单/双价、网络减免与费用是否正确；F/I/A/U是否分离，未决项的限定是否足够、哪些未决项会阻断此次有限验收。

已知特殊项：E14/E54同字节但混合年代，容量旧价条款由E15修订覆盖；FCR energy为BSP237—238并非222—227，不新增未经证明独立能量现金收入；E33二进制DOC提取禁用；E46/E52/E65只网页核对未下载原件；前2025-06 FCR采购、容量现金单位和历史GCT等U仍开放，建模false。

只读，不修改文件、状态或启动其他阶段，不创建/委派任何子Agent。不发送消息到其他用户线程。可自行核对官方公开资料。向主线程返回：结论PASS/PASS_WITH_RESTRICTIONS/FAIL，P0/P1/P2清单（文件位置、主张、原件/URL和条款、建议修复）、逐1.1—1.8覆盖评估及仍需限制；只有缺口明确记录但不影响本轮研究记录正确性时才可限定通过。不要将原件哈希和算术PASS当成规则真实性/完整性审核。
