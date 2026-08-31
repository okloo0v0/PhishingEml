# PhishingEml 阶段 A 共享契约

## 1. 契约状态

| 项目 | 值 |
|---|---|
| 契约版本 | v1.1 |
| 生效阶段 | 阶段 A：冻结共享契约 |
| 适用范围 | 解析器、规则引擎、模型、后端、数据库、前端和测试 |
| 变更方式 | 必须经过全组确认，并同步修改代码、文档和测试 |
| 默认时间 | 2026-08-31 |

本文件是跨模块开发的语义基准。实现代码可以增加内部辅助字段，但不能改变本文件中已定义字段的含义、类型、单位和空值约定。

## 2. 模块依赖关系

    全组确认需求和契约
      -> 成员 2 输出 ParsedEmail、ParsedUrl、AttachmentMeta
      -> 成员 1 使用确定的文本字段训练模型
      -> 成员 3 编排解析器、规则引擎、模型和数据库
      -> 成员 4 接入稳定的 API 响应
      -> 全组执行端到端测试

成员 1、3、4 可以提前开发各自的骨架和 Mock，但不能自行定义另一套字段语义。

## 3. 命名和空值约定

- JSON 字段使用 snake_case。
- 枚举值使用小写英文字符串。
- 数量使用非负整数。
- 分数使用浮点数，最终分数单位为 0--100。
- 模型概率使用浮点数，范围为 0--1。
- 缺少的可选字符串使用空字符串或 null，具体以字段表为准。
- 多值字段使用数组，不能用逗号拼接字符串代替。
- 时间统一使用 UTC ISO 8601 字符串；API 输出使用 `Z` 后缀，例如 `2026-08-31T08:30:00Z`。
- 邮件头名称统一转为小写；同名重复头使用换行拼接。
- URL 的 raw_url 保留邮件中的原始字符串，normalized_url 用于匹配和比较。
- 任何展示给用户的邮件内容都视为不可信文本。

## 4. 领域枚举

### RiskLevel

| 值 | 含义 |
|---|---|
| low | 未发现明显风险或风险分数低于 30 |
| medium | 存在可疑特征，风险分数为 30 至 59.9 |
| high | 风险分数大于等于 60 |

### ResultLabel

| 值 | 含义 |
|---|---|
| legitimate | 模型概率低于 0.50 |
| phishing | 模型概率大于等于 0.50 |

ResultLabel 表示模型的二分类判断，RiskLevel 表示规则和模型融合后的风险等级，两者必须分开使用。不能把 medium 风险直接解释成“确认安全”。

### IndicatorType

| 值 | 含义 |
|---|---|
| url | 完整 URL 指标 |
| domain | 注册域名或主机名指标 |

### Severity

| 值 | 含义 |
|---|---|
| info | 信息性提示 |
| warning | 需要用户注意 |
| critical | 高危证据，例如黑名单命中 |

### FeedbackLabel

| 值 | 含义 |
|---|---|
| confirmed_phishing | 用户确认是钓鱼邮件 |
| false_positive | 用户认为系统误报 |
| unsure | 用户无法确认 |

## 5. 解析对象契约

### 5.1 Mailbox

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---|---|
| display_name | string | "" | 邮件头中的显示名 |
| address | string | "" | 标准化后的邮箱地址 |
| domain | string | "" | address 中的小写域名 |
| is_valid | boolean | false | 是否完成基本邮箱格式校验 |

解析失败不代表邮箱一定恶意。is_valid 只表示格式校验结果，不表示域名真实存在或可信。

### 5.2 ParsedUrl

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---|---|
| raw_url | string | 必填 | 邮件中提取到的原始 URL |
| normalized_url | string | 必填 | 用于匹配的规范化 URL |
| display_text | string | "" | HTML 链接可见文本 |
| scheme | string | "" | URL 协议，如 http 或 https |
| host | string | "" | URL 主机名或 IP |
| registrable_domain | string | "" | 可注册域名；无法判断时为空 |
| port | integer/null | null | URL 端口 |
| path | string | "" | URL 路径 |
| query | string | "" | URL 查询字符串，不包含问号 |
| is_https | boolean | false | scheme 是否为 https |
| uses_ip | boolean | false | host 是否为 IP 地址 |
| is_shortener | boolean | false | 是否命中短链接域名词表 |
| suspicious_tokens | string[] | [] | URL 中命中的可疑词 |
| blacklist_hit | boolean | false | 是否命中当前黑名单 |
| blacklist_match_type | BlacklistMatchType/null | null | `exact_url` 或 `registrable_domain` |
| blacklist_indicator_id | integer/null | null | 命中的黑名单条目 ID |
| blacklist_source | BlacklistSource/null | null | 命中条目的来源 |
| blacklist_confidence | number/null | null | 命中条目的置信度，0--1 |

