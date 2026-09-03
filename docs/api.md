# PhishingEml API 文档

> 维护对象：字段语义以 `docs/shared-contract.md` 和 `src/domain/` 为准。
> 本文示例均为**真实返回结构**，前端可据此直接对接。

## 1. 基本信息

- Base URL：`http://127.0.0.1:8000`
- 认证：无（本地课程原型）
- 请求/响应均为 JSON；时间统一 UTC ISO 8601 带 `Z` 后缀
- 交互式文档：`http://127.0.0.1:8000/docs`（Swagger UI）

## 2. 统一响应格式

所有接口成功时：

```json
{ "success": true, "data": {}, "request_id": "uuid" }
```

失败时：

```json
{
  "success": false,
  "error": { "code": "PARSE_FAILED", "message": "邮件无法解析" },
  "request_id": "uuid"
}
```

前端判断逻辑：`success === true` 走 `data`，否则读 `error.code` 和 `error.message` 展示给用户。

## 3. 通用枚举（前端展示/筛选需要）

| 字段             | 取值                                                 | 说明      |
| -------------- | -------------------------------------------------- | ------- |
| result_label   | `legitimate` / `phishing`                          | 模型二分类   |
| risk_level     | `low` / `medium` / `high`                          | 融合后风险等级 |
| severity       | `info` / `warning` / `critical`                    | 规则严重程度  |
| indicator_type | `url` / `domain`                                   | 黑名单类型   |
| source         | `manual` / `import` / `phishtank`                  | 黑名单来源   |
| status         | `active` / `review` / `false_positive`             | 黑名单状态   |
| feedback label | `confirmed_phishing` / `false_positive` / `unsure` | 反馈标签    |

## 4. 错误码

| HTTP | 错误码                 | 场景              |
| ----:| ------------------- | --------------- |
| 400  | INPUT_REQUIRED      | 未提供任何输入         |
| 400  | INPUT_CONFLICT      | 同时提供两个及以上输入来源   |
| 400  | EMPTY_INPUT         | 输入为空（0 字节/空白）   |
| 400  | INVALID_FILE_TYPE   | 文件类型不支持（非 .eml） |
| 400  | INVALID_PAGINATION  | 分页参数越界          |
| 400  | INVALID_FEEDBACK    | 反馈字段非法或备注过长     |
| 400  | VALIDATION_ERROR    | 请求参数校验失败        |
| 404  | RECORD_NOT_FOUND    | 记录或演示样本不存在      |
| 409  | DUPLICATE_INDICATOR | 黑名单指标已存在        |
| 413  | FILE_TOO_LARGE      | 文件超过 5 MiB      |
| 422  | BLACKLIST_INVALID   | 黑名单指标格式错误       |
| 422  | PARSE_FAILED        | 邮件无法解析          |
| 503  | MODEL_NOT_READY     | 模型文件或元数据未准备好    |
| 500  | INTERNAL_ERROR      | 未预期的服务错误        |

## 5. 接口

### 接口总览（共 12 个）

| 方法     | 路径                         | 说明                   |
| ------ | -------------------------- | -------------------- |
| GET    | `/health`                  | 健康检查                 |
| POST   | `/api/emails/analyze`      | 邮件分析（核心，上传/粘贴/样本三选一） |
| GET    | `/api/detections`          | 检测历史列表               |
| GET    | `/api/detections/{id}`     | 检测详情                 |
| DELETE | `/api/detections/{id}`     | 删除检测记录               |
| GET    | `/api/blacklist`           | 黑名单列表                |
| POST   | `/api/blacklist`           | 新增黑名单                |
| PATCH  | `/api/blacklist/{id}`      | 更新黑名单                |
| GET    | `/api/statistics/overview` | 统计总览                 |
| GET    | `/api/model/metrics`       | 模型指标                 |
| GET    | `/api/knowledge`           | 防范知识库                |
| POST   | `/api/feedback`            | 用户反馈                 |

### 5.1 健康检查

`GET /health`

```json
{ "success": true, "data": { "status": "ok" }, "request_id": "uuid" }
```

### 5.2 邮件分析（核心）

`POST /api/emails/analyze`，`multipart/form-data`。`file`、`raw_text`、`sample_id` **严格三选一**。

