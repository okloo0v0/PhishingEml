# PhishingEml 模型能力提升调研与实验路线报告

> 调研日期：2026-09-08
> 适用版本：当前 `v1.0.0` TF-IDF + Logistic Regression 基线之后的模型迭代
> 研究边界：只处理本地邮件原文、头部、正文、URL 字符串和附件元数据；不访问 URL，不下载、解压、执行或渲染附件。
> 证据范围：项目真实实验记录、公开论文、数据集原始页面及 APWG、Microsoft、Cloudflare、Proofpoint 等威胁研究资料。

## 一、执行摘要

1. **当前模型的首要问题不是测试集分数不够高，而是泛化证据不够强。** `v1.0.0` 在当前测试集 F1 为 0.9844、跨来源测试 F1 为 0.9841，但训练和测试仍以历史英文公开语料为主；普通垃圾邮件硬负样本的 phishing 判定率为 32.27%，12 条人工边界样本 F1 只有 0.8333。直接换成更大的神经网络，不一定能解决来源、年代和类别边界问题。
2. **推荐的近期主线是多视图轻量模型，而不是直接上线大语言模型。** 在现有 word TF-IDF 基础上增加字符 n-gram、邮件头/URL/附件结构特征和意图特征，分别建模后做校准的 late fusion。字符特征能覆盖拼写扰动、Unicode、域名和短文本，结构特征对 AI 改写更稳定，仍符合本地、静态、可解释的项目边界。
3. **Transformer 应作为对照分支。** 优先比较 DistilBERT 与一个多语言小模型，用于补足上下文、中文和自然语言改写；只有在“时间留出、来源留一、硬负样本、对抗样本”四类测试上稳定优于轻量基线，才替换主模型。论文中的随机切分高准确率不能直接视为部署收益。
4. **数据升级比模型升级更优先。** 训练集需要增加普通 spam、安全通知、账单/账号类正常邮件、短文本、中文/多语言、2023--2025 新型钓鱼和 AI 改写样本；必须保留来源、时间、攻击类型、生成方式和去重组，避免同一模板跨集合泄漏。
5. **时效性需要成为持续机制。** 建立按月份/来源/攻击类型的回放集、漂移监测、人工反馈池和版本晋级门槛。新模型至少要报告 PR-AUC、phishing recall、固定低误报率下的召回、Brier score、分组指标和最坏分组结果，而不只报告 Accuracy/F1。

## 二、当前模型基线与真实薄弱点

### 2.1 当前算法和数据

当前模型采用：

```text
subject + text_body
  -> Unicode/空白规范化
  -> 邮箱、URL、长数字占位符替换
  -> word TF-IDF (1,2)-gram，最多 50,000 特征
  -> class_weight=balanced 的 Logistic Regression
  -> phishing probability
```

模型版本为 `v1.0.0`，特征版本为 `text-v1`，生产标签阈值为 0.50。训练、验证、测试样本分别为 10,175、2,181、2,181；另有 1,611 条跨来源测试和 1,695 条 `spam_other` 硬负样本。模型文件、数据版本、随机种子和 SHA-256 已记录，训练与推理使用同一清洗函数。

项目内证据：[模型元数据](../models/model_meta.json)、[实验记录](experiments.csv)、[数据说明](../data/README.md)、[端到端测试报告](test-report.md)。

### 2.2 已有结果应如何解释

| 评估集合 | 当前结果 | 能说明什么 | 不能说明什么 |
|---|---:|---|---|
| 主测试集 | F1 0.9844，Accuracy 0.9849 | 对当前数据分布区分能力强 | 不能证明对新年代、新语言和新攻击稳定 |
| 跨来源测试 | F1 0.9841 | 对已纳入数据源的来源变化有一定适应性 | 不等于真正的未见来源，因为语料家族仍可能重合 |
| 980 封原始 MIME 联调 | F1 0.9703，980/980 成功 | 解析、规则、模型、持久化链路可用 | 与离线测试不是同一评估口径 |
| `spam_other` 硬负样本 | 32.27% 被判 phishing | 揭示 spam/phishing 边界混淆 | 不能用调高阈值简单掩盖 |
| Ling 外部集合 | 全体 4.20%、spam 子集 17.25% 被判 phishing | 外部硬负误报较主硬负集低但仍存在 | 数据年代仍旧，不能代表当前邮件流量 |
| 12 条人工边界样本 | F1 0.8333 | 中文与边界案例存在明显改进空间 | 样本太少，不能作为正式指标 |

