# 罗马尼亚100MW/200MWh完整测算

**正式期2025-01-01至2026-08-31；608/608日窗口完成；最终独立审核PASS。**

- [结果展示：月/年、滚动12月、EFC、六项现金及9张图](report_v1/结果展示.md)
- [完整审核与主线程验收记录](../../project/romania_full_run_20261002/review_and_acceptance.md)
- [全期物理/现金独立复算](full_validation.json)
- [报告聚合与文件哈希复核](presentation_validation_v1.json)
- [原始求解输出说明](run_v1/report.md)及[运行manifest](run_v1/manifest.json)

全部EUR，p=1，100MW/200MWh名义能量、SOC10—190MWh、效率0.92。DA+aFRR+FCR容量机会价值；容量及激活价格为已确认研究代理。结果是完美信息条件毛现金，不是实际可执行净利润或完整FCR履约收益。2026年只含1—8月，不年化；9月1日观察日不计正式现金。

命令（从仓库根目录，以求解环境运行；新计算必须换全新输出目录）：

```powershell
python project/run_ro_milp.py run --start 2025-01-01 --end 2026-09-01 --power 100 --hours 2 --market DA+aFRR+FCR --p-up 1 --p-down 1 --p-fcr 1 --time-limit 30 --gap 0.0001 --output outputs/new_full_run
```

报告生成另需pandas和matplotlib，已用本机Python3.12.4/pandas2.3.3/matplotlib3.11.1完成，不改变求解环境。生成及验证脚本在`project/romania_full_run_20261002/`，求解源码精确快照在其`solver_snapshot/`。
