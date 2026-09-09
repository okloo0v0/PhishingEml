## 一、已完成内容

### 1. 接入 DeepSeek 大模型

新增：

```text
src/detection/deepseek_client.py
```

大模型会读取：

- 邮件主题
- 发件人和 Reply-To
- 正文
- URL 结构特征
- URL 黑名单命中情况
- 附件名称、类型和风险提示
- 解析警告
- 规则得分和规则解释
- 本地模型钓鱼概率

大模型只负责辅助分析，不覆盖原有规则和本地模型结果。

未配置 API Key 时：

```json
{
  "llm_status": "disabled",
  "llm_assessment": null
}
```

调用失败或返回格式错误时，不影响原有检测流程。

---

### 2. 固定大模型输出格式

大模型输出：

```json
{
  "verdict": "legitimate | suspicious | phishing",
  "confidence": 0.93,
  "summary": "邮件风险总结",
  "key_findings": [
    "发现的关键风险证据"
  ],
  "recommendations": [
    "建议采取的措施"
  ],
  "uncertainty": "模型判断限制"
}
```

后端会校验字段、置信度范围和 JSON 格式。

---

### 3. 增加 URL 视觉混淆检测

新增 URL 特征：

```text
lookalike_characters
```

可以识别类似：

```text
g00gle.com
paypa1.com
micr0soft.com
```

视觉混淆会被现有 `R06` 可疑 URL 规则捕获，并在证据中说明。

---

### 4. 自动加入黑名单

对以下高风险 URL 自动加入黑名单：

- 视觉混淆字符
- Punycode 域名
- IP 地址作为主机
- URL 中包含用户信息
- 编码字符
- 多级可疑子域名

自动加入的黑名单字段：

```json
{
  "indicator_type": "url",
  "source": "auto_rule",
  "confidence": 0.82,
  "note": "自动规则命中: lookalike_characters"
}
```

普通的 `http`、`login`、`verify` 等弱特征不会单独触发自动入黑名单。

---

### 5. 增加数据库字段

`detections` 表增加：

```text
llm_assessment TEXT
llm_status VARCHAR(32)
```

旧数据库会在初始化时自动增加字段，不需要删除数据库重建。

---

## 二、后端接口说明

### 1. 分析邮件

```http
POST /api/emails/analyze
```

请求方式支持三选一：

#### 上传文件

```bash
curl.exe -X POST "http://127.0.0.1:8000/api/emails/analyze" ^
  -F "file=@data\samples\suspicious_urgent.eml"
```

#### 粘贴邮件原文

```http
Content-Type: multipart/form-data
```

字段：

```text
raw_text=完整的邮件原文
```

#### 分析演示样本

```text
sample_id=suspicious_urgent
```

三个字段必须且只能传一个。

---

### 2. 成功响应

```json
{
  "success": true,
  "data": {
    "result_label": "phishing",
    "risk_level": "high",
    "model_probability": 0.91,
    "rule_score": 75.0,
    "final_score": 83.2,
    "model_version": "baseline-v1",
    "explanations": [],
    "urls": [],
    "attachments": [],
    "advice": [],
    "parse_warnings": [],
    "llm_status": "ready",
    "llm_assessment": {
      "verdict": "phishing",
      "confidence": 0.94,
      "summary": "该邮件存在多个疑似钓鱼特征。",
      "key_findings": [
        "链接域名疑似使用视觉混淆字符",
        "正文要求验证账号信息"
      ],
      "recommendations": [
        "不要点击链接",
        "不要提交密码或验证码"
      ],
      "uncertainty": "未访问链接页面，仅基于静态邮件内容判断。"
    },
    "detection_id": 12,
    "created_at": "2026-09-08T12:00:00Z"
  },
  "request_id": "..."
}
```

---

### 3. LLM 状态字段

```text
disabled
```

未配置 API Key。

```text
ready
```

DeepSeek 调用成功并返回合法 JSON。

```text
unavailable
```

理论上用于调用失败或返回格式错误的情况。

---

### 4. 查询检测历史

```http
GET /api/detections
```

支持：

```text
page
page_size
risk_level
```

示例：

```http
GET /api/detections?page=1&page_size=20&risk_level=high
```

---

### 5. 查询检测详情

```http
GET /api/detections/{detection_id}
```

详情中包含：

- 原始邮件基本信息
- 规则解释
- URL 静态特征
- 附件元数据
- 本地模型结果
- LLM 评估结果
- 处置建议

---

### 6. 查询黑名单

```http
GET /api/blacklist
```

支持：

```text
keyword
status
page
page_size
```

示例：

```http
GET /api/blacklist?keyword=g00gle.com
```

自动添加的条目会显示：

```json
{
  "indicator_type": "url",
  "source": "auto_rule",
  "status": "active",
  "confidence": 0.77,
  "note": "自动规则命中: lookalike_characters"
}
```

---

### 7. 手工添加黑名单

```http
POST /api/blacklist
```

请求：

```json
{
  "indicator": "https://bad.example.invalid/login",
  "indicator_type": "url",
  "source": "manual",
  "note": "人工确认的恶意链接",
  "confidence": 0.98
}
```

---

### 8. 更新黑名单状态

```http
PATCH /api/blacklist/{indicator_id}
```

请求：

```json
{
  "status": "review",
  "note": "等待人工复核"
}
```

状态包括：

```text
active
review
false_positive
```

---

## 三、前端使用说明

前端分析页面调用：

```javascript
POST /api/emails/analyze
```

主要展示：

```text
result_label       检测标签
risk_level         风险等级
final_score        综合分数
explanations       规则证据
advice             本地处置建议
urls               URL 静态信息
attachments        附件信息
llm_assessment     大模型辅助分析
```

前端新增“智能辅助评估”区域，展示：

- 大模型结论
- 置信度
- 风险摘要
- 关键发现
- 模型建议
- 不确定性说明

所有 LLM 字符串都使用文本节点展示，不直接插入 HTML。

---

## 四、数据库使用说明

### `detections` 表新增字段

```sql
llm_assessment TEXT
llm_status VARCHAR(32)
```

`llm_assessment` 保存 JSON 字符串，例如：

```json
{
  "verdict": "suspicious",
  "confidence": 0.86,
  "summary": "邮件存在可疑链接。",
  "key_findings": [],
  "recommendations": [],
  "uncertainty": ""
}
```

### `blacklist_indicators` 表复用现有字段

自动黑名单不新增表，直接使用已有字段：

```text
indicator
indicator_type
source
status
confidence
note
created_at
updated_at
```

自动黑名单统一使用：

```text
source = auto_rule
```

这样前端、后端和数据库都可以继续复用现有黑名单管理流程。