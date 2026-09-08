# V1.2 数据工作区

V1.2 从本目录开始维护新的数据获取与审计链路，目标是补充真实、公开、脱敏的中文邮件和现代攻击样本，并重设计行为意图标签。

目录约定：

- `manifests/`：来源目录、许可证核验、下载时间、SHA-256、脱敏和划分报告；
- `processed/`：V1.2 清洗、去重、标注和划分后的本地文件；
- `raw_refs/`：原始文件的本地引用记录，不复制共享原始数据。

V1.2 数据不得直接覆盖 `data/processed/` 的默认 V1/V1.1 文件。训练前必须完成来源/活动/时间隔离、内容去重和人工标注质量审计。URL 仅作离线静态数据，邮件中的 URL 不得访问；附件只保留元数据，不下载、解压或执行。

## 当前获取批次

第一批允许下载的公开资源由 `scripts/download_v1_2_sources.py` 明确列出，当前包括 2024 年
发布的 Figshare Seven Phishing Email Datasets、2025 年发布的中英文 LLMGen 辅助集，以及
2023 年 EPVME 数据集的 README/LICENSE 审计文件。2026 年 9 月 8 日已完成 11 个文件的本地
审计，明细见 `manifests/source_audit.csv`：Figshare 七个 CSV 共 203,897 条记录（其中 TREC-05
和 TREC-06 各有缺失标签行，需清洗），LLMGen 中文 3,030 条、英文/混合 3,746 条。Figshare
是 2024 年重新发布的历史语料，不能把发布日期当作邮件发生时间；必须从 `date` 字段测量实际
时间覆盖。LLMGen 明确标记为 LLM 生成，只能用于辅助训练或鲁棒性测试，不能作为独立最终测试
集。EPVME 当前只保留 README/LICENSE，作为构造攻击语料审计依据，不在 Phase 1 下载 49,136
封 EML 压缩包。下载后必须重新检查字段、隐私、重复和数据来源；`license_status=review_required`
的资源不得直接进入训练。

```powershell
uv run python scripts\download_v1_2_sources.py --list
uv run python scripts\download_v1_2_sources.py
uv run python scripts\audit_v1_2_sources.py
uv run python scripts\audit_v1_2_data_layout.py
```
