# 成员1：数据获取与机器学习实施计划书

**项目：** PhishingEml 钓鱼邮件静态分析与检测系统
**适用角色：** 成员1（数据与模型负责人）
**计划版本：** v1.0
**编制日期：** 2026-09-01
**依据：** `AGENTS.md`、`docs/shared-contract.md`、`钓鱼邮件检测系统详细实现方案.md`

## 当前执行状态

截至 2026-09-01：

- [x] 步骤1：确认环境、契约和任务边界；
- [x] 步骤2：建立数据目录、来源登记机制并收集第一批原始邮件；
- [x] 步骤3：统一读取邮件容器并生成未清洗 JSONL；
- [x] 步骤4：构造统一文本和清洗规则；
- [x] 步骤5：去重和数据泄漏检查；
- [x] 步骤6：标签清洗和数据划分；
- [x] 步骤7：训练 TF-IDF + Logistic Regression 基线；
- [x] 步骤8：模型评估与错误分析；
- [x] 步骤9：生成模型元数据和版本记录；
- [x] 步骤10：实现 ModelPredictor 推理接口；
- [ ] 步骤11及以后：尚未开始。

当前原始候选库存为 Nazario 钓鱼邮件 4382 封、SpamAssassin ham 正常邮件 6951 封。该数量为清洗去重前统计；正式训练仍以清洗去重后 `phishing` 与 `legitimate` 各 4000--5000 封为目标。来源、SHA-256 和下载状态见 `data/manifests/sources.csv`，容器内邮件数量见 `data/manifests/inventory.csv`。

步骤3已通过 `scripts\prepare_raw_dataset.py` 生成 11,333 条未清洗中间记录，其中
`phishing` 为 4,382 条、`legitimate` 为 6,951 条。统计结果见
`data/manifests/raw_parse_summary.json`：25 条记录同时缺少主题和正文，21 次文本部分
解码使用未知字符集的 UTF-8 安全回退。异常均以告警保留，不中断数据集处理。

步骤4已通过 `scripts\prepare_clean_dataset.py` 完成。所有记录均生成
`feature_version=text-v1` 的 `model_text`，统一上限为 20,000 字符；邮箱、URL、长数字
分别替换为 `<EMAIL>`、`<URL>`、`<NUMBER>`。清洗统计见
`data/manifests/clean_summary.json`，并已验证无超长文本、重复 ID 或未替换的邮箱/URL。

步骤5已通过 `scripts\deduplicate_dataset.py` 完成。11,333 条清洗记录中保留 7,257 条，
其中 `phishing` 为 3,121 条、`legitimate` 为 4,136 条；181 条原始哈希重复和 3,895 条
规范文本重复已删除。每条保留记录均写入 `dedup_group`，步骤6不得将同一组拆分到不同
数据集。详见 `data/manifests/dedup_report.json`。SimHash 审计得到 3,847 对近重复候选，
仅作风险记录而不自动删除；此外有 1 条空 `model_text` 留待步骤6按可训练性规则剔除。

去重后的钓鱼样本为 3,121 条，低于正式第一版每类 4,000--5,000 条的目标。不能通过
保留重复样本凑数；后续应补充独立公开钓鱼语料，并在实验报告中记录当前样本量限制。

## 补充语料轮次记录（2026-09-01）

为解决上述 phishing 样本不足，本轮从 Zenodo 8339691 下载并登记了四份公开 CSV：
`Nigerian_5.csv`、`Nigerian_Fraud.csv`、`Nazario.csv` 和 `SpamAssasin.csv`。标签映射、
下载地址、SHA-256 和本地路径见 `data/manifests/sources.csv`；原始文件位于
`data/raw/supplemental_zenodo/`，不提交 Git。

补充文件经 `scripts\\prepare_supplemental_dataset.py` 生成 17,037 条 `text-v1` 记录，
其中 `phishing` 8,229 条、`legitimate` 7,090 条、`spam_other` 1,718 条。与旧数据
联合执行 `scripts\\deduplicate_dataset.py` 后保留 17,844 条：`phishing` 7,913 条、
`legitimate` 8,236 条、`spam_other` 1,695 条；二分类合计 16,149 条，已达到万级目标。
（其中部分补充记录与旧语料重复，最终以联合去重报告为准。）