系统只解析 URL 字符串，不访问 URL、不跟踪跳转、不下载页面。

#### URL 规范化规则

规范化只用于静态比较和黑名单匹配，不能改变 `raw_url`。规则按以下顺序执行：

1. 去除首尾空白；缺少 scheme 时仅在字符串符合主机/路径形式时补充 `http://`，并在风险特征中记录 `missing_scheme`；无法解析时保留原文，规范化结果为空。
2. scheme 和 host 转为小写；host 末尾的 `.` 去除。
3. 国际化域名转换为 ASCII Punycode；IPv4 原样规范化，IPv6 保留方括号形式；`localhost` 视为主机名，不计算注册域名。
4. 去掉默认端口（HTTP 80、HTTPS 443）；非默认端口必须保留。
5. 保留 path 和 query 的原有顺序，不对 query 参数排序、不删除参数；去掉 fragment。
6. `normalized_url` 使用解析器重新组合 scheme、authority、path、query；不得触发 DNS、HTTP、TLS 或任何外部请求。
7. `registrable_domain` 使用本地 Public Suffix List（若未引入该依赖，则采用明确记录局限性的保守规则）；IP、localhost、无法判断的主机名为空。

`is_https` 只表示 scheme 是否为 `https`，不表示证书有效或站点可信；`uses_ip` 只表示语法上是否为 IP 地址。

#### 黑名单命中语义

- 先比较规范化后的完整 URL，命中有效 `active` 条目时记录 `exact_url`。
- 未命中完整 URL 时，再比较 `registrable_domain`，命中有效 `active` 条目时记录 `registrable_domain`。
- 精确 URL 优先于注册域名；同一 URL 的同一匹配类型只保留一个命中，重复条目以 ID 最小者为主并记录日志。
- `review` 和 `false_positive` 条目不参与检测命中；它们仍可在黑名单管理接口中展示。
- 命中字段只描述离线数据匹配结果，不代表 URL 当前可访问，也不代表已确认恶意。

### 5.3 AttachmentMeta

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---|---|
| filename | string | 必填 | 邮件声明的附件文件名 |
| mime_type | string | 必填 | MIME 类型 |
| size | integer | 必填 | 附件字节数，只读取元数据 |
| sha256 | string | 必填 | 附件内容哈希；无法读取内容时为空 |
| extension | string | "" | 小写文件扩展名 |
| risk_hints | string[] | [] | 高风险扩展名、双扩展名等提示 |

附件不写入可执行目录，不解压，不执行。risk_hints 不是恶意代码扫描结论。

### 5.4 ParsedEmail

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---|---|
| message_id | string | "" | Message-ID |
| subject | string | "" | 解码后的邮件主题 |
| date | string | "" | Date 原文或规范化字符串 |
| sender | Mailbox | 空对象 | From 地址 |
| reply_to | Mailbox/null | null | Reply-To 地址 |
| return_path | Mailbox/null | null | Return-Path 地址 |
| recipients | Mailbox[] | [] | To 地址列表 |
| cc | Mailbox[] | [] | Cc 地址列表 |
| text_body | string | "" | 纯文本正文 |
| html_body | string | "" | 原始 HTML 正文，只用于解析，不直接渲染 |
| urls | ParsedUrl[] | [] | 正文和 HTML 中提取的 URL |
| attachments | AttachmentMeta[] | [] | 附件元数据 |
| headers | object | {} | 小写邮件头到字符串的映射 |
| parse_warnings | string[] | [] | 编码、MIME 或字段缺失警告 |

解析器必须尽量返回部分结果。单个字段缺失时优先返回空值和 parse_warnings，而不是让整封邮件解析失败。

## 6. 检测对象契约

### 6.1 Explanation

