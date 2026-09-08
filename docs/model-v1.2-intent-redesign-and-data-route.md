# V1.2 Intent 重设计与公开数据路线

**研究日期：2026-09-08**  
**目标：**为下一轮真实补充数据、intent 分支重设计和重训建立可执行的闭环。

当前数据工作区已按版本归档到 `data/v1/`、`data/v1.1/` 和 `data/v1.2/`。V1/V1.1 保存历史
摘要与本地归档副本；V1.2 仅登记待核验来源和新的处理路径，不会覆盖旧版 `data/processed/`。

## 一、结论先行

1. V1.1.1 已验证 `structure` 视图在中文和边界场景中提供独立信息；下一轮不需要继续用人工模板证明结构视图。
2. 当前 `intent` 视图是命中词计数，OOF 融合权重为 0。继续增加同类关键词不会解决问题，必须改为“邮件行为意图”的多标签监督任务。
3. 公开补充数据应拆成三种角色：真实训练语料、真实外部测试语料、仅用于 URL/攻击类型参考的情报数据；三者不能混用。
4. 下一轮版本建议命名为 **V1.2：真实补充数据与 Intent 重设计**。在 intent 分支通过外部测试门槛前，不提升为默认自动拦截模型。

## 二、公开数据集准入路线

### 2.1 数据源分层

| 数据源/类型 | 建议角色 | 处理结论 |
| --- | --- | --- |
| 真实脱敏邮件，含主题、正文、时间、语言和邮件头 | 训练 + 外部测试 | 优先纳入；按来源、活动和时间隔离 |
| Sting9 等带 `message_type`、`attack_type`、`detected_language`、时间和脱敏头字段的数据 | 中文/现代补充候选 | 先确认最终许可证；页面同时出现 CC0 与 ODC-BY-NC 表述，未确认前不写入仓库 |
| MeAJOR 等多来源合并邮件语料 | 规模化补充候选 | 先核对原始来源许可、重复邮件和时间分布，再决定是否训练 |
| PhishTank 等已验证钓鱼 URL feed | URL 特征、时间新鲜度、域名测试 | 只保存离线快照、时间和哈希；不访问邮件中的 URL，不把 URL-only 记录伪装成邮件正文 |
| 中文/英文 LLM 生成邮件集 | 训练增强或鲁棒性测试 | 可做辅助集；不作为独立最终测试集，因为生成分布和真实攻击活动不等价 |
| 邮箱探测流量、IP/账号扫描记录 | 非本任务数据 | 不并入邮件正文分类训练 |

### 2.2 推荐补充集构成

下一轮建议先形成一个可审计的 `v1_2_external_catalog`，而不是直接把所有下载数据混进训练：

| 分区 | 建议规模 | 主要用途 |
| --- | ---: | --- |
| 中文真实训练 | 600--1,000 | 学习中文行为表达和邮件格式 |
| 现代攻击训练 | 600--1,000 | OAuth consent、device-code、BEC、云文档、QR、附件诱导 |
| intent 标注训练 | 800--1,200（可与前两者重叠） | 多标签 intent 分支 |
| 中文外部测试 | >=200 | 只来自未见来源或未见活动 |
| 现代攻击外部测试 | >=300 | 按攻击类型分层，至少 40 条/主要类型 |
| 词面相近对照集 | >=150 对 | 检验意图而不是关键词 |

规模是实验规划，不是已有数据事实；实际数量以下载、脱敏、去重和许可审计后的清单为准。

### 2.3 隔离规则

所有记录进入统一目录前必须保留：

- `source_id`、原始来源 URL、下载时间、许可、文件 SHA-256；
- `message_timestamp`、`submission_timestamp`、语言、攻击类型；
- `campaign_id` 或可替代的活动/模板聚类标识；
- `source_hash`、规范化 `content_fingerprint`、`dedup_group`；
- `data_origin`：`real_public`、`synthetic_safe`、`llm_generated`、`url_only`；
- 是否含原始头、Reply-To、Return-Path、HTML、URL 元数据和附件元数据。