补充语料的完整处理统计见 `data/manifests/supplemental_summary.json` 和
`data/manifests/dedup_combined_report.json`。`spam_other` 保留为硬负样本，不进入第一版
二分类训练；Zenodo 整理集的原始来源可能与现有 Nazario/SpamAssassin 重叠，步骤6仍需
按 `dedup_group` 分层划分并保留来源分布，避免随机切分造成模板泄漏。

步骤6已通过 `scripts\\split_dataset.py` 完成。脚本剔除 1 条空 `model_text`，将 1,611
条二分类记录作为来源-标签均衡的 `cross_source_test`，其余 14,537 条按标签以 70/15/15
划分为 train/valid/test；`spam_other` 1,695 条单独输出为硬负样本。主数据集标签为
`legitimate` 7,414、`phishing` 7,123，所有 split 的 `dedup_group` 均无交叉。结果和
限制见 `data/manifests/split_summary.json`。

步骤7已通过 `scripts\\train_model.py` 完成。脚本只在 train 集（10,175 条）拟合固定的
TF-IDF + Logistic Regression Pipeline，并为 valid/test 各 2,181 条记录生成预测。模型
版本为 `v1.0.0`，特征版本为 `text-v1`，类别顺序校验为 `[legitimate, phishing]`，
第二列概率定义为 phishing 概率。模型产物位于被 Git 忽略的
`models/phishing_model.joblib`，训练元数据见 `data/manifests/model_training_summary.json`。

步骤8已通过 `scripts\\evaluate_model.py` 完成。valid 集在 0.30--0.70 范围内以 0.01
步长调参，得到诊断阈值 0.44；由于共享契约固定 `result_label` 阈值为 0.50，生产结果
仍使用 0.50，本轮报告同时输出 contract/tuned 两套指标。测试集（2,181 条）在阈值选择
后一次性评估，contract 指标为 Precision=0.9924、Recall=0.9766、F1=0.9844、
Accuracy=0.9849，混淆矩阵为 `[[1104,8],[25,1044]]`。跨来源测试集（1,611 条）
contract F1=0.9841。验证集诊断阈值 0.44 在测试集上的 F1=0.9850，但未改变生产契约阈值。
错误样本和分来源指标见 `data/manifests/model_evaluation_summary.json`；
`spam_other` 硬负样本在 contract 阈值下的 phishing 命中率为 32.27%，提示普通垃圾邮件
与钓鱼邮件之间仍存在明显混淆风险。

步骤9已通过 `scripts\\generate_model_metadata.py` 完成。生成的
`models/model_meta.json` 与共享 `ModelMetadata` 字段兼容，并额外记录数据版本、联合
去重报告 SHA-256、模型文件 SHA-256、依赖版本、训练参数、样本数量、测试/跨来源指标和
混淆矩阵。实验记录已写入 `docs/experiments.csv`，实验 ID 为
`v1.0.0-ds-20260901-baf7f3a6`。模型二进制仍不提交 Git，成员3可据此校验模型文件完整性
并映射 `MODEL_NOT_READY`。

### 步骤8补充实验：错误样本与额外测试语料（2026-09-01）

为避免只依据单一随机测试集判断模型能力，本轮新增两类离线实验：

1. `scripts\\analyze_error_samples.py` 读取 `evaluation_predictions.csv`，并合并
   `emails.csv` 与 `cross_source_test.jsonl` 的结构字段。输出只保留样本 ID、来源、标签、
   错误类型、长度、占位符计数、字符集标记和概率区间，不写入主题、正文、邮箱、URL 或附件
   内容。共分析 58 个错误，其中 false negative 41 个、false positive 17 个；跨来源测试
   集贡献 25 个错误。错误主要集中在短文本（28/58）和含非 ASCII 字符样本（18/58），说明
   短正文、语言差异和格式噪声是后续特征增强的优先方向。全局高权重词同时出现 `account`、
   `payment`、`click` 等钓鱼信号，以及年份、列表和引用格式等正常邮件信号，提示模型仍可能
   学到来源/年代模板特征。