| 字段 | 类型 | 语义 |
|---|---|---|
| code | string | 稳定规则编号，如 R01、R05 |
| title | string | 面向用户的简短标题 |
| detail | string | 规则解释 |
| evidence | string | 命中的邮件证据摘要，必须脱敏和截断 |
| score | number | 此规则贡献的 0--100 分 |
| severity | Severity | info、warning 或 critical |

code 一旦发布不能随意改名。前端可以根据 code 展示样式，但不能根据 title 文本判断业务逻辑。

规则编号、默认分值、严重程度和单封邮件最大计分次数固定如下。规则实现可以增加证据细节，但不得改变编号或默认分值；规则命中应按 code 去重，并受 `max_hits_per_email` 限制。

| code | 含义 | 默认分值 | 严重程度 | 每封邮件最大命中次数 |
|---|---|---:|---|---:|
| R01 | 发件人与 Reply-To 域名不一致 | 15 | warning | 1 |
| R02 | 链接显示信息与真实目标不一致 | 20 | critical | 1 |
| R03 | URL 或注册域名命中黑名单 | 40 | critical | 1 |
| R04 | 正文包含紧迫性诱导语言 | 10 | warning | 1 |
| R05 | 要求提交账号或敏感信息 | 15 | warning | 1 |
| R06 | URL 存在可疑结构特征 | 10 | warning | 1 |
| R07 | 附件类型或文件名存在风险提示 | 20 | critical | 1 |
| R08 | 发件人字段缺失或格式异常 | 5 | info | 1 |
| R09 | 邮件头存在异常或不完整信息 | 10 | warning | 1 |
| R10 | 内容疑似冒充权威品牌 | 10 | warning | 1 |

`rule_score` 是各规则贡献分值去重、限次后求和，再截断到 0--100 的结果。单条规则的 `Explanation.score` 是该规则本次实际贡献值，不得重复累计同一规则的多个证据。规则目录的机器可读版本位于 `src/domain/rule_contract.py`。

### 6.2 DetectionResult

| 字段 | 类型 | 语义 |
|---|---|---|
| detection_id | integer/null | 数据库检测记录 ID |
| result_label | ResultLabel | 模型二分类结果 |
| risk_level | RiskLevel | 融合后的风险等级 |
| model_probability | number | 模型判定为 phishing 的概率，0--1 |
| rule_score | number | 规则引擎总分，0--100 |
| final_score | number | 融合总分，0--100 |
| model_version | string | 模型版本，例如 v1.0.0 |
| explanations | Explanation[] | 主要风险证据 |
| urls | ParsedUrl[] | URL 静态分析结果 |
| attachments | AttachmentMeta[] | 附件元数据 |
| advice | string[] | 面向用户的处理建议 |
| parse_warnings | string[] | 解析警告 |
| created_at | string/null | 检测时间 |

## 7. 评分契约

默认常量：

    MODEL_WEIGHT = 0.65
    RULE_WEIGHT = 0.35
    LOW_RISK_THRESHOLD = 30.0
    HIGH_RISK_THRESHOLD = 60.0
    MODEL_PHISHING_THRESHOLD = 0.50

计算方式：

    rule_probability = rule_score / 100
    final_score = 100 * (
        0.65 * model_probability
        + 0.35 * rule_probability
    )

final_score 必须限制在 0--100，并保留 1 位小数。模型概率和规则分数超出范围时应先截断到合法范围，同时记录开发日志。

规则分数只用于风险融合和解释，不直接替代模型标签。模型不支持概率输出时，不能把 decision_function 的原始值直接命名为概率。

### 7.1 模型契约

第一版模型固定使用完整的 scikit-learn Pipeline（TF-IDF + Logistic Regression），推理代码只依赖 `ModelPredictor` 接口，不直接操作模型文件。

#### ModelInput

| 字段 | 类型 | 语义 |
|---|---|---|
| subject | string | 解码后的主题，缺失为空 |
| text_body | string | 纯文本正文；HTML 只取安全文本，不把标签作为模型语义 |
| model_text | string | 固定拼接文本，格式为 `subject`、换行、`text_body`；长度按配置截断 |
| feature_version | string | 特征契约版本，第一版为 `text-v1` |

模型输入禁止包含未脱敏的附件二进制、服务器路径、数据库 ID 和运行时黑名单状态。主题和正文的截断规则必须在训练和推理中一致。

