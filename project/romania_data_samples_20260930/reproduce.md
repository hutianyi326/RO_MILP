# 样本交付复现与验证入口

研究辅助材料，不是生产模型/输入规范。操作在项目根目录，依赖本任务已配置的Python运行时及runtime_versions.json所列lxml/pypdf/tzdata等。analyze_samples.py从不可覆盖的原件及回执生成本目录对应的研究表、verification.json/series_checks.json/ida_checks.json；build_delivery.py随后生成来源目录、转录年度/费率表和基线核验。它们可更新派生表但不重取或覆盖原件；只读审核需在临时目录独立复算，不运行覆盖派生表的操作。

先执行analyze_samples.py，再执行build_delivery.py。预期7887检查PASS，199回执、177原件、DA96日6839行、容量783行、系统64796长字段行、IDCT143行、FX66行；IDA2004模板行、46有效数字价格和价量对，source_id为IDA_2025-10-01/IDA2，buy缺失。见verification/ida_checks与原件定位。

首轮34文件字节快照保存于round1_snapshot/<原相对路径>，按review_round1_manifest.json逐一验哈希；它保留首轮错误状态，不当当前输入。第二轮清单是实际修订后快照。文件后缀误判由真实内容检测解决：部分CSV原件为original.html，原字节不改名覆盖；BNR首页HTML不当XML。失败回执是来源线索/条件证据，不是时间序列或无成交证明。

自动检查验证处理正确性；15条SQ、12DS和12U依然存在。只读审核、有限验收及国家门禁记录分别归档，最终验收不会因检查PASS消除输入缺口。