划分顺序必须是：来源/活动整组隔离 -> 时间切分 -> 内容去重 -> 训练/验证/测试。不能先随机切分再补做活动去重。现有 `spam_other` 硬负样本继续使用稳定 SHA-256 分桶，不能被新补充集重写。

## 三、Intent 分支重设计

### 3.1 从关键词计数改为行为语义标签

Intent 的基本单位不再是“出现了哪些词”，而是“谁要求收件人通过什么渠道完成什么动作”。建议采用多标签 schema：

| 标签 | 判定问题 | 正例语义 |
| --- | --- | --- |
| `credential_request` | 是否要求提供凭据或身份材料？ | 密码、验证码、身份证明、恢复码 |
| `oauth_authorization` | 是否要求授权应用、批准登录或输入设备代码？ | 同意第三方应用、device code、Allow |
| `payment_change` | 是否要求付款、转账或修改受益人？ | 更改收款账户、紧急付款 |
| `external_document_action` | 是否要求打开外部文档、下载附件或启用内容？ | 查看共享文件、下载 PDF/Office |
| `reply_or_data_request` | 是否要求回复、确认或发送资料？ | 回复确认、提供名单 |
| `social_pressure` | 是否使用紧急、权威、保密或绕过审批施压？ | 最后通知、领导要求、不要走流程 |
| `benign_notice` | 是否只是通知，且明确不要求敏感操作？ | 正常收据、维护通知、既有工单更新 |

另外保留三个可选辅助字段：

- `action_target`：账号、支付、文件、设备、个人资料、无；
- `requested_channel`：邮件回复、网页、OAuth 授权页、附件、二维码、既有门户；
- `negation_or_disclaimer`：是否出现“不会索要密码/验证码”等反向语义。

例如，“我们绝不会通过邮件索要验证码”应标为 `benign_notice=1`、`credential_request=0`；“请回复验证码完成验证”才标为 `credential_request=1`。这组反事实样本是当前 intent 最需要的数据。

### 3.2 推荐模型接口

V1.2 不建议立即引入大型 Transformer 作为生产依赖。先保持轻量、可解释和可消融：

```text
raw subject/body/header/context
        |
        +-- word/char TF-IDF -> phishing views
        |
        +-- static structure -> structure view
        |
        +-- multi-label intent encoder
              - 词/字符 n-gram
              - 否定范围与请求模态词
              - action-object pair
              - sender/request channel metadata
              - HTML/URL/attachment action cues
        |
        +-- per-label calibrated probabilities
              -> intent feature vector
              -> non-negative OOF fusion
```

Intent 分支先独立训练多标签分类器，而不是直接用 `phishing/legitimate` 总标签训练。推荐每个标签使用 one-vs-rest Logistic Regression 或 Linear SVM + 概率校准，输出 7 个标签概率和 3 个辅助字段编码。这样分支学习的是请求行为，融合层才有机会获得与词面不同的信息。

### 3.3 标注流程

1. 先抽取 100 条真实样本做双人试标，修订标签手册和边界例子。
2. 正式标注 800--1,200 条；至少 20% 样本双人复核。
3. 记录每个标签的正例数、双人一致率和 Cohen's kappa 或 Krippendorff's alpha。
4. 标签稀疏时不强行训练；单标签正例过少的类别先合并到上级意图。
5. 生成“同主题不同意图”配对集，并把配对 ID 作为不可跨集合边界。

推荐的对照对：

- 正常 MFA 安全提醒 vs 索要验证码；
- 正常付款完成通知 vs 要求修改收款账户；
- 正常云文档通知 vs 要求外部 OAuth 授权；
- 正常附件说明 vs 要求下载并启用内容；
- 正常领导通知 vs 紧急要求绕过审批。

