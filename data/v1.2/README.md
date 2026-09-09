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
阈值校准使用 46 条固定人工双语边界样本，7 个意图标签均有至少 6 个正例；其中
`reply_or_data_request` 有 8 个正例，`social_pressure` 有 10 个正例。逐标签阈值在推理阶段的
最终 intent 概率上校准，边界集精确匹配率由默认阈值的 91.3% 提升到 93.5%。结果仍为
provisional：校准和报告使用同一固定边界集，只能验证实现与受控边界行为，不能代替来源隔离的
外部测试；在获得更大规模人工标注前，不得将校准阈值或 intent 概率直接转换为主模型融合权重。

当前保留 3 条失败样本作为后续回归靶点：英文正常登录通知漏检 `benign_notice`、中文已付发票
通知误触发付款变更/回复请求、中文保密施压表达漏检 `social_pressure`。校准参数和默认/校准后
逐样本结果分别记录在 `manifests/intent_threshold_calibration.json`、默认阈值对照
`manifests/intent_boundary_eval_default.json` 与校准后的正式边界报告
`manifests/intent_boundary_eval.json`。

## 来源隔离人工标签验证

新增 DiFraud phishing benchmark 的上游 `test` 分片作为外部验证来源。数据卡为 MIT，仓库发布于
2023 年并在 2024 年更新；本地从 Hugging Face 公共镜像下载，Git blob OID 已与上游 API 公布的
`89258551a9892a21907c4aae82e3f7be9ce80adb` 一致。该分片不进入训练，只确定性抽取 100 条
（50 欺骗、50 非欺骗，seed=1202），并对训练数据执行双指纹去重，精确重叠为 0。
这里的隔离仅表示上游 test 分片未参与训练且精确内容/模型文本指纹不重叠，不能排除潜在的
活动或语义模板重叠。

人工真值仅是二分类欺骗标签，不是 V1.2 的 7 类 intent 标签。因此独立验证目标限定为“是否激活
任一危险意图”：Precision 0.773、Recall 0.680、F1 0.723，混淆矩阵 TN/FP/FN/TP 为
40/10/16/34。结果说明 intent 有跨来源信号，但漏检仍高，不能据此调整阈值或融合权重。底层
benchmark 来自 2020 年，也不能证明对 2022--2026 现代攻击的时效性。完整审计见
`manifests/intent_external_holdout_eval.json`。

本轮另否决 Chataut 2024 候选：实际内容包含 2002 年邮件，所谓 phishing 分片标签为 `spam`，
且仓库无明确许可证；下载文件已删除。Twente 2024 仍是更理想的独立验证候选，但当前环境访问
Zenodo 文件端点返回 403，未使用任何无法通过官方 MD5 的代理副本。

```powershell
uv run python scripts\download_v1_2_sources.py --list
uv run python scripts\download_v1_2_sources.py
uv run python scripts\audit_v1_2_sources.py
uv run python scripts\evaluate_external_intent_holdout.py
uv run python scripts\audit_v1_2_data_layout.py
```