#### FeatureVector 与 ModelPrediction

- `FeatureVector.feature_version` 必须与模型元数据一致；`model_text` 是实际送入 Pipeline 的文本；`numeric_features` 仅用于可解释记录，字段名和值必须是有限数值。
- `ModelPrediction.phishing_probability` 是模型对 `phishing` 的概率，范围 0--1；不得把 `decision_function` 原值直接当概率。
- `result_label` 按 `phishing_probability >= 0.50` 得到；`legitimate` 和 `phishing` 的标签顺序固定为 `[legitimate, phishing]`。
- `model_version`、`feature_version` 必须非空，且推理返回值必须与加载的 `ModelMetadata` 完全一致。
- 模型文件默认名为 `models/phishing_model.joblib`，元数据默认名为 `models/model_meta.json`。文件缺失、无法反序列化、版本不一致或指标元数据缺失时，接口返回 `503 MODEL_NOT_READY`，不得使用未声明的临时模型兜底。
- `predict(input)` 只做本地推理，不访问网络；输入为空仍允许推理，但由服务层按照分析输入契约决定是否拒绝请求。

`ModelMetadata` 至少记录 `model_name`、`model_version`、`feature_version`、`trained_at`、`label_order`、训练指标和 artifact 文件名。指标文件必须能追溯数据版本、随机种子、训练/测试样本数量和特征配置。

### 7.2 结果校验

服务层生成 `DetectionResult` 后必须校验：概率和分数为有限值且在范围内；`final_score` 符合本节融合公式；风险等级符合阈值；结果标签符合模型概率。校验失败视为内部契约错误，不得把不一致结果写入数据库或返回前端。

## 8. API 契约

### 8.1 统一响应

成功响应：

    {
      "success": true,
      "data": {},
      "request_id": "uuid"
    }

失败响应：

    {
      "success": false,
      "error": {
        "code": "PARSE_FAILED",
        "message": "邮件无法解析"
      },
      "request_id": "uuid"
    }

所有成功响应的 `data` 只包含契约字段；失败响应不返回堆栈、绝对路径、模型文件路径或原始私密邮件内容。`request_id` 由服务端生成并贯穿日志和响应。

### 8.2 主要接口

| 方法 | 路径 | 请求 | 成功结果 |
|---|---|---|---|
| POST | /api/emails/analyze | multipart/form-data：`file`、`raw_text`、`sample_id` 严格三选一 | DetectionResult |
| GET | /api/detections | page、page_size、risk_level | 分页检测摘要 |
| GET | /api/detections/{id} | 路径 ID | 完整检测详情 |
| DELETE | /api/detections/{id} | 路径 ID | 删除结果 |
| GET | /api/blacklist | keyword、status、page | 黑名单列表 |
| POST | /api/blacklist | indicator、indicator_type、source、note | 黑名单条目 |
| PATCH | /api/blacklist/{id} | status、confidence、note | 更新后的条目 |
| GET | /api/statistics/overview | 可选时间范围 | 看板统计 |
| GET | /api/model/metrics | 无 | 模型元数据和指标 |
| GET | /api/knowledge | keyword、category | 防范知识列表 |
| POST | /api/feedback | detection_id、label、note | 反馈记录 |

### 8.3 分析接口输入规则

#### D-001 决议（已冻结）

`file`、`raw_text`、`sample_id` 是三种互斥输入来源。请求必须且只能提供其中一个；服务端和前端均不得实现隐式优先级或静默忽略任何字段。

| 请求情况 | 响应 |
|---|---|
| 三个字段均未提供 | `400 INPUT_REQUIRED` |
| 两个或三个字段同时提供，即使其中一个为空 | `400 INPUT_CONFLICT` |
| 恰好一个字段提供，但文件为 0 字节、`raw_text` 仅含空白或 `sample_id` 为空白 | `400 EMPTY_INPUT` |
| 恰好提供有效 `file` | 按文件校验和解析流程处理 |
| 恰好提供有效 `raw_text` | 将其作为完整 RFC 822/MIME 邮件原文解析 |
| 恰好提供有效 `sample_id` | 仅从配置的演示样本目录读取，不接受路径或 URL |

