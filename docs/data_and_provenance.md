# 数据压缩和来源审计

本仓库采用保留原目录的独立打包方式。罗马尼亚研究文件、原始官方证据和已有采集/解析脚本来自同一工作区；新增打包说明不是对既有数据的重新审批。

## 文件清单

- `packaging/source_manifest.json`：每个来源文件的原相对路径、仓库路径、编码方式、源/仓库大小及各自SHA256。
- `packaging/compressed_files.json`：超过打包阈值而改为gzip的大表。gzip解压结果必须匹配原始SHA256。
- `packaging/excluded_files.json`：环境缓存及重复审核提交快照。早期审核文本、清单和最终结论保留；排除快照不表示将这些旧审核意见删除。
- `packaging/verification.json`：打包复核结果，包括文件大小、复制校验、gzip恢复校验及敏感凭证模式筛查范围。

未压缩文件逐字节复制；压缩文件只改变存储编码，不更改CSV/JSON内容。旧研究中的hash和绝对路径仍指向原时点证据。新清单描述本次仓库映射，不替换旧清单。

## 恢复大表

在 `compressed_files.json` 找到原路径，例如某个 `file.csv` 在仓库中保存为 `file.csv.gz`。使用支持gzip的解压工具，将其解压到相同文件夹并保留原文件名；再与 `source_manifest.json` 的 `source_sha256` 对照。

已有研究脚本需要原 `.csv`/`.json` 时，应先恢复；不要把gzip字节直接交给按普通文本读取的脚本。恢复后的大文件已在本仓库 `.gitignore` 中逐项忽略，因此后续 `git add -A` 不会把它们重复提交。

官方ZIP/RAR/PDF等原件保持原格式；其文件后缀可能体现当时获取方式，读取时应遵循原研究的魔数/格式记录。不要擅改源文件覆盖原件。

## 可复现性的限度

本次保留原件、来源、研究脚本及结果，但没有重新执行全部历史下载、解析或研究流水线。既有脚本依赖、Windows文档转换和历史环境可能需另行配置；源站历史版本也可能发生变化。脚本存在不代表一个命令即可无条件复现全部研究。

MILP目前只有已审数学说明和性能设计，尚无正式优化输入规范、求解实现或收益回测。原始数据和描述性统计的可追溯性不能代替模型输入适用性审核。

## Git大文件处理

普通GitHub仓库拒绝超过100MiB的单个文件；本次将超过40MiB的文本大表无损gzip压缩，上传前检查实际Git文件大小。依据：[GitHub官方大文件说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)，访问日2026-10-02。本仓库不依赖Git LFS即可读取这批压缩数据。