| 字段        | 类型     | 说明                            |
| --------- | ------ | ----------------------------- |
| file      | file   | `.eml` 文件，≤ 5 MiB             |
| raw_text  | string | 完整 MIME 邮件原文，≤ 200000 字符      |
| sample_id | string | 内置演示样本 ID（来自 `data/samples/`） |

请求示例（curl）：

```bash
curl -F "file=@sample.eml" http://127.0.0.1:8000/api/emails/analyze
curl -F "raw_text=Subject: hi" http://127.0.0.1:8000/api/emails/analyze
```

成功响应 `data`（`DetectionResult`）：

```json
{
  "detection_id": 1,
  "result_label": "phishing",
  "risk_level": "high",
  "model_probability": 0.91,
  "rule_score": 40.0,
  "final_score": 73.2,
  "model_version": "v1.0.0",
  "explanations": [
    {
      "code": "R03",
      "title": "URL 或域名命中黑名单",
      "detail": "邮件中的链接命中黑名单",
      "evidence": "http://bad.example.invalid/login",
      "score": 40.0,
      "severity": "critical"
    }
  ],
  "urls": [
    {
      "raw_url": "http://bad.example.invalid/login",
      "normalized_url": "http://bad.example.invalid/login",
      "display_text": "点击登录",
      "scheme": "http",
      "host": "bad.example.invalid",
      "registrable_domain": "example.invalid",
      "port": null,
      "path": "/login",
      "query": "",
      "is_https": false,
      "uses_ip": false,
      "is_shortener": false,
      "suspicious_tokens": [],
      "blacklist_hit": true,
      "blacklist_match_type": "registrable_domain",
      "blacklist_indicator_id": 1,
      "blacklist_source": "manual",
      "blacklist_confidence": null
    }
  ],
  "attachments": [
    {
      "filename": "notice.pdf.exe",
      "mime_type": "application/octet-stream",
      "size": 120,
      "sha256": "abcd1234",
      "extension": ".exe",
      "risk_hints": ["高风险扩展名", "双扩展名"]
    }
  ],
  "advice": ["该邮件疑似钓鱼，请勿点击链接、回复敏感信息或下载附件"],
  "parse_warnings": [],
  "created_at": "2026-09-01T10:36:04Z"
}
```

> 注：`urls`、`attachments`、`explanations`、`parse_warnings` 无内容时为空数组 `[]`。

### 5.3 检测历史列表

`GET /api/detections?page=1&page_size=20&risk_level=high`

| 参数         | 类型     | 说明                             |
| ---------- | ------ | ------------------------------ |
| page       | int    | 从 1 开始，默认 1                    |
| page_size  | int    | 1--100，默认 20                   |
| risk_level | string | 可选 `low`/`medium`/`high`，省略为全部 |

响应 `data`：

```json
{
  "items": [
    {
      "detection_id": 1,
      "subject": "Account notice",
      "result_label": "phishing",
      "risk_level": "high",
      "final_score": 73.2,
      "url_count": 1,
      "attachment_count": 1,
      "model_version": "v1.0.0",
      "created_at": "2026-09-01T10:36:04Z"
    }
  ],
  "pagination": { "page": 1, "page_size": 20, "total": 1, "total_pages": 1 }
}
```

### 5.4 检测详情

`GET /api/detections/{id}`

响应 `data`：

```json
{
  "detection_id": 1,
  "result_label": "phishing",
  "risk_level": "high",
  "model_probability": 0.91,
  "rule_score": 40.0,
  "final_score": 73.2,
  "model_version": "v1.0.0",
  "explanations": [],
  "advice": [],
  "created_at": "2026-09-01T10:36:04Z",
  "email": {
    "subject": "Account notice",
    "sender": { "display_name": "银行", "address": "a@example.com", "domain": "example.com", "is_valid": true },
    "reply_to": { "display_name": "", "address": "b@other.com", "domain": "other.com", "is_valid": true },
    "text_body": "正文...",
    "html_body": "",
    "filename": "sample.eml",
    "parse_warnings": []
  },
  "urls": [],
  "attachments": []
}
```

> `email.reply_to` 可能为 `null`。`email.sender`、`email.reply_to` 结构同 5.2 里的 Mailbox 对象。

`DELETE /api/detections/{id}` — 删除检测记录，成功返回 `data: {}`；不存在返回 `404 RECORD_NOT_FOUND`。

### 5.5 黑名单

`GET /api/blacklist?keyword=&status=&page=1&page_size=20`

