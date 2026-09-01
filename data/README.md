# 训练数据说明

## 当前阶段

成员1步骤2先收集公开原始邮件归档，并记录来源、许可证说明、下载时间、文件大小和 SHA-256。原始文件放在 `data/raw/`，默认不提交 Git；处理脚本和来源清单可以提交。

## 当前收集来源

### Nazario Phishing Corpus

- 来源目录：<https://monkey.org/~jose/phishing/>
- 用途：明确标注的钓鱼邮件正样本。
- 计划标签：`phishing`。
- 当前下载项：早期 mbox 与 2021--2025 年度 mbox。
- 许可证：CC BY 4.0，以来源站点的 `LICENSE.txt` 为准；使用时保留来源和许可证记录。

### SpamAssassin Public Corpus

- 来源目录：<https://spamassassin.apache.org/old/publiccorpus/>
- 用途：明确标注的 `ham` 正常邮件样本。
- 计划标签：`legitimate`。
- 当前下载项：easy ham、hard ham 及其 2003 年补充归档。
- 注意：普通 `spam` 不直接标记为 `legitimate`，后续保留为 `spam_other` 硬负样本。

## 安全和隐私限制

- 只下载固定公开数据源，不访问邮件正文中的 URL。
- 不执行、解压或渲染邮件附件；后续解析只读取附件元数据。
- 原始数据不提交 Git，不保存邮箱密码、令牌或私人邮件。
- 下载脚本会生成 `data/manifests/sources.csv`，其中记录本地相对路径、大小、SHA-256 和状态。

## 重建命令

项目使用 Python 3.11 和 uv：

```powershell
uv sync
uv run python scripts\download_datasets.py --list
uv run python scripts\download_datasets.py
uv run python scripts\inventory_datasets.py
uv run python scripts\prepare_raw_dataset.py
```

脚本只下载固定列表中的文件；已存在且未被删除的文件不会重复下载。

## 步骤3：离线统一读取

`scripts\prepare_raw_dataset.py` 使用本地 `mailbox`、`tarfile` 和 Python `email`
标准库读取归档，并将每封邮件写为 `data/processed/raw_emails.jsonl`。该文件保持
Git 忽略；可提交的 `data/manifests/raw_parse_summary.json` 记录解析总数、空记录数、
来源与标签计数，以及解析告警计数。

读取适配器位于 `scripts\email_loader.py`，仅服务于成员1的离线语料准备，不属于
应用运行时模块。它不会替代成员2在 `src\parsers\` 中维护的生产邮件解析器；
后续集成时仍以 `ParsedEmail` 共享契约为准。

本次运行的统计为：11,333 条中间记录，包含 4,382 条 `phishing` 和 6,951 条
`legitimate`。读取过程只在内存中读取 tar 成员，不会将邮件附件写出、解压或执行，
也不会访问邮件中的 URL。