## 四、实验与验收门槛

### 4.1 Intent 单分支指标

- 每个标签：Precision、Recall、F1、PR-AUC；
- 总体：macro-F1、micro-F1、subset accuracy；
- 概率：Brier score 和校准曲线；
- 按语言、攻击类型、邮件长度、是否有 URL/附件分层报告。

### 4.2 多视图贡献门槛

intent 不以“融合权重非零”作为唯一成功标准。候选通过条件应为：

1. 在至少两个未参与训练的外部测试分区上，相对 `word+char+structure` 的 macro-F1 或 PR-AUC 有稳定正增益；
2. 通过按活动/来源分组的 bootstrap 置信区间，增益不能只来自单个模板簇；
3. 主测试集 F1 下降不超过 0.5 个百分点；
4. hard-negative 测试集的 phishing 误报率不恶化超过预设容差；
5. 词面相近、意图相反的对照集上，intent 分支至少降低一类系统性错误。

OOF 权重、消融差值和置信区间全部写入 `data/manifests/`。如果 intent 仍然为 0，应保留失败报告并继续改进标注/表征，不调高权重强行纳入。

## 五、实施顺序

### Phase 1：数据审计

- 新增 `data/manifests/v1_2_source_catalog.csv` schema；
- 实现公开数据下载、哈希、许可证和时间记录；
- 只导入邮件或脱敏消息，不访问正文 URL；
- 完成来源/活动/时间隔离报告。

### Phase 2：Intent 标注与特征

- 新增 `intent_labels` 和 `intent_annotation_version` 字段；
- 实现多标签训练文件和标注质量报告；
- 将当前关键词特征保留为 baseline，对比新的行为编码；
- 增加否定、请求模态、动作-对象对和请求渠道特征。

### Phase 3：重训与外部评估

- 固定 V1.1.1 作为基线，不覆盖默认模型；
- 运行 `word+char+structure`、`+legacy_intent`、`+behavior_intent` 三组消融；
- 独立报告中文、现代攻击、对照配对和 hard-negative 结果；
- 只有达到门槛才生成 `v1.2-candidate` 元数据。

### Phase 4：安全与版本决策

- 复核原始数据不入 Git、敏感字段已脱敏；
- 复核附件只保留元数据；
- 复核 URL 只做离线文本/特征处理；
- 通过测试后再评审是否让 V1.2 成为默认模型。

## 六、目前不确定项

- Sting9 页面同时出现 CC0 和 ODC-BY-NC 许可表述，最终许可证必须向数据提供方或仓库元数据核实。
- 公开语料中“现代 OAuth/device-code/BEC 邮件正文”的可下载规模和完整邮件头覆盖率尚未确认，不能预先承诺样本数量。
- 中文公开数据可能更偏诈骗短信、网页文本或 LLM 生成邮件；若不能获得真实邮件，必须把它们标为辅助集，不冒充真实外部测试。
- PhishTank 只提供 URL 级情报，不能单独证明邮件 intent。

## 七、参考来源

- Sting9 Dataset Access，检索日期 2026-09-08：<https://sting9.org/dataset>
- FBI/IC3，Malicious Cyber Actors Gain Access to Victim Accounts Through Consent Phishing，2026-09-01：<https://www.ic3.gov/PSA/2026/PSA260901>
- PhishTank Developer Information，检索日期 2026-09-08：<https://phishtank.org/developer_info.php>
- LLMGen-Phishing-Email-Dataset，检索日期 2026-09-08：<https://huggingface.co/datasets/Dizzzy0x00/LLMGen-Phishing-Email-Dataset>
- 四川大学 CNEPD 数据说明，2019-12-04：<https://csri.scu.edu.cn/info/1012/1084.htm>
- CIC-Trap4Phish 2025 Dataset，检索日期 2026-09-08：<https://www.unb.ca/cic/datasets/trap4phish2025.html>