补充约束：`file` 只接受 `.eml` 或明确声明的邮件原文，文件大小不超过 5 MiB；`raw_text` 不超过 200000 个 Unicode 字符；未知 `sample_id` 返回 `404 RECORD_NOT_FOUND`；分析过程不允许网络访问、不允许执行、解压或渲染附件。该决议关闭 D-001，后续变更须按第 10 节提交契约修订。

代码层使用 `src/domain/schemas.py` 中的 `AnalysisInput` 表示请求来源，使用 `validate_analysis_input()` 执行上述互斥校验；Web 框架的 `UploadFile`、表单字段和 HTTP 响应对象只能在 API 适配层转换，不得把框架对象传入解析器、规则引擎或模型模块。

### 8.4 HTTP 状态码和错误码

| HTTP | 错误码 | 使用场景 |
|---:|---|---|
| 400 | INPUT_REQUIRED | 没有提供任何输入 |
| 400 | INVALID_FILE_TYPE | 文件类型不支持 |
| 400 | EMPTY_INPUT | 输入为空 |
| 413 | FILE_TOO_LARGE | 文件超过 5 MiB |
| 422 | PARSE_FAILED | 无法完成必要的邮件解析 |
| 422 | BLACKLIST_INVALID | 黑名单指标格式错误 |
| 400 | INPUT_CONFLICT | 分析请求同时提供两个或以上输入来源 |
| 400 | INVALID_PAGINATION | 分页参数越界或组合不合法 |
| 400 | INVALID_FEEDBACK | 反馈字段缺失、枚举值非法或备注超长 |
| 400 | INVALID_DATE_RANGE | 统计时间范围格式错误或起止时间倒置 |
| 404 | RECORD_NOT_FOUND | 检测或黑名单记录不存在 |
| 409 | DUPLICATE_INDICATOR | 黑名单指标已经存在 |
| 503 | MODEL_NOT_READY | 模型文件或元数据未准备好 |
| 500 | INTERNAL_ERROR | 未预期的服务错误 |

`NETWORK_ACCESS_NOT_SUPPORTED` 为内部配置错误或安全策略错误：当 `ALLOW_NETWORK=true` 时应用启动必须拒绝，而不是悄悄忽略配置；如果运行期发现任何网络访问路径，相关操作必须拒绝并记录安全日志。

### 8.5 分页、统计和增强接口响应

- `GET /api/detections` 返回 `HistoryResponse`：`items` 为 `DetectionSummary[]`，`pagination` 包含 `page`（从 1 开始）、`page_size`（1--100）、`total` 和 `total_pages`。空结果的 `total_pages` 为 0，但 `page=1` 仍合法。
- `DetectionSummary` 只返回列表所需摘要，不返回正文、原始 HTML、完整请求头或附件内容。
- `GET /api/blacklist` 返回 `BlacklistItem[]` 和同样的 `Pagination`；`hit_count` 是历史检测中命中该条目的次数，不因停用而清零。
- `GET /api/statistics/overview` 返回 `StatisticsOverview`：风险等级计数、模型标签计数、规则命中计数、附件类型计数和按 UTC 日期聚合的检测数量。无数据时各计数返回空对象或 0，不返回 null。
- `GET /api/model/metrics` 返回 `ModelMetrics`，包括模型/特征版本、训练时间、样本数量、指标和二维混淆矩阵；它是离线评估结果，不代表当前邮件的预测结果。
- `GET /api/knowledge` 返回 `KnowledgeArticle[]`，内容为防范教育材料，不包含可访问的钓鱼链接。
- `POST /api/feedback` 接受 `FeedbackRequest`，`detection_id` 必须存在，`label` 必须为 `confirmed_phishing`、`false_positive` 或 `unsure`，`note` 可空且限制长度；返回 `FeedbackResponse`。反馈只记录人工意见，第一版不自动改写模型。

## 9. 数据库契约

### emails

| 字段 | 类型 | 约束 |
|---|---|---|
| id | integer | 主键 |
| file_hash | varchar(64) | 非空，SHA-256 |
| filename | varchar(255) | 可空 |
| subject | text | 可空或脱敏 |
| sender | text | 可空或脱敏 |
| reply_to | text | 可空或脱敏 |
| text_body | text | 可空，建议限制保存长度 |
| html_body | text | 可空，建议限制保存长度 |
| parse_warnings | text | JSON 字符串 |
| created_at | datetime | 非空 |

### detections