2. `scripts\\run_extra_evaluation.py` 使用未参与训练的 Ling.csv 作为 `spam_other` 硬负
   样本，并使用 12 条安全人工边界样本测试中文、紧急通知、账户验证和正常通知场景。Ling
   共 2,859 条（其中 `spam_other` 458 条），精确指纹重叠为 0；在 0.50 阈值下 120 条被判为 phishing，整体命中率 4.20%，其中 `spam_other` 被判为 phishing 的比例为 17.25%，
   平均 phishing 概率 0.1862，最高概率 0.8321。人工边界样本准确率、Precision、Recall
   和 F1 均为 0.8333，混淆矩阵为 `[[5,1],[1,5]]`。人工样本仅用于回归和边界诊断，不计入
   训练或正式模型指标。

实验产物：`data/manifests/error_analysis_summary.json`、
`data/manifests/extra_evaluation_summary.json` 为可提交的非敏感摘要；对应明细预测和结构
分析 CSV 位于 `data/processed/`，按 `.gitignore` 保持本地。Ling 的原始文件、大小、
SHA-256、标签映射和许可信息已登记在 `data/manifests/sources.csv`。

### 当前模型能力评估（v1.0.0）

当前模型是基于 `text-v1` 的 TF-IDF + Logistic Regression 二分类基线，生产阈值为 0.50，
类别顺序为 `[legitimate, phishing]`。在主测试集 2,181 条上，Precision=0.9924、
Recall=0.9766、F1=0.9844、Accuracy=0.9849，混淆矩阵为 `[[1104,8],[25,1044]]`；
跨来源测试集 F1=0.9841。由此可认为模型已经具备课程原型所需的离线基线能力：对当前语料
分布中的钓鱼/正常邮件有较强区分能力，且误报和漏报数量均较低。

上述结论不能外推为真实生产环境的安全保证。第一，数据仍以英文公开历史语料为主，测试集
与训练集存在相同来源和相近年代，可能残留来源或模板特征。第二，`spam_other` 外部硬负样本
共 2,859 条，其中 458 条为普通 spam；其 phishing 判定率为 17.25%，说明模型对“促销、
群发、账户/支付相关但非钓鱼”的邮件仍有明显混淆。第三，人工边界样本只有 12 条，F1=0.8333，
只能作为安全回归信号，不能替代大规模独立测试。第四，错误分析发现 58 个错误中有 41 个
false negative，且 28 个错误属于短文本，表明简短、信息不足或语言/格式异常邮件仍是主要
薄弱场景。因此当前模型适合“疑似风险提示”和课程演示，不适合作为唯一拦截依据。

### 已完成实验总结

- 数据工程：完成公开来源登记、标签统一、文本清洗、精确/规范文本去重、按去重组划分和
  训练-验证-测试防泄漏检查；原始数据和明细处理文件保持本地忽略。
- 基线训练：完成固定 Pipeline、训练日志、模型元数据、版本号、数据版本和 SHA-256 记录。
- 阈值实验：在验证集扫描 0.30--0.70，诊断最优阈值为 0.44；为遵循共享契约，生产仍固定
  使用 0.50，并保留 tuned 结果用于分析。
- 错误分析：完成主测试集和跨来源测试集错误类型、来源、长度、占位符、非 ASCII 和全局
  特征权重统计，不输出邮件正文或真实地址。
- 额外评估：完成 Ling 外部硬负样本和 12 条 `example.invalid` 人工边界样本测试，记录精确
  重叠数、预测明细和非敏感摘要。

### 后续实验设计与模型优化方向

1. **分层独立评估**：新增完全未参与训练的来源，并按来源、语言、年份、正文长度、是否
   multipart、是否含 URL/附件元数据分层报告 Precision、Recall、F1、误报率和漏报率；测试
   集只在方案冻结后使用一次。
2. **硬负样本专项**：扩大普通 spam、营销通知、订阅邮件和安全但含账户词邮件，分别计算
   `spam_other` 与 legitimate 的误报率；评估 class weight、阈值和三分类方案
   (`legitimate`/`spam_other`/`phishing`) 对误报的影响。
3. **时间与来源切分**：按时间或来源留出整组测试，避免同一模板或同一数据集同时出现在训练
   和测试中，量化跨年代、跨来源泛化差异。
4. **特征增强对照实验**：在保持当前文本基线可回退的前提下，对比 word/character n-gram、
   主题与正文分开权重、语言标记、邮件结构统计和静态 URL/发件人关系特征；每次只改变一类
   因素，并记录数据版本、随机种子和指标。