| 参数               | 类型     | 说明                                    |
| ---------------- | ------ | ------------------------------------- |
| keyword          | string | 模糊匹配 indicator                        |
| status           | string | 可选 `active`/`review`/`false_positive` |
| page / page_size | int    | 分页，同 5.3                              |

响应 `data`：

```json
{
  "items": [
    {
      "id": 1,
      "indicator": "bad.example.invalid",
      "indicator_type": "domain",
      "source": "manual",
      "status": "active",
      "confidence": null,
      "note": "",
      "hit_count": 3,
      "created_at": "2026-09-01T10:00:00Z",
      "updated_at": "2026-09-01T10:00:00Z"
    }
  ],
  "pagination": { "page": 1, "page_size": 20, "total": 1, "total_pages": 1 }
}
```

`POST /api/blacklist`（JSON body）：

```json
{ "indicator": "bad.example.invalid", "indicator_type": "domain", "source": "manual", "note": "", "confidence": null }
```

- 成功返回单个 `BlacklistItem`（结构同上）；重复返回 `409 DUPLICATE_INDICATOR`。

`PATCH /api/blacklist/{id}`（JSON body，字段都可选）：

```json
{ "status": "false_positive", "confidence": 0.8, "note": "" }
```

- 成功返回更新后的单个 `BlacklistItem`；记录不存在返回 `404 RECORD_NOT_FOUND`。

### 5.6 统计总览

`GET /api/statistics/overview`

响应 `data`：

```json
{
  "total_detections": 10,
  "risk_counts": { "low": 3, "medium": 4, "high": 3 },
  "result_counts": { "legitimate": 5, "phishing": 5 },
  "rule_hit_counts": { "R03": 2, "R04": 1 },
  "attachment_type_counts": { "application/pdf": 2, "application/octet-stream": 1 },
  "daily_counts": { "2026-09-01": 10 }
}
```

> 无数据时各计数字段为 `0` 或空对象 `{}`，不会是 `null`。

### 5.7 模型指标

`GET /api/model/metrics`

响应 `data`：

```json
{
  "model_name": "tfidf_logistic_regression",
  "model_version": "v1.0.0",
  "feature_version": "text-v1",
  "trained_at": "2026-09-01T10:36:04Z",
  "sample_counts": { "train": 10175, "valid": 2181, "test": 2181 },
  "metrics": {
    "test_precision": 0.9924,
    "test_recall": 0.9766,
    "test_f1": 0.9844,
    "test_accuracy": 0.9849,
    "cross_source_precision": 0.9885,
    "cross_source_recall": 0.9797,
    "cross_source_f1": 0.9841,
    "cross_source_accuracy": 0.9845
  },
  "confusion_matrix": [[1104, 8], [25, 1044]]
}
```

> `confusion_matrix` 为二维数组，行=实际、列=预测，标签顺序 `[legitimate, phishing]`。

### 5.8 知识库

`GET /api/knowledge?keyword=&category=`

| 参数       | 类型     | 说明             |
| -------- | ------ | -------------- |
| keyword  | string | 匹配标题/摘要        |
| category | string | 可选，如 `识别`/`应对` |

响应 `data`（数组）：

```json
[
  {
    "id": 1,
    "category": "识别",
    "title": "如何识别钓鱼邮件",
    "summary": "关注发件人、链接和紧迫性语言",
    "content": "检查发件人域名是否与声称机构一致...",
    "sort_order": 1
  }
]
```

### 5.9 用户反馈

`POST /api/feedback`（JSON body）：

```json
{ "detection_id": 1, "label": "false_positive", "note": "" }
```

- `label`：`confirmed_phishing` / `false_positive` / `unsure`
- `note` 可空，≤ 500 字符
- `detection_id` 不存在返回 `404 RECORD_NOT_FOUND`；`label` 非法返回 `400 INVALID_FEEDBACK`

响应 `data`：

```json
{ "feedback_id": 1, "detection_id": 1, "label": "false_positive", "created_at": "2026-09-01T10:36:04Z" }
```

> 第一版只校验并记录日志，不持久化、不自动重训模型。

## 6. 当前实现状态提示

- 解析器与规则引擎目前为**占位实现**：`rule_score` 恒为 0、`explanations`/`urls`/`attachments` 为空，补充上后才有真实值。
- `model_probability`、`final_score`、`result_label` 来自模型（ `models/phishing_model.joblib` ）。


