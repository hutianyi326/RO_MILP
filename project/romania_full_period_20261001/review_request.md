# 第三步正式独立审核请求

2026-10-01。用户“执行第三步，并由review agent审核”；根线程主笔，复用/root/romania_rules_review实际gpt-6-astra/high。禁止下级委派、禁止直接修改研究、状态或开始下一阶段。

审核范围：固定WBD3.1—3.9、D01—D19、四种用途及基线。审核对象是已实际执行的数据获取、字段覆盖、描述分析、源限制和未完成状态的准确性，**不是预先要求整阶段PASS**。请独立判断有无问题；即使记录可接受，仍须单独明确完整第三步退出false以及受阻子项，不能通过移除缺失市场来闭合。

主文件 countries/RO/full_period_20261001/analysis_report.md、data_dictionary.md、source_directory.md、stage_completion_and_gaps.md；全部CSV/JSON/PNG/SVG及源清单；project/romania_full_period_20261001研究辅助、授权/前置复核/视觉与复现记录、project/country_status.yaml；引用的四份固定基线及旧规则/样本。正式快照manifest锁所有本批次研究文件、辅助和状态hash；官方原件与旧源按manifest只读核对。大表原路径hash冻结，轻量文档另存round1_snapshot。

重点检查：两种源时钟与相邻源日、DA原生38,711源期/38,708目标合同与58,364描述映射、20月同机构控制不得称独立核验；逐产品字段数值/null/零及100个容量产品月；FCR早期空/23/25小时边界及5产品日缺时；LEI分母不当现金；SCADA原生03 bis/错日期/负值/14,567小时及A联合14,496、净毛/prosumer未核、±1h敏感性；供方只限57,202吻合小时、labels非法人和12,125未相符小时；Anexa2金额不是偏差价、Data finalizarii不是publication；BNR两年命名空间和413公布日不前填、账务规则未闭；所有字段来源、单位、实际范围、图样本；632新+96复用/642尝试/真实UTC获取日不可改成目录日期；F/I/A/U分离、U/DS不能因统计PASS关闭；国家RO仍researching且所有模型/asof门禁false。

请返回PASS/FAIL或PASS_WITH_RESTRICTIONS（清楚作用对象）、P0/P1/P2计数、逐项文件/行或CSV键证据与修复要求、未被审核缺陷替代的真实研究依赖、核查方法和未检查限制。不要写文件，由主线程保存原结论；需要修正时主线程修复后再请复核。