5. **错误驱动补数**：优先补充 41 个漏报对应的短文本、中文/非 ASCII、伪装链接和异常格式
   场景；对 17 个误报重点补充普通 spam 与正常账户通知，避免只增加容易样本。
6. **概率和阈值校准**：使用独立校准集比较 Platt/等距回归或简单阈值策略，报告 PR-AUC、
   ROC-AUC、Brier score 和不同风险等级下的召回/误报权衡，不直接用测试集调参。
7. **稳健性与安全回归**：增加空正文、超长正文、编码损坏、重复 URL、HTML 伪装和附件元数据
   样本，确认模型推理不访问 URL、不执行附件，并持续验证 HTML 转义和敏感信息不落盘。

后续模型版本只有在独立来源评估、硬负样本误报分析和可复现实验记录齐全后，才考虑替换
`v1.0.0`；否则继续将其作为稳定基线。

## 1. 目标与边界

### 1.1 总目标

建立一条可重复执行的离线流程：

```text
公开数据/脱敏样本
  -> 原始数据登记
  -> MIME/文本统一解析
  -> 标签统一、脱敏、去重
  -> 防泄漏数据划分
  -> TF-IDF + Logistic Regression 训练
  -> 指标与错误样本分析
  -> 保存 Pipeline 和模型元数据
  -> 提供 ModelPredictor 推理接口
```

### 1.2 工作边界

- 只处理邮件原文和静态文本，不访问 URL。
- 不下载、解压、执行或渲染附件。
- 公开数据只用于课程项目和离线实验，遵守原始许可证。
- 原始数据、真实私人邮件和未脱敏内容不得提交 Git。
- 第一版模型只使用 `subject + text_body`，不把 URL 黑名单状态、附件二进制或数据库字段送入模型。
- 模型输出必须遵守共享契约：`phishing_probability` 范围为 `0~1`，标签阈值为 `0.50`，标签顺序为 `[legitimate, phishing]`。

## 2. 依赖与对接约束

### 2.1 可独立推进的内容

- 数据源选择和下载说明；
- 原始数据目录、manifest 和哈希记录；
- 数据清洗、脱敏、去重和切分脚本；
- 基线模型训练、评估和错误分析；
- Pipeline、元数据和实验记录生成。

### 2.2 必须对接但不阻塞前期工作的内容

| 对接成员 | 对接内容 | 最晚确认点 |
|---|---|---|
| 成员2 | `ParsedEmail.subject`、`ParsedEmail.text_body` 的实际语义；HTML 转纯文本方式 | 训练/推理共用文本构造函数前 |
| 成员2 | 空正文、乱码、损坏 MIME 的处理和 `parse_warnings` | 推理边界测试前 |
| 成员3 | `ModelPredictor` 放置路径、初始化方式、模型未就绪异常映射 | 模型交付前 |
| 成员3 | 模型路径和最大文本长度的配置位置 | 集成测试前 |
| 成员4 | 模型版本、概率和标签展示字段 | 页面联调前 |

### 2.3 不能自行修改的共享语义

以下内容如需变化，必须先走契约变更流程，不得在成员1内部悄悄改名或改含义：

- `ModelInput`、`ModelPrediction`、`ModelMetadata` 字段；
- `feature_version = text-v1`；
- `result_label` 的二分类语义和 `0.50` 阈值；
- 默认模型文件名；
- `DetectionResult` 中的概率和模型版本含义。

## 3. 数据源与标签方案

### 3.1 推荐数据组合

| 数据用途 | 首选来源 | 内部标签 | 备注 |
|---|---|---|---|
| 钓鱼正样本 | Nazario Phishing Corpus | `phishing` | 主要正样本来源，保留原始来源标识 |
| 钓鱼补充样本 | Phishing Pot 或其他明确标注的公开钓鱼 EML | `phishing` | 作为跨来源测试或补充训练 |
| 正常样本 | Enron Email Dataset | `legitimate` | 抽样时注意邮件线程和重复模板 |
| 正常样本补充 | SpamAssassin `ham` | `legitimate` | 只使用明确的 ham |
| 普通垃圾邮件 | TREC Spam Corpus 等 | `spam_other` | 默认不并入二分类训练，作为硬负样本测试 |
| 演示和边界样本 | 人工构造、使用 `example.invalid` 域名 | `demo_phishing`/`demo_legitimate` | 不用于正式指标，单独存放 |