| 字段 | 类型 | 约束 |
|---|---|---|
| id | integer | 主键 |
| email_id | integer | 外键，非空 |
| result_label | varchar(32) | legitimate/phishing |
| risk_level | varchar(16) | low/medium/high |
| model_probability | real | 0--1 |
| rule_score | real | 0--100 |
| final_score | real | 0--100 |
| model_version | varchar(64) | 非空 |
| explanations | text | JSON 字符串 |
| advice | text | JSON 字符串 |
| created_at | datetime | 非空 |

### email_urls

| 字段 | 类型 | 约束 |
|---|---|---|
| id | integer | 主键 |
| email_id | integer | 外键，非空 |
| display_text | text | 可空 |
| raw_url | text | 非空 |
| normalized_url | text | 非空 |
| domain | varchar(255) | 可空 |
| features | text | JSON 字符串 |
| blacklist_hit | boolean | 默认 false |

### attachments

| 字段 | 类型 | 约束 |
|---|---|---|
| id | integer | 主键 |
| email_id | integer | 外键，非空 |
| filename | varchar(255) | 可空 |
| mime_type | varchar(255) | 可空 |
| size | integer | 默认 0 |
| sha256 | varchar(64) | 可空 |
| risk_hints | text | JSON 字符串 |

### blacklist_indicators

| 字段 | 类型 | 约束 |
|---|---|---|
| id | integer | 主键 |
| indicator | varchar(2048) | 非空、唯一 |
| indicator_type | varchar(16) | url/domain |
| source | varchar(64) | manual/import/phishtank |
| status | varchar(32) | active/review/false_positive |
| confidence | real | 0--1，可空 |
| note | text | 可空 |
| created_at | datetime | 非空 |
| updated_at | datetime | 非空 |

### 9.1 数据库序列化和级联

- `emails.sender`、`reply_to` 保存为 Mailbox JSON；邮箱地址在写入展示层前脱敏，数据库不保存密码、认证令牌或真实附件文件。
- `emails.parse_warnings`、`detections.explanations`、`detections.advice`、`email_urls.features`、`attachments.risk_hints` 必须保存为 UTF-8 JSON 数组或对象，禁止用自定义分隔符拼接。
- `headers` 若持久化，使用小写 header 名到字符串的 JSON 对象；敏感头（如认证信息）不得保存或必须脱敏。
- `file_hash` 是邮件内容去重和追踪标识，不作为 `emails` 的唯一约束；同一邮件可以因重复检测产生多条 `detections` 记录。
- 删除 `emails` 时，关联的 `email_urls`、`attachments` 和对应 `detections` 必须级联删除；删除历史检测不得反向删除原始 `emails`，除非明确执行邮件级删除。
- 数据库时间统一保存 UTC，API 序列化为带 `Z` 的 ISO 8601 字符串。
- 所有查询使用参数化 SQL 或 Repository 的参数绑定；黑名单 `indicator` 唯一性按规范化后的指标值和类型共同判断，不能只按展示原文判断。

### 9.2 黑名单字段语义

`indicator_type=url` 时 `indicator` 必须是规范化完整 URL；`indicator_type=domain` 时必须是小写主机名或注册域名，不得包含 scheme、path 或 query。`source` 仅允许 `manual`、`import`、`phishtank`；`status` 仅允许 `active`、`review`、`false_positive`；`confidence` 为空表示来源未提供置信度，非空必须在 0--1。

## 10. 变更规则

以下修改必须提交 Pull Request，并至少由两名相关成员确认：

- 删除或重命名字段；
- 修改字段类型、单位或空值语义；
- 修改评分权重和阈值；
- 修改 API 路径、状态码或错误码；
- 修改数据库外键或黑名单匹配语义；
- 修改“不访问 URL、不执行附件”的安全边界。

配置契约同样属于共享契约：`allow_network`/`ALLOW_NETWORK` 字段保留用于未来隔离沙箱扩展，但当前基础版固定为 `false`。代码在读取到 `ALLOW_NETWORK=true` 时必须拒绝启动，并显示“基础版不实现沙箱隔离，网络访问作为后续隔离沙箱扩展保留”；不得通过把该值静默改回 false 来掩盖配置错误。

兼容性修改优先采用新增字段，禁止在同一版本中让一个字段承载两种含义。

