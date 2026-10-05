# 罗马尼亚全EUR价格数据 v1

日期：2026-10-02。主线程根据用户要求授权新增本目录及`project/romania_eur_release_20261002/`，并更新根README导航；既有混合币种数据和官方原件不覆盖。本版为用户要求的EUR模型输入导出，不修改市场范围或MILP数学公式，不实现求解器。

## 数据入口

| 文件 | 内容 |
|---|---|
| [prices_eur_qh_20250101_20260831.csv](prices_eur_qh_20250101_20260831.csv) | 正式期主表，58,364行，7个价格字段全部为EUR（含全空FCR激活字段） |
| [prices_eur_observation_20260901.csv](prices_eur_observation_20260901.csv) | 独立观察日96行，不计正式现金 |
| [da_native_eur.csv](da_native_eur.csv) | 原生DA合同与EUR/MWh价格 |
| [capacity_native_hourly_eur.csv](capacity_native_hourly_eur.csv) | 原生容量小时统计及研究订单映射；接受均价、报价均价、tenderPrice均换算为EUR代理，后两项只供诊断 |
| [activation_native_qh_eur.csv](activation_native_qh_eur.csv) | 原生激活价，EUR/MWh代理、保持原始符号 |
| [fx_by_bucharest_delivery_day.csv](fx_by_bucharest_delivery_day.csv) | 609个Bucharest交付日与BNR参考汇率日期的映射，含观察日 |
| [currency_conversion_summary.csv](currency_conversion_summary.csv) | 各EUR价格的非空/空值/零价/负价数量和极值 |
| [coverage_monthly_eur.csv](coverage_monthly_eur.csv) | 按转换后的逐QH EUR价格重算月度极值，保留覆盖统计 |
| [price_missing_in_scope_eur.csv](price_missing_in_scope_eur.csv) | 原始缺口保留，仅系列名改为对应EUR字段 |
| [source_registry.csv](source_registry.csv) | 继承已审682个来源的URL、原件哈希和获取日期 |
| [validation.json](validation.json)、[build_summary.json](build_summary.json)、[manifest.json](manifest.json) | 换算检查、构建摘要及本版文件SHA256 |

全部CSV为UTF-8 BOM。货币价格字段只保留EUR；`fx_ron_per_eur`是“每1EUR对应RON数”的换算比率，不是额外RON价格或收入。原币数值仍可通过来源键回溯 [原币数据v1](../prices_v1_20261002/README.md)。本版不允许把两版价格重复计入现金。

## 换汇口径

1. 从`delivery_start_utc`转换到`Europe/Bucharest`，获得当地交付日D；不用UTC日期、OPCOM源市场日或数据下载日匹配汇率。
2. 沿用已确认口径，取**严格早于D的最近BNR参考日期**，包括周末、节假日及年界；不是D当日稍后发布的汇率。匹配按当地日，相同D的全部QH使用同一值。
3. BNR XML的`Rate currency="EUR"`表示1EUR对应RON金额。`EUR价格 = RON价格 / fx_ron_per_eur`。DA原本就是EUR，不再换汇。
4. 容量转换后单位为EUR/(MW·h)代理，价格不乘/除0.25；计算QH容量收入时才乘0.25小时。激活价为EUR/MWh代理；已有MWh电量不再乘时长。
5. 原始负价/零价、缺失和状态全部保留；下调原始价格不预先取负。模型现金为`up_price × up_MWh − down_price × down_MWh`。
6. 不使用月均/年均汇率倒算整期收益，不在数据准备时保留两位小数。缺必要汇率即拒绝本版构建，不填1或借用未来汇率。