### 3.2 标签原则

清洗中间数据允许保留三类标签：

```text
phishing
legitimate
spam_other
```

训练第一版二分类模型时只使用 `phishing` 和 `legitimate`。`spam_other` 进入独立硬负样本评估，避免把普通广告垃圾邮件误当作正常邮件。

### 3.3 第一版数据量目标

首版建议达到：

- **第一版模型目标：** 8000--10000 封去重后的二分类邮件，其中 `phishing` 和 `legitimate` 各约 4000--5000 封；
- `spam_other`：至少 500 封独立硬负样本，仅用于补充评估，不并入第一版二分类训练；
- 中文和人工边界样本：20--50 封，单独用于演示和回归测试，不作为正式测试指标的唯一依据。

为尽早完成端到端 MVP，允许先使用 2000--3000 封去重后的二分类样本验证数据处理、训练和推理链路；该小规模模型不得替代第一版正式基线。若公开数据不足以达到第一版目标，必须在 `data/README.md` 和实验记录中注明样本量限制、类别分布和对泛化能力的影响，不能伪造指标。

## 4. 分步骤执行计划

## 步骤1：确认环境、契约和任务边界

### 输入

- `AGENTS.md`；
- `docs/shared-contract.md`；
- 当前 Python 和依赖环境。

### 操作

1. 阅读 `ModelInput`、`ModelPrediction`、`ModelMetadata` 定义。
2. 确认模型输入只有 `subject`、`text_body`、`model_text`、`feature_version`。
3. 确认标签顺序 `[legitimate, phishing]` 和概率阈值 `0.50`。
4. 确认模型默认产物路径和错误语义 `MODEL_NOT_READY`。
5. 建立成员1任务清单，并通知成员2、成员3即将采用的文本清洗和截断配置。

### 产物

- 本计划书；
- 成员间确认记录；
- 待确认问题清单。

### 验收条件

- 能明确解释训练输入、模型输出和不能送入模型的数据；
- 没有新增与共享契约冲突的字段定义。

## 步骤2：建立数据目录和来源登记机制

### 操作

1. 使用以下目录：

```text
data/raw/              # 原始下载数据，不提交 Git
data/processed/        # 清洗后的 CSV/JSONL
data/samples/          # 脱敏演示样本
data/manifests/        # 来源、哈希和数量清单
models/                # Pipeline 和元数据
```

2. 编写或完善 `data/README.md`，记录每个数据源的：名称、来源、许可证、下载日期、文件名、SHA-256、原始样本数、采用标签和已知限制。
3. 为每个原始文件生成 SHA-256，禁止使用本地绝对路径作为数据标识。
4. 检查 `.gitignore`，确保原始邮件、数据库、日志和大型模型文件按团队约定处理。

### 建议 manifest 字段

```text
source
source_file
downloaded_at
license
sha256
raw_count
parseable_count
label_mapping
notes
```

### 产物

- `data/README.md`；
- `data/manifests/sources.csv`；
- 原始文件校验哈希记录。

### 验收条件

- 任意成员能根据 manifest 知道数据从哪里来、何时下载、如何重建；
- 仓库中没有真实私密邮件或未脱敏原始数据。

## 步骤3：统一读取邮件和非邮件数据格式

### 操作

1. 对 `.eml` 使用 Python `email` 标准库读取；
2. 对 mbox 使用 `mailbox.mbox` 遍历；
3. 对 maildir 使用 `mailbox.Maildir` 遍历；
4. 不依赖 Web 服务，不访问邮件中的 URL；
5. 解析失败的样本记录失败原因，不直接静默丢弃；
6. 优先复用成员2的纯函数解析器；在其尚未完成时，可使用成员1临时适配器，但最终字段必须映射到 `ParsedEmail` 语义。

### 中间记录格式

```json
{
  "id": "source-000001",
  "source": "nazario",
  "subject": "...",
  "text_body": "...",
  "parse_warnings": [],
  "source_hash": "sha256...",
  "label": "phishing"
}
```

### 产物

- 统一读取模块；
- 解析失败清单；
- 未清洗中间 JSONL。

### 验收条件

- 能处理纯文本、HTML、multipart、中文主题和损坏 MIME；
- 单封邮件解析失败不会导致整个数据集处理中断；
- 不执行附件、不解压附件、不发起网络请求。

