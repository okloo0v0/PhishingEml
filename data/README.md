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
uv run python scripts\prepare_clean_dataset.py
uv run python scripts\deduplicate_dataset.py
uv run python scripts\split_dataset.py
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

## 步骤4：统一文本清洗

`scripts\prepare_clean_dataset.py` 调用 `src\detection\text_features.py` 中的
`clean_email_text()`，为训练和推理生成相同的 `text-v1` 输入：主题、换行、正文，
最长 20,000 个字符。清洗会统一 Unicode/空白，移除控制字符，并将邮箱、URL 和长
数字替换为 `<EMAIL>`、`<URL>`、`<NUMBER>` 占位符；不会访问 URL，也不会读取附件内容。

清洗结果写入被 Git 忽略的 `data/processed/cleaned_emails.jsonl`，非敏感统计写入
`data/manifests/clean_summary.json`。2026-09-01 本次运行处理 11,333 条记录，替换
邮箱 12,734 次、URL 28,105 次、长数字 4,018 次；44 条记录因超过长度上限被截断。

## 步骤5：去重与泄漏审计

`scripts\deduplicate_dataset.py` 先按原始 `source_hash` 删除字节完全相同的记录，再按
`text-v1` 的完整 `model_text` SHA-256 指纹去重。每个保留记录都包含相同值的
`content_fingerprint` 和 `dedup_group`，步骤6必须以 `dedup_group` 为不可跨集合的边界。

本次去重从 11,333 条保留 7,257 条：删除 181 条原始哈希重复和 3,895 条规范文本重复。
`data/manifests/dedup_report.json` 还记录了 3,847 对 SimHash 近重复候选（1,397 条记录）；
它们只用于审计，不自动删除，以免误删有效的钓鱼变体。当前中间数据没有可靠的
发件人和线程元数据，因此线程/发件人聚类留待与成员2生产解析器对齐后补做。

## 补充语料轮次

补充语料统一登记在 `data/manifests/sources.csv`，原始 CSV 保存在被 Git 忽略的
`data/raw/supplemental_zenodo/`。下载和重建命令为：

```powershell
uv run python scripts\download_supplemental.py --list
uv run python scripts\download_supplemental.py
uv run python scripts\prepare_supplemental_dataset.py
uv run python scripts\deduplicate_dataset.py `
  --input data\processed\cleaned_emails.jsonl `
  --input data\processed\supplemental_cleaned_emails.jsonl `
  --output data\processed\deduplicated_emails_combined.jsonl `
  --report data\manifests\dedup_combined_report.json
```

本轮采用 Zenodo 8339691 的公开整理 CSV（CC BY 4.0）：`Nigerian_5.csv` 的
`0/1` 映射为 `legitimate/phishing`，`SpamAssasin.csv` 的 `0/1` 映射为
`legitimate/spam_other`，并另外登记了 `Nigerian_Fraud.csv` 和 `Nazario.csv` 的
明确 phishing 标签。补充文件共解析 17,037 条，联合旧数据后输入 28,370 条，
精确去重后保留 17,844 条：二分类样本 16,149 条（`phishing` 7,913 条、
`legitimate` 8,236 条），另保留 1,695 条 `spam_other` 硬负样本。完整统计见
`data/manifests/supplemental_summary.json` 和 `data/manifests/dedup_combined_report.json`。

补充数据可能包含原始公开语料中的个人信息或历史内容，因此只保留本地原始文件和
哈希登记，不将 CSV、JSONL 或邮件正文提交 Git。`spam_other` 不进入第一版二分类
训练，只用于误报/硬负样本评估。

## 步骤6：标签清洗与数据划分

`scripts\split_dataset.py` 校验标签集合 `phishing`、`legitimate`、`spam_other`，
剔除空 `model_text`，将 `spam_other` 单独写入硬负样本文件。二分类记录先按来源-标签
抽取 10% 的 `cross_source_test.jsonl`，剩余记录再按标签以 70/15/15 划分到
`emails.csv` 的 `train`、`valid`、`test`。划分过程中以 `dedup_group` 为组边界，
并在脚本中检查组不交叉。

本轮输入 17,844 条，剔除 1 条空文本；二分类有效记录 16,148 条，跨来源测试集
1,611 条，主数据集 14,537 条：train 10,175、valid 2,181、test 2,181。主数据集
标签计数为 `legitimate` 7,414、`phishing` 7,123；另有 `spam_other` 1,695 条硬负
样本。统计见 `data/manifests/split_summary.json`，标签剔除见
`data/manifests/label_drop_report.json`。

## 步骤7：训练基线模型

运行 `uv run python scripts\train_model.py`，脚本只使用 `emails.csv` 的 `train` 划分
拟合固定的 TF-IDF + Logistic Regression Pipeline，并对 valid/test 输出预测概率。模型
文件 `models\phishing_model.joblib` 被 Git 忽略，训练配置和版本记录在
`data/manifests/model_training_summary.json`，预测明细在被忽略的
`data/processed/model_predictions.csv`。

本次训练使用 10,175 条 train 样本，valid/test 各 2,181 条。分类器类别顺序已校验为
`[legitimate, phishing]`，`predict_proba[:, 1]` 明确定义为 phishing 概率，阈值为 0.50。
步骤8将基于这些固定预测生成 Precision、Recall、F1、混淆矩阵和错误样本分析。