### 2.3 错误归因

当前 58 个已分析错误中，false negative 41 个、false positive 17 个；短文本占 28 个，含非 ASCII 字符占 18 个。全局高权重词中还出现数据来源和年代痕迹，例如年份、邮件列表格式以及特定语料词。这意味着下一版应优先解决：

- 短正文和缺少正文的邮件；
- 中文、多语言和编码噪声；
- 普通营销 spam 与真正 phishing 的区分；
- 同义改写、拼写扰动、Unicode 和文本填充；
- BEC、纯回复请求、设备码授权等无典型恶意 URL 的社会工程；
- 整图邮件、二维码和被图片承载的品牌/诱导文本。

## 三、钓鱼技术变化及对模型的影响

### 3.1 生成式 AI 与高度个性化文本

生成式 AI 能以很低成本生成语法自然、角色相关、主题多变的邮件。Microsoft 在 2026 年披露的设备码钓鱼活动中观察到，攻击者用生成式 AI 生成与受害者岗位匹配的 RFP、发票和制造流程诱饵，并结合自动化和动态设备码绕过静态特征。[Microsoft Defender Security Research, 2026](https://www.microsoft.com/en-us/security/blog/2026/04/06/ai-enabled-device-code-phishing-campaign-april-2026/)

**模型影响：** 拼写错误、固定紧迫词和旧模板相似度会失效；应提高意图、请求动作、身份关系和结构不一致信号的权重。不能把“像 AI 写的”本身当作钓鱼证据，因为正常邮件同样可能由 AI 辅助生成。

### 3.2 二维码、整图邮件和视觉承载

APWG 在 2025 年报告大量二维码邮件活动；Proofpoint 称其在 2025 年上半年识别到 420 万个 QR code threats，并观察到恶意邮件中 URL 的使用频率约为附件的四倍。[APWG Q1 2025](https://apwg.org/trendsreports)、[Proofpoint Human Factor Vol. 2](https://www.proofpoint.com/us/blog/email-and-cloud-threats/human-factor-vol-2-offers-new-insights-phishing)

Cloudflare 还给出了整封正文由带链接 JPEG 构成的案例：品牌和诱导词只存在于图片中，纯文本过滤器无法识别。[Cloudflare Phishing Threats Report, 2023](https://blog.cloudflare.com/2023-phishing-report/)

**模型影响：** 当前只分析正文文本和 `<a>` 链接，会漏掉图片内文字与 QR 内容。MVP 内可先增加安全的结构信号，如 `inline_image_count`、`image_link_count`、`text_to_image_ratio`、`cid_reference_count` 和空正文+图片组合。真实图片解码、OCR 和 QR 解码应放到受资源限制的隔离进程，经过单独安全评审后再启用，不能在 Web 进程中直接处理附件。

### 3.3 受信任服务、跳转链和官方认证流程滥用

Microsoft 披露的活动使用 Vercel、Cloudflare Workers、AWS Lambda 和被入侵的正常域名承担跳转，并最终引导用户进入真实的 Microsoft device login 流程。Cloudflare 的统计也表明身份欺骗、信誉良好的服务和合法域名会削弱单一黑名单判断；其 2022--2023 数据中，89% 的 unwanted messages 至少通过了 SPF、DKIM 或 DMARC 中的一项。[Microsoft, 2026](https://www.microsoft.com/en-us/security/blog/2026/04/06/ai-enabled-device-code-phishing-campaign-april-2026/)、[Cloudflare, 2023](https://blog.cloudflare.com/2023-phishing-report/)

**模型影响：** “HTTPS”“知名域名”“认证通过”不能作为安全结论。项目不能访问 URL，因此应静态识别多级跳转参数、URL 中嵌套 URL、设备码/授权意图、显示域名与目标域名关系，并把认证结果作为一个证据而不是否决其他风险。

### 3.4 BEC、冒充和无链接攻击

APWG 2026 Q1 报告记录 971,181 起 phishing attacks，并指出 BEC 通过冒充员工、供应商或可信方诱导转账或交付敏感信息；72% 的 BEC 使用免费 Webmail 域名。[APWG Q1 2026](https://docs.apwg.org/reports/apwg_trends_report_q1_2026.pdf)

**模型影响：** 模型需要识别付款、账户变更、保密、绕过审批、回复敏感信息、外部聊天迁移等行为意图，而不能只依赖恶意 URL 和附件。

### 3.5 对抗改写与概念漂移

IWSPA 2023 对抗数据集包含 TextFooler、PWWS、DeepWordBug、BAE 对文本的成功攻击样本，以及 GPT-2 合成钓鱼邮件。[IWSPA 2023 Adversarial/Synthetic Dataset](https://github.com/ReDASers/IWSPA-2023-Adversarial-Synthetic-Dataset)

2026 年预印本 PhishSigma++ 的实验进一步显示，在 Good Word 文本填充下，基于类型实体关系的模型比 token Bayesian 和 DistilBERT 基线更稳定。这是支持“学习相对不变的结构/关系信号”的新证据，但尚不应视为已充分复现的成熟结论。[PhishSigma++, 2026](https://arxiv.org/abs/2605.11619)

## 四、前人算法路线对比

### 4.1 传统文本与字符模型

| 路线 | 设计 | 优点 | 局限 | 对本项目价值 |
|---|---|---|---|---|
| word TF-IDF + LR/SVM | 词/短语稀疏向量，线性分类 | 快、稳定、可解释、CPU 友好 | 易学习模板、来源和年代词 | 当前基线，必须保留 |
| char TF-IDF + Linear SVM/LR | 字符 3--5/3--6 gram | 对拼写变形、短文本、URL、Unicode 较敏感 | 对长程语义弱，维度较大 | **近期优先级最高** |
| 词+字符双通道 | 两路概率或特征拼接 | 兼顾语义词组与局部扰动 | 需校准并控制重复特征 | 适合 v1.1 主模型 |
| 树模型处理结构特征 | RF、XGBoost、GBDT | 非线性关系、特征重要性清楚 | 小数据易过拟合，概率需校准 | 适合作为结构分支 |

IWSPA-AP 2018 专门设置了“正文”和“完整邮件”两个子任务，并以接近真实分布的不平衡数据评价模型，说明邮件头与类别不平衡从早期公开基准起就是重要问题。[IWSPA-AP 2018](https://ceur-ws.org/Vol-2124/invited_paper_1.pdf)

### 4.2 深度学习和 Transformer

| 代表工作 | 算法设计 | 使用数据 | 报告结果 | 应用判断 |
|---|---|---|---|---|
| THEMIS (2019) | header/body、字符/词多层向量，改进 RCNN + attention | IWSPA-AP | Accuracy 99.848%，FPR 0.043% | 证明多层级建模可行，但架构和数据较旧，复现成本高 |
| CATBERT (2020) | Tiny BERT 文本表示 + 邮件头上下文 | 研究方社会工程邮件集 | FPR 1% 时 detection rate 87%，高于其 LR/DistilBERT/LSTM 基线 | 支持“语义+上下文”而非纯正文路线 |
| Explainable DistilBERT (2024) | 微调 DistilBERT + LIME/Transformer Interpret | Kaggle，11,322 safe + 7,328 phishing，过采样平衡 | 不平衡测试 Accuracy 97.50%，平衡测试 98.48% | 可作语义/XAI 对照；同源随机切分不足以证明时间泛化 |
| MeAJOR (2025) | 多源数据、工程特征，比较 RF/XGB/MLP/CNN | 135,894 条多源样本 | XGBoost F1 98.34% | 支持多源+结构特征；与本项目已有来源高度重叠，必须重新去重 |
| PhishSigma++ (2026, 预印本) | 40 类实体、5 类跨实体关系、类型图和稀疏关系掩码 | 29,142 封 RFC822 邮件 | clean F1 0.9675；Good Word padding 下 F1 0.9579 | 前沿结构不变性方向；适合借鉴特征，不宜整套照搬 |

来源：[THEMIS](https://ieeexplore.ieee.org/document/8701426/)、[CATBERT](https://arxiv.org/abs/2010.03484)、[Explainable DistilBERT](https://arxiv.org/abs/2402.13871)、[MeAJOR](https://arxiv.org/abs/2507.17978)、[PhishSigma++](https://arxiv.org/abs/2605.11619)。

### 4.3 URL、意图与多模态分支

- **URLTran** 对 URL 字符序列做 Transformer 预训练和微调，并加入 homoglyph、compound word split 对抗样本；论文报告在 FPR 0.01% 时 TPR 86.80%，说明低误报率下的召回比单一 Accuracy 更适合安全模型评价。[URLTran, 2021](https://arxiv.org/abs/2106.05256)
- **Profiler** 将威胁等级、认知操纵和邮件类型三个模型组合为风险画像；在 9,000 legitimate + 900 phishing 的机构数据上，相比其 ML ensemble 报告减少 30% false positives 和 25% false negatives。其价值是把社会工程意图作为独立视图，而非把所有信号压进一个标签。[Profiler, 2022](https://arxiv.org/abs/2208.08745)
- **DIDECO** 在 2026 年发布了 220 封 LLM 生成 spear-phishing 邮件、20 类显式/隐式意图和 2,162 条标注，可用于意图模型的小规模验证或辅助训练，但不能单独承担主分类评估。[DIDECO, LREC 2026](https://aclanthology.org/2026.lrec-1.542/)
- **QR 结构检测**已有研究尝试不提取载荷、直接使用 QR 像素/结构特征，最佳 XGBoost AUC 约 0.9133。该方向说明二维码可被独立建模，但数据为生成 QR，且本项目需要先解决安全隔离和数据真实性。[Trad & Chehab, 2025](https://arxiv.org/abs/2505.03451)

### 4.4 为什么不推荐直接使用通用 LLM 作为主判定器

ChatSpamDetector 等研究报告了很高的 LLM 分类准确率和自然语言解释能力，但通用 LLM 作为本项目主模型会引入：模型/API 版本漂移、网络依赖、邮件隐私外发、不可复现实验、推理成本和 prompt injection 风险。[ChatSpamDetector, 2024](https://arxiv.org/abs/2402.18093)

因此，LLM 更适合作为**离线研究对照或对已脱敏样本生成候选解释**，不进入默认检测链路。任何邮件正文都应视为不可信数据，不能让其中指令改变检测流程、系统提示或工具调用。

## 五、数据集调研与使用建议

### 5.1 主要公开数据集

| 数据集 | 规模/内容 | 年代 | 适合用途 | 主要风险 |
|---|---|---|---|---|
| Enron | 约 50 万封、约 150 名用户；官方版本无附件 | 主要为 1998--2002 企业邮件 | legitimate、工作邮件上下文、线程去重 | 年代旧、隐私敏感、存在完整性/编辑问题，不应直接当现代分布 |
| SpamAssassin Public Corpus | 6,047 封；spam/easy ham/hard ham 等 | 2002--2005 | hard ham、普通 spam 负例 | 年代旧，地址和主机部分脱敏，版权仍归原作者 |
| Nazario/Monkey.org | mbox 与按年 phishing 文件；当前目录覆盖到 2025 | 2005--2025 | phishing 正例、时间留出 | 年度文件可能与整理数据重复；必须核验许可和内容隐私 |
| TREC Spam Track | 2005--2007 公共 spam corpora，按时间顺序评测 | 2005--2007 | 在线/时间顺序 spam 评测、硬负例 | spam 不等于 phishing；年代旧 |
| IWSPA-AP | 正文/完整邮件两个不平衡任务，含 synthetic attacks | 2018 | 标准化 phishing benchmark、header ablation | 规模有限，需遵守共享任务许可 |
| Curated Datasets (Zenodo 8339691) | 11 个整理集，覆盖 1995--2022 | 发布于 2023 | 快速复现实验、来源对照 | 多个子集来自 Enron/Nazario/SpamAssassin/TREC，跨文件重复风险高 |
| IWSPA 2023 Adversarial/Synthetic | 4 类 TextAttack 对抗样本 + GPT-2 合成样本 | 2023 | 鲁棒性测试 | 对特定 ALBERT 生成，不能代表所有真实攻击 |
| MeAJOR | 135,894 条、多源、工程特征 | 2025 | 大规模结构特征基准 | 合并公开源可能与现有训练集高度重叠；需溯源后使用 |
| DIDECO | 220 封 LLM spear-phishing、20 类意图 | 2026 | 意图辅助任务、AI 文本边界测试 | 全为合成且规模小，不适合作主测试集 |

原始资料：[CMU Enron](https://www.cs.cmu.edu/~enron/)、[Apache SpamAssassin](https://spamassassin.apache.org/old/publiccorpus/readme.html)、[Nazario/Monkey.org](https://monkey.org/~jose/phishing/)、[NIST TREC Spam](https://trec.nist.gov/data/spam.html)、[IWSPA-AP](https://ceur-ws.org/Vol-2124/)、[Zenodo Curated Datasets](https://zenodo.org/records/8339691)。

### 5.2 推荐的数据角色划分

下一版不要再把所有公开数据随机混合后切分。建议按数据角色冻结：

| 数据角色 | 建议来源 | 是否参与训练 |
|---|---|---:|
| 主训练集 | 当前去重数据 + 新增 hard ham/spam + 经审核的新 phishing | 是 |
| 同分布验证集 | 与训练相同来源但 dedup group 隔离 | 仅调参/校准 |
| 来源留一测试 | 每次完整留出一个来源 | 否 |
| 时间留出测试 | 训练截至 2022，验证 2023，测试 2024--2025 | 否 |
| 硬负测试 | 普通营销、账单、账号通知、招聘、newsletter、安全告警 | 否 |
| 对抗测试 | IWSPA 2023 + 自建 Unicode/插词/同义改写 | 否 |
| 多语言测试 | 中文、英文及少量其他语言的正常/钓鱼配对 | 否 |
| 新技术测试 | BEC、无 URL、QR/整图、设备码、云服务跳转、AI 改写 | 否 |

### 5.3 新数据标注字段

每条样本至少增加：

```text
sample_id, source, source_file_hash, collected_year, received_at_available
label, label_provenance, language, attack_type, delivery_type
has_url, has_attachment, has_inline_image, has_qr, is_ai_generated
dedup_group, thread_group, template_group, privacy_status, license
```

`is_ai_generated` 只描述数据来源，不作为模型输入特征。攻击类型建议使用多标签：`credential`、`payment_bec`、`attachment`、`qr`、`oauth_device_code`、`brand_impersonation`、`reply_request`、`data_request`、`job_scam`、`other`。

## 六、推荐模型架构

### 6.1 v1.1：轻量多视图模型（优先实施）

```text
ParsedEmail
  ├─ Text lexical view
  │    ├─ subject word TF-IDF (1,2)
  │    ├─ body word TF-IDF (1,2)
  │    └─ subject+body char TF-IDF (3,5)
  │          -> calibrated LinearSVC / Logistic Regression
  │
  ├─ Static structure view
  │    ├─ header completeness and domain relations
  │    ├─ URL count/protocol/IP/punycode/embedded URL/query features
  │    ├─ attachment/inline image/MIME/HTML features
  │    └─ language, length and text-image ratio
  │          -> HistGradientBoosting / RandomForest / Logistic Regression
  │
  ├─ Intent view
  │    ├─ credential/payment/download/reply/authorization request
  │    └─ urgency/authority/secrecy/process bypass
  │          -> rule features first; supervised auxiliary model later
  │
  └─ Existing rules and offline blacklist

OOF probabilities from model branches
  -> calibrated logistic meta-classifier
  -> phishing probability + uncertainty
  -> current rule fusion contract
  -> low / medium / high + explanations
```

实现要点：

- 使用 out-of-fold (OOF) 预测训练 meta-classifier，禁止直接用训练集内概率做融合。
- 字符特征保留标点和 Unicode 归一化前后的差异计数；不要只依赖已清洗文本。
- 模型分支使用原子结构特征，不直接输入 `rule_score`、`final_score` 或黑名单命中，避免在当前 0.65/0.35 融合中重复计分。
- 对所有概率做校准，并记录 Brier score 和 calibration curve。
- 输出 branch probabilities、top linear features 和结构特征贡献，解释文本使用固定模板生成，不使用在线 LLM。
- 新模型使用 `feature_version=text-structure-v2`；在修改 `ModelInput`、元数据和生产阈值前，先走共享契约变更。

### 6.2 v1.2：小型多语言 Transformer 对照

推荐比较两类方案：

1. DistilBERT 级别英文模型，用于与相关论文直接对照；
2. 多语言轻量编码器或 XLM-R/Multilingual MiniLM 级模型，用于中文和非 ASCII 场景。

Transformer 分支只接收脱敏、截断后的文本；结构分支仍独立保留。训练时对比 class-weighted loss 与 focal loss，不通过在切分前复制少数类来平衡。若 GPU 不可用，可先冻结编码器提取 embedding，再训练校准 Logistic Regression，作为成本更低的语义基线。

**晋级条件：** 在相同数据划分下，最坏分组 phishing recall、硬负误报率和时间留出 PR-AUC 均优于 v1.1；若只提升随机测试 Accuracy，不替换主模型。

### 6.3 v1.3：关系不变性与有限视觉特征

在 v1.1 稳定后，可借鉴 PhishSigma++，构造不依赖具体词面的关系特征：

- `sender_domain != reply_to_domain`；
- 显示域名、目标域名、品牌实体之间的关系；
- 请求动作与目标资产（账号、验证码、付款、文件）的关系；
- 发件人身份与免费邮箱/组织声明的关系；
- 附件类型、正文动作和链接类型之间的关系。

视觉分支先只增加图片/MIME/HTML结构统计。OCR/QR 解码必须采用隔离进程、超时、内存/像素上限和已审计解码库；不得访问解码出的 URL。此功能安全评审未通过前，不进入默认分析链路。

## 七、实验设计与验收门槛

### 7.1 必做消融实验

| 实验 ID | 变量 | 目的 |
|---|---|---|
| E1 | 当前 word TF-IDF + LR | 冻结对照基线 |
| E2 | char TF-IDF + LR/LinearSVC | 验证短文本和扰动收益 |
| E3 | word + char | 验证双通道互补性 |
| E4 | 仅结构特征 | 测量文本之外的独立能力 |
| E5 | word + char + structure | v1.1 候选 |
| E6 | E5 + 三分类训练 | 验证 spam/phishing 边界改善 |
| E7 | DistilBERT | 英文语义对照 |
| E8 | 多语言小模型 | 中文/多语言对照 |
| E9 | 最佳文本模型 + structure late fusion | v1.2 候选 |
| E10 | E9 + 对抗训练 | 验证鲁棒性，避免只看 clean 指标 |

### 7.2 指标体系

主指标：

- PR-AUC；
- phishing precision、recall、F1；
- false positive rate 和 false negative rate；
- recall at FPR = 1%、0.5%（样本量允许时）；
- Brier score、Expected Calibration Error；
- 单封 CPU 推理 P50/P95、模型大小和峰值内存。

分组指标：

- source、year、language、attack_type；
- text length、URL/附件/图片存在性；
- legitimate、spam_other、phishing；
- clean、Unicode、同义改写、Good Word padding、LLM rewrite。

除平均值外，必须报告**最坏分组 recall、最坏分组 FPR 和各组样本量**。样本少于 30 的分组只作为案例结果，不给出稳定百分比结论。

### 7.3 建议晋级门槛

新版本替换 `v1.0.0` 前，建议同时满足：

1. 时间留出和来源留一测试的 PR-AUC 均不低于基线；
2. `spam_other` 硬负误报率相对下降至少 30%，且 phishing recall 下降不超过 1 个百分点；
3. 中文/非 ASCII 与短文本分组 recall 均有可重复提升；
4. 对抗集平均 recall 不低于 clean recall 的 90%；
5. Brier score 优于基线，风险区间校准误差可解释；
6. 单封 CPU P95 推理时间满足本地演示 3 秒总响应目标；
7. 重新执行全套解析、API、安全和 980 封 MIME 回放，无新增未处理异常。

上述数值是本项目的工程验收建议，不是论文或行业通用标准；应在第一次完整实验后根据样本规模冻结。

## 八、应对时效性的持续机制

### 8.1 数据与评估滚动窗口

- `train`: 历史稳定数据；
- `calibration`: 最近一个已完成时间窗口；
- `shadow_test`: 更新但未用于调参的最新窗口；
- `golden_regression`: 固定安全、解析和典型攻击样本，永不进入训练。

每个季度或每次收集到足够新标注后执行 shadow evaluation，不按日历自动发布新模型。任何新数据先查来源许可、隐私、标签可信度、精确重复、规范文本重复、SimHash/MinHash 近重复和模板组泄漏。

### 8.2 漂移监测

离线记录并比较：

- 邮件长度、语言、URL/附件/图片比例；
- 规则命中分布、结构特征分布；
- 模型概率分布、低置信度比例和各风险等级比例；
- 已反馈样本上的误报/漏报；
- 字符 n-gram 或 embedding 的 Population Stability Index、Jensen-Shannon divergence。

漂移告警只触发“审查和补标”，不能自动把新邮件加入训练或自动替换生产模型。反馈样本需要人工确认，防止攻击者通过恶意反馈污染模型。

### 8.3 新攻击回归库

至少维护以下安全构造样本：

- 语法自然的 AI 改写钓鱼与 AI 辅助正常邮件配对；
- 同义替换、插入正常段落、字符拆分、零宽字符、同形字符；
- 中文/英文混写和编码异常；
- 无 URL 的 BEC、付款账户变更、保密/绕流程请求；
- device code/OAuth 授权诱导；
- 使用合法云服务域名或嵌套跳转参数；
- 整图、图片链接、QR 和空正文邮件；
- 安全但包含“账号、验证、付款、紧急”等词的 hard negative。

## 九、实施路线与工作量建议

### 阶段 A：两至三天，建立可信评估

1. 冻结 v1.0.0 预测和当前所有数据划分。
2. 增加时间、攻击类型、语言、hard negative 清单。
3. 实现统一 benchmark 脚本和分组指标。
4. 建立 2024--2025 phishing 时间留出集和正常邮件配对集。

**交付：** `benchmark_manifest.json`、固定 split、基线完整指标和错误案例表。

### 阶段 B：三至五天，完成 v1.1

1. 增加 char TF-IDF。
2. 从 `ParsedEmail` 提取结构化原子特征。
3. 比较二分类与 `legitimate/spam_other/phishing` 三分类训练。
4. 采用 OOF late fusion 和概率校准。
5. 接入现有 `ModelPredictor` 适配层并保留 v1.0.0 回退。

**交付：** `text-structure-v2`、消融表、模型文件、元数据、错误分析和回归测试。

### 阶段 C：三至七天，语义模型对照

1. 训练 DistilBERT 与多语言小模型。
2. 运行来源留一、时间留出、对抗和 hard negative 测试。
3. 比较模型收益、CPU 时延、大小、解释稳定性。

**交付：** 是否升级到 v1.2 的明确决策，而不是默认替换轻量模型。

### 阶段 D：后续研究

1. 实体关系特征与意图多任务学习。
2. 隔离的 OCR/QR 静态分析原型。
3. 反馈审核、漂移看板和 shadow model。

## 十、风险、分歧与待核实项

| 项目 | 当前判断 | 置信度/原因 |
|---|---|---|
| char n-gram 能改善拼写和短文本鲁棒性 | 值得优先验证 | 高；成熟方法且成本低，但具体收益需本项目消融 |
| Transformer 一定优于当前 LR | 不成立 | 高；论文数据和切分不同，当前基线已很强 |
| 结构/实体关系对 AI 改写更稳定 | 方向合理 | 中；CATBERT、Profiler、PhishSigma++ 等支持，但最新结果需复现 |
| MeAJOR 可直接扩充当前数据 | 不建议 | 高；其多源组成与当前 Enron/Nazario/SpamAssassin/Zenodo 家族可能重叠 |
| AI 生成文本可以直接检测 | 不应作为主目标 | 高；正常邮件也可能由 AI 辅助，来源检测与恶意意图不同 |
| QR/OCR 可立即加入 Web 进程 | 不建议 | 高；与当前附件安全边界冲突，需要隔离和资源限制 |
| 2024--2025 Nazario 年度文件可用于时间测试 | 有潜力 | 中；文件存在，但仍需核验许可、标签、隐私和与现有数据的重复 |
| 2026 预印本结论可作为生产依据 | 不可以 | 高；应作为前沿线索，等待同行评审或本地复现 |

待核实事项：

- 当前原始样本是否保留可靠的邮件时间，能否支持严格 chronological split；
- 2024--2025 Nazario 数据的具体许可与可再分发范围；
- 本地硬件是否能在 3 秒总响应预算内运行多语言 Transformer；
- 是否允许新增隔离进程处理 inline image，及其与“不得渲染附件”边界的契约解释；
- 三分类模型如何映射回当前二分类 `DetectionResult`，需要先冻结契约。

## 十一、参考来源

以下页面均于 2026-09-08 检索；论文报告的指标均是各自数据和切分下的结果，未与本项目直接横向排名。

1. Fang et al., [Phishing Email Detection Using Improved RCNN Model With Multilevel Vectors and Attention Mechanism](https://ieeexplore.ieee.org/document/8701426/), IEEE Access, 2019.
2. El Aassal et al., [Anti-Phishing Pilot at ACM IWSPA 2018](https://ceur-ws.org/Vol-2124/invited_paper_1.pdf), IWSPA-AP, 2018.
3. Lee et al., [CATBERT: Context-Aware Tiny BERT for Detecting Social Engineering Emails](https://arxiv.org/abs/2010.03484), 2020.
4. Maneriker et al., [URLTran: Improving Phishing URL Detection Using Transformers](https://arxiv.org/abs/2106.05256), 2021.
5. Shmalko et al., [Profiler: Profile-Based Model to Detect Phishing Emails](https://arxiv.org/abs/2208.08745), 2022.
6. Gholampour & Verma, [Adversarial Robustness of Phishing Email Detection Models and Dataset](https://github.com/ReDASers/IWSPA-2023-Adversarial-Synthetic-Dataset), 2023.
7. Uddin & Sarker, [An Explainable Transformer-based Model for Phishing Email Detection](https://arxiv.org/abs/2402.13871), 2024.
8. Koide et al., [ChatSpamDetector](https://arxiv.org/abs/2402.18093), 2024.
9. Mendes et al., [MeAJOR Corpus](https://arxiv.org/abs/2507.17978), 2025.
10. Trad & Chehab, [Detecting Quishing Attacks with Machine Learning Techniques Through QR Code Analysis](https://arxiv.org/abs/2505.03451), 2025.
11. Cho & Seo, [Towards Reliable and Practical Phishing Detection](https://aclanthology.org/2025.naacl-industry.18/), NAACL Industry 2025.
12. Popovic et al., [DIDECO: An Annotated Dataset for Intent Detection in Digital Communications](https://aclanthology.org/2026.lrec-1.542/), LREC 2026.
13. Shang et al., [PhishSigma++: Malicious Email Detection with Typed Entity Relations](https://arxiv.org/abs/2605.11619), 2026 preprint.
14. Fernando & Komninos, [Evaluating and Combating the Impact of Concept Drift](https://arxiv.org/abs/2606.11471), 2026 preprint.
15. [CMU Enron Email Dataset](https://www.cs.cmu.edu/~enron/).
16. [Apache SpamAssassin Public Corpus](https://spamassassin.apache.org/old/publiccorpus/readme.html).
17. [Nazario Phishing Corpus / Monkey.org](https://monkey.org/~jose/phishing/).
18. [NIST TREC Spam Track](https://trec.nist.gov/data/spam.html).
19. Champa, [Phishing Email Curated Datasets](https://zenodo.org/records/8339691), Zenodo, 2023.
20. [APWG Phishing Activity Trends Report, Q1 2026](https://docs.apwg.org/reports/apwg_trends_report_q1_2026.pdf).
21. [Microsoft: Inside an AI-enabled device code phishing campaign](https://www.microsoft.com/en-us/security/blog/2026/04/06/ai-enabled-device-code-phishing-campaign-april-2026/), 2026.
22. [Cloudflare Phishing Threats Report](https://blog.cloudflare.com/2023-phishing-report/), 2023.
23. [Proofpoint Human Factor Vol. 2](https://www.proofpoint.com/us/blog/email-and-cloud-threats/human-factor-vol-2-offers-new-insights-phishing), 2025.

## 十二、最终建议

项目下一版应以 **v1.1 轻量多视图模型** 为明确目标：先补数据角色和评估框架，再实现 word+char+structure+intent 的 OOF 融合与校准。Transformer、多模态和实体图是有价值的研究分支，但必须通过时间留出、来源留一、硬负样本和对抗样本证明增益后再进入主链路。

这条路线既保留了当前系统的可解释性、静态安全边界和 CPU 可运行性，也能直接应对当前最明显的模型缺口：普通 spam 误报、短文本、多语言、AI 改写、BEC 无链接邮件，以及文本之外的结构信号。