## 步骤4：构造统一文本和清洗规则

### 固定文本契约

```python
model_text = f"{subject}\n{text_body}"[:MODEL_TEXT_MAX_CHARS]
feature_version = "text-v1"
```

首版建议将 `MODEL_TEXT_MAX_CHARS` 固定为 `20000`，并在训练配置、模型元数据和推理配置中使用同一值。

### 清洗顺序

1. 解码主题和正文；
2. HTML 正文转安全可见文本，去除 `script`、`style` 和标签；
3. 统一换行和空白；
4. 邮箱地址替换为 `<EMAIL>`；
5. URL 采用一种策略并固定：保留结构，或替换为 `<URL>`；
6. 对长数字、随机追踪参数做适度归一化；
7. 截断单封 `model_text`；
8. 记录清洗警告和原始长度/清洗后长度。

### 禁止事项

- 不把 HTML 标签本身作为主要语义输入；
- 不把附件二进制、附件内容哈希、服务器路径、数据库 ID 或运行时黑名单状态放入 `model_text`；
- 不使用会访问 URL 的清洗库或在线服务。

### 产物

- `src/detection/text_features.py` 或等价共享模块；
- 清洗后的 `data/processed/emails.csv`；
- 清洗统计报告。

### 验收条件

- 相同主题和正文在训练、验证、测试、在线推理中生成完全一致的 `model_text`；
- 空主题但正文有效、主题有效但正文为空的样本可以处理；
- 清洗不产生 HTML 注入或外联行为。

## 步骤5：去重和数据泄漏检查

### 操作

1. 对原始邮件内容计算 `source_hash`；
2. 删除完全重复样本；
3. 对规范化后的主题+正文进行近重复检查；
4. 对同一邮件线程、同一批模板或同一发件人批量样本进行分组；
5. 在划分数据集之前完成去重和分组；
6. 输出重复数量、近重复数量和按来源统计。

### 推荐字段

```text
source_hash
content_fingerprint
thread_group
sender_group
```

### 产物

- 去重后的中间数据；
- `data/manifests/dedup_report.json`；
- 泄漏检查报告。

### 验收条件

- 相同 `source_hash` 不出现在多个 split；
- 明显相同模板不会同时进入训练和测试；
- 报告中明确说明无法识别的近重复风险。

## 步骤6：标签清洗和数据划分

### 操作

1. 校验标签只能来自允许集合；
2. 删除无法可靠判定标签的样本，记录删除原因；
3. 对 `phishing` 和 `legitimate` 做分层划分；
4. 默认划分为 train/valid/test = 70%/15%/15%；
5. 额外保留跨来源测试集和 `spam_other` 硬负样本集；
6. 固定 `random_state=42`；
7. 检查每个 split 的来源分布、标签分布、语言分布和平均文本长度。

### 推荐输出字段

```text
id, source, label, subject, body, raw_text, source_hash, split
```

项目契约使用 `text_body`，详细方案中的 CSV 示例使用 `body`。为避免歧义，建议清洗内部同时保留 `body` 和 `text_body`，其中二者内容必须相同，并在训练脚本中明确使用 `text_body`。

### 产物

- `data/processed/emails.csv`；
- `data/processed/split_summary.json`；
- 标签映射和删除清单。

### 验收条件

- 训练集、验证集、测试集数量和类别比例可复现；
- TF-IDF 只在训练集上拟合；
- 测试集不参与任何参数选择。

## 步骤7：训练 TF-IDF + Logistic Regression 基线

### 固定基线配置

```python
Pipeline([
    ("tfidf", TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        min_df=2,
        max_features=50000,
        sublinear_tf=True,
    )),
    ("classifier", LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        random_state=42,
    )),
])
```

### 操作

1. 读取 `split=train` 的 `model_text` 和标签；
2. 拟合完整 Pipeline；
3. 在 valid 上进行有限调参或阈值观察；
4. 测试集只在配置冻结后评估一次；
5. 输出预测标签、概率和样本 ID；
6. 检查分类器的类别顺序是否为 `[legitimate, phishing]`；
7. 检查 `predict_proba` 的第二列是否对应 `phishing`。

### 产物

- `models/phishing_model.joblib`；
- 训练日志；
- valid/test 预测结果。

### 验收条件

