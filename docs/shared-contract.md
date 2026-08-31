# PhishingEml 阶段 A 共享契约

## 1. 契约状态

| 项目 | 值 |
|---|---|
| 契约版本 | v1.0 |
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
- 时间统一使用 ISO 8601 字符串；服务端保存带时区时间。
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
| blacklist_match_type | string/null | null | exact_url 或 registrable_domain |

系统只解析 URL 字符串，不访问 URL、不跟踪跳转、不下载页面。

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

### 8.2 主要接口

| 方法 | 路径 | 请求 | 成功结果 |
|---|---|---|---|
| POST | /api/emails/analyze | multipart/form-data：file、raw_text、sample_id 三选一 | DetectionResult |
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

- file、raw_text、sample_id 至少提供一个；
- 优先级为 file，其次 raw_text，最后 sample_id；
- file 只接受 .eml 或明确声明的邮件原文；
- 文件大小不能超过 5 MiB；
- raw_text 不能超过 200000 个字符；
- 分析过程不允许网络访问；
- 分析过程不允许执行附件。

### 8.4 HTTP 状态码和错误码

| HTTP | 错误码 | 使用场景 |
|---:|---|---|
| 400 | INPUT_REQUIRED | 没有提供任何输入 |
| 400 | INVALID_FILE_TYPE | 文件类型不支持 |
| 400 | EMPTY_INPUT | 输入为空 |
| 413 | FILE_TOO_LARGE | 文件超过 5 MiB |
| 422 | PARSE_FAILED | 无法完成必要的邮件解析 |
| 422 | BLACKLIST_INVALID | 黑名单指标格式错误 |
| 404 | RECORD_NOT_FOUND | 检测或黑名单记录不存在 |
| 409 | DUPLICATE_INDICATOR | 黑名单指标已经存在 |
| 503 | MODEL_NOT_READY | 模型文件或元数据未准备好 |
| 500 | INTERNAL_ERROR | 未预期的服务错误 |

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

## 10. 变更规则

以下修改必须提交 Pull Request，并至少由两名相关成员确认：

- 删除或重命名字段；
- 修改字段类型、单位或空值语义；
- 修改评分权重和阈值；
- 修改 API 路径、状态码或错误码；
- 修改数据库外键或黑名单匹配语义；
- 修改“不访问 URL、不执行附件”的安全边界。

兼容性修改优先采用新增字段，禁止在同一版本中让一个字段承载两种含义。