这是研究换汇约定，不是BNR规定的交易结算汇率选择。BNR说明参考汇率不强制用于交易或账务：[官方XML说明](https://curs.bnr.ro/)，本轮访问2026-10-02。每日日期来自XML的Cube日期，不冒充精确发布时间。

## 币种和单位核查

| 市场 | 原币证据 | 本版价格单位 | 核实程度 |
|---|---|---|---|
| DA | OPCOM原生CSV表头`Euro/MWh`，逐份来源保留 | EUR/MWh | 源单位明确；直接沿用，不换汇 |
| FCR容量 | DAMAS页面`LEI`；TSO FCR程序与STS月报使用lei/hMW | EUR/(MW·h) | 币种RON；具体API均价分母映射沿用已批准研究假设 |
| aFRR上/下容量 | DAMAS页面`LEI`；STS月报容量使用lei/hMW | EUR/(MW·h) | 币种RON；程序个别文字单位与月报存在旧有冲突，不宣称全部字段官方确认 |
| aFRR上/下激活 | DAMAS页面价格`LEI`；ANRE Art.63区分本地PE和欧洲平台报价币种 | EUR/MWh | 本次选用DAMAS本地LEI系列按RON换算；API分母及最终结算性质仍为已登记代理限制 |
| FCR独立激活 | DAMAS原字段全null，没有数值可确认或换算 | 全空EUR/MWh代理列 | 保持`SOURCE_NULL_NOT_MODELED`，不是0价格 |

**F（来源事实）**：原始表头、页面币种标签、BNR参考汇率及空值。**I（处理解释）**：UTC转当地日、逐日匹配、源数值除汇率。**A（建模假设）**：前一参考日选择、容量及激活API分母映射、采用系统均价作为本站收入代理。换汇不把A升级为官方事实。

证据位置：

- OPCOM《Mcp and Traded Volume》，表头及Romania行；源市场日与逐件访问时间见source_registry。已留存的2024-12-31边界CSV首部明确Euro/MWh，正式输入来自同一路由；原币v1已独立核对全期原件。
- Transelectrica DAMAS页面观察，2026-09-30，[币种标签定位](../../../../countries/RO/data_samples_20260930/ui_observations.md)：tenderStatistics的Average accepted price[LEI]及marginalPricesOverview的价格[LEI]。JSON本身没有完整单位说明，不能仅靠字段名确认分母。
- Transelectrica《2025年8月STS监测报告》，报告期2025-08、首次发布日期未知，PDF p4/5/8；访问2026-10-01，见[证据GC02—GC05](../../../../countries/RO/gap_closure_20261001/evidence_register.csv)及[官方PDF](https://www.transelectrica.ro/documents/10179/18723178/2025-08-STS-Raport.pdf/1c2cc5bf-e0f5-48ff-bc12-2019c164623c)。支持容量币种和时间单位，不证明系统均价等于单站发票。
- ANRE 127/2021附件合并网页，基础日期2021-12-08，Art.50、63表6，2026-10-02重新访问：[官方法规](https://legislatie.just.ro/Public/DetaliiDocument/280280)。本地PE报价为lei/MWh、欧洲平台为EUR/MWh，故不能将“罗马尼亚所有aFRR数据”统一推定为RON；本包只转换既有DAMAS LEI系列。报价规则也不单独证明报表每个字段的最终结算语义。
- BNR年度XML，2024、2025、2026，`Cube@date / Rate@currency=EUR`，原件取得日期/哈希见source_registry；[2025原件](https://curs.bnr.ro/files/xml/years/nbrfxrates2025.xml)。本次从这三份原始XML重新建立609日映射，而非仅删除旧表RON列。

## 验证与限制

本次检查来源版本哈希、BNR XML倍率及日期、58,364+96条UTC连续网格、DST的92/100段、当地日期匹配、正负零和空值保留、原币反算、逐值Decimal独立计算、与已审v1 EUR代理列一致、原生表/QH表一致、原数据未被改写。结果见validation.json；本轮未另行调用独立review agent，不将上版review自动称为本版review。

市场范围仍为DA、FCR容量及aFRR容量/激活，不扩展IDA/IDC/mFRR/RR。FCR容量在6月起范围内缺580QH；aFRR容量每方向缺4QH、激活每方向缺1QH。alpha和小时数据门禁逐列保持原值：正式aFRR可用13,375小时、禁用1,216小时。价格统一EUR不代表缺失被恢复或模型已求解；旧数据审核限制继续适用。

复现脚本：[build_eur.py](../../../../project/romania_eur_release_20261002/build_eur.py)。全部源证据留在既有目录，新市场修订应创建新版本，不覆盖本版原始来源。