- Pipeline 可独立重新加载；
- 重新加载后对同一输入的概率和标签一致；
- 不使用未经校准的 `decision_function` 值冒充概率。

## 步骤8：模型评估与错误分析

### 必须输出

- Precision；
- Recall；
- F1；
- Accuracy（辅助）；
- 混淆矩阵；
- 按来源和标签的分组指标；
- 误报（FP）样本 CSV；
- 漏报（FN）样本 CSV。

### 分析维度

1. 是否存在来源偏差；
2. 是否把普通垃圾邮件误判为钓鱼；
3. 是否因英文训练语料导致中文样本效果不稳定；
4. 是否有模板泄漏或标签错误；
5. 模型与规则结论不一致的样本有哪些共同特征。

### 产物

- `models/metrics.json` 或并入 `model_meta.json`；
- `data/processed/error_samples.csv`；
- `docs/experiments.csv`；
- 简短错误分析说明。

### 验收条件

- 指标均来自真实运行结果；
- 混淆矩阵总数与测试集数量一致；
- 每个结论都能追溯到样本或统计，不用单一 accuracy 宣称模型可靠。

## 步骤9：生成模型元数据和版本记录

### 最低元数据

```json
{
  "model_name": "tfidf_logistic_regression",
  "model_version": "v1.0.0",
  "feature_version": "text-v1",
  "trained_at": "2026-09-01T00:00:00Z",
  "label_order": ["legitimate", "phishing"],
  "dataset_version": "ds-YYYYMMDD",
  "random_state": 42,
  "train_count": 0,
  "valid_count": 0,
  "test_count": 0,
  "max_text_chars": 20000,
  "features": ["subject", "text_body", "tfidf_word_ngram_1_2"],
  "metrics": {},
  "artifact_filename": "phishing_model.joblib",
  "metadata_filename": "model_meta.json"
}
```

### 操作

1. 用 UTC ISO 8601 记录训练时间；
2. 记录数据版本、随机种子、依赖版本和全部训练参数；
3. 记录模型文件 SHA-256；
4. 确认元数据字段与 `ModelMetadata` 兼容；
5. 版本号与实验记录绑定，不覆盖已发布模型而不留记录。

### 产物

- `models/model_meta.json`；
- 模型文件校验哈希；
- `docs/experiments.csv` 新增实验记录。

### 验收条件

- 只看元数据即可追溯模型由哪份数据、哪套配置训练得到；
- 元数据不存在、损坏或版本不匹配时，成员3可以映射为 `MODEL_NOT_READY`。

## 步骤10：实现 ModelPredictor 推理接口

### 接口要求

```python
class ModelPredictor:
    def predict(self, model_input: ModelInput) -> ModelPrediction:
        ...
```

### 操作

1. 启动时加载完整 Pipeline 和元数据；
2. 校验模型版本、特征版本、标签顺序和文件完整性；
3. 使用与训练相同的文本构造和截断逻辑；
4. 调用 `predict_proba`；
5. 将 phishing 对应概率转换为 `ModelPrediction`；
6. 使用共享函数根据概率生成 `result_label`；
7. 模型缺失或加载失败时抛出项目约定错误，不在运行期临时训练。

### 产物

- `src/detection/model_predictor.py`；
- `tests/test_model_predictor.py`；
- 与成员3的接入说明。

步骤10已完成。`ModelPredictor` 默认加载 `models/phishing_model.joblib` 和
`models/model_meta.json`，启动时校验元数据完整性、`text-v1` 特征版本、
`[legitimate, phishing]` 标签顺序、artifact SHA-256 和 Pipeline 的 `classes_`。
推理时优先从 `subject` 与 `text_body` 重建标准 `model_text`；当两者均为空时允许使用
调用方提供的预构造 `model_text`。模型缺失、损坏、哈希不一致或结构不兼容统一抛出
`DomainError(ErrorCode.MODEL_NOT_READY, ..., 503)`，绝不在运行期临时训练或访问网络。
输入特征版本不匹配会明确拒绝，输出通过 `validate_model_prediction()` 校验。

### 验收条件

- 输出满足 `validate_model_prediction()`；
- `feature_version` 和 `model_version` 与元数据完全一致；
- 空文本、中文文本、超长文本和模型缺失均有明确行为。

## 步骤11：与成员2、成员3完成集成验证

### 与成员2验证

