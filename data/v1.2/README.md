# V1.2 数据工作区

V1.2 从本目录开始维护新的数据获取与审计链路，目标是补充真实、公开、脱敏的中文邮件和现代攻击样本，并重设计行为意图标签。

目录约定：

- `manifests/`：来源目录、许可证核验、下载时间、SHA-256、脱敏和划分报告；
- `processed/`：V1.2 清洗、去重、标注和划分后的本地文件；
- `raw_refs/`：原始文件的本地引用记录，不复制共享原始数据。

V1.2 数据不得直接覆盖 `data/processed/` 的默认 V1/V1.1 文件。训练前必须完成来源/活动/时间隔离、内容去重和人工标注质量审计。URL 仅作离线静态数据，邮件中的 URL 不得访问；附件只保留元数据，不下载、解压或执行。

## 当前获取批次

第一批资源曾包含 Figshare Seven Phishing Email Datasets，但本地审计确认其邮件主要来自
2000--2010 年，不能满足 V1.2 的时效性目标，已从 `raw_refs/` 删除并从来源清单移除。当前
保留 2025 年发布的中英文 LLMGen 辅助集（共 6,776 条）以及 2023 年 EPVME 数据集的
README/LICENSE 审计文件。明细见 `manifests/source_audit.csv`。LLMGen 明确标记为 LLM 生成，
只能用于辅助训练或鲁棒性测试，不能作为独立最终测试集。EPVME 当前只保留 README/LICENSE，
作为构造协议/MIME/UI 攻击语料的审计依据，不在 Phase 1 下载 49,136 封 EML 压缩包。
下一步应优先验证能提供 2022--2026 实际邮件时间覆盖的公开来源，再从中清洗、去重并抽取约
20K--30K 条补充样本；`license_status=review_required` 的资源不得直接进入训练。

## Sting9 快速核验结论

Sting9 页面描述了邮件正文、脱敏 raw headers、语言、攻击类型、原始时间戳和附件元数据，理论上
适合 V1.2 的轻量多视图数据补充。但截至 2026-09-08，研究入口将数据下载标为 `Coming Soon`，
API 需要研究者注册和 JWT，公开页面给出的 GitHub dump 也未能形成可重复下载入口。因此当前将
`sting9_email` 标记为 `failed`，不下载、不纳入训练；待公开转储或 API 访问重新可复现后再恢复审计。

中文公开训练集路线已在 2026-09-08 关闭。检索报告见
`docs/v1.2-data-source-and-paper-review-2026-09.md`：当前未找到同时满足真实中文邮件、公开可下载、
许可证可审计、非纯生成和近年时效性的来源。中文能力改由独立人工回归集、成对意图样本和字符级
多视图特征验证。

GPT 数据补充已完成初筛：从 3,746 条中保留 2,000 条平衡样本，字段和文本长度合格、无重复，
但全部属于 LLM 生成数据，仅作为 intent 分支辅助训练，不能作为独立测试或真实攻击泛化证据。
阈值校准使用 8 条固定人工边界样本，结果仅为 provisional；在获得更大规模人工标注前，不得
将校准阈值或 intent 概率直接转换为主模型融合权重。

```powershell
uv run python scripts\download_v1_2_sources.py --list
uv run python scripts\download_v1_2_sources.py
uv run python scripts\audit_v1_2_sources.py
uv run python scripts\audit_v1_2_data_layout.py
```