- 解析器输出的 `subject` 与 `text_body` 可直接构造 `ModelInput`；
- HTML 邮件不会把标签作为模型主体文本；
- 解析警告不会阻塞模型推理，除非服务层判定为解析失败。

### 与成员3验证

- 后端可以加载 `ModelPredictor`；
- 模型路径来自配置，不写死绝对路径；
- 模型未就绪返回 `503 MODEL_NOT_READY`；
- 后端融合模型概率时使用共享评分函数，不重复计算概率。

### 与成员4验证

- 前端使用 `result_label`、`model_probability`、`model_version` 展示；
- 概率、标签和风险等级不混为同一概念；
- 页面使用“疑似”“风险提示”等措辞。

### 产物

- 集成测试记录；
- 字段映射说明；
- 问题清单和修复记录。

### 验收条件

- 使用一封正常样本和一封钓鱼样本完成端到端推理；
- 结果可被服务层校验并写入 `DetectionResult`；
- 模型不访问网络、不处理附件内容。

## 步骤12：冻结成员1交付版本

### 交付清单

- `scripts/download_datasets.py` 或等价下载说明；
- `scripts/prepare_dataset.py`；
- `scripts/train_model.py`；
- `src/detection/text_features.py`；
- `src/detection/model_predictor.py`；
- `data/README.md`；
- `data/manifests/sources.csv`；
- `data/processed/emails.csv`（按仓库隐私规则处理）；
- `models/phishing_model.joblib`；
- `models/model_meta.json`；
- `docs/experiments.csv`；
- 误报漏报样本及分析说明；
- 成员3接入说明和测试命令。

### 最终验收命令

```powershell
pytest -q
python scripts\prepare_dataset.py
python scripts\train_model.py
```

### 发布前检查

- [ ] 原始数据未进入 Git；
- [ ] 数据来源、许可证和哈希已登记；
- [ ] 去重和数据泄漏检查已完成；
- [ ] TF-IDF 只在训练集拟合；
- [ ] 指标、混淆矩阵和错误样本已生成；
- [ ] Pipeline 和元数据可以重新加载；
- [ ] 标签顺序是 `[legitimate, phishing]`；
- [ ] 概率范围和阈值符合契约；
- [x] `feature_version` 为 `text-v1`；
- [ ] 推理不访问 URL、不执行或解压附件；
- [ ] 成员2、成员3已确认字段映射；
- [ ] 模型版本和数据版本已固定。

## 5. 风险与处理策略

| 风险 | 影响 | 处理 |
|---|---|---|
| 正常样本不足 | 误报率高 | 增加 Enron/SpamAssassin ham，保留来源分组指标 |
| 普通 spam 被误标 legitimate | 标签污染 | 保留 `spam_other`，独立作为硬负样本 |
| 数据模板重复 | 测试指标虚高 | 按 hash、模板、线程和来源分组去重 |
| 英文样本占比过高 | 中文演示不稳定 | 单独加入中文人工样本，降低结论强度 |
| URL/邮箱信息泄漏来源 | 模型学习数据集指纹 | 脱敏并做跨来源测试 |
| 公开数据许可证不清 | 无法合规提交 | 只提交下载说明和哈希，不提交原始内容 |
| 模型概率与标签顺序错位 | 线上结果反转 | 训练和推理阶段显式校验 `classes_` 与第二列概率 |
| 训练和推理清洗不一致 | 预测不可复现 | 复用同一文本构造函数和配置 |
| 模型文件缺失或损坏 | API 无法检测 | 明确返回 `MODEL_NOT_READY`，禁止临时兜底 |

## 6. 完成定义

成员1工作只有同时满足以下条件才算完成：

1. 数据来源可追溯，标签规则有书面说明；
2. 清洗和划分脚本可重复执行；
3. 数据泄漏、重复和隐私检查有结果记录；
4. 基线 Pipeline 已训练并可重新加载；
5. Precision、Recall、F1、混淆矩阵和错误样本已生成；
6. `model_meta.json` 能追溯数据版本、参数、指标和模型版本；
7. `ModelPredictor` 输出符合共享契约；
8. 成员3能在无额外临时逻辑的情况下接入模型；
9. 正常、钓鱼、中文、空正文、超长文本和模型缺失测试均通过；
10. 计划中的安全边界没有被任何脚本或依赖破坏。
