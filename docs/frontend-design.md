# 前端实现方案

## 技术与边界

- 原生 HTML、CSS、JavaScript 和本地 ECharts 文件实现单页界面；不依赖 Node 构建流程。
- FastAPI 在 `/` 提供应用页面，在 `/static` 提供前端资源；页面与 API 同源请求。
- 只调用本地 `/api/...` 接口。URL 以文本节点展示，不设置真实 `href`；附件只展示元数据。
- 所有 API 字段通过 DOM `textContent` 写入，禁止把邮件内容、规则证据或知识库内容传给 `innerHTML`。

## 信息架构

| 视图 | 主要任务 | 接口 |
| --- | --- | --- |
| 邮件检测 | 上传 `.eml` 或粘贴 MIME 原文，查看融合风险、证据、URL、附件和建议 | `POST /api/emails/analyze`、`POST /api/feedback` |
| 检测历史 | 按风险等级筛选、查看单条检测详情 | `GET /api/detections`、`GET /api/detections/{id}` |
| 黑名单 | 新增离线指标、搜索、按状态查看和标记待复核 | `GET/POST/PATCH /api/blacklist` |
| 统计看板 | 查看风险分布、趋势、规则命中和模型离线指标 | `GET /api/statistics/overview`、`GET /api/model/metrics` |
| 防范知识 | 按类别和关键字阅读本地教育材料 | `GET /api/knowledge` |

## 交互原则

1. 检测页只允许文件或原文一种输入方式；切换输入方式不会同时提交字段，匹配 D-001 严格互斥契约。
2. 高、中、低风险同时用文字和颜色表达；模型标签和融合风险等级分开显示。
3. 加载、空数据、接口失败和模型未就绪均在页面内给出反馈，并保留后端错误码。
4. 高风险信息按“分数 -> 证据 -> 静态资源 -> 建议 -> 反馈”排列，减少用户在页面间往返。
5. 界面使用 `example.invalid` 演示语义，不鼓励点击或访问任何邮件链接。

## 目录

```text
src/web/
  index.html               # 单页应用结构
  css/app.css              # 设计令牌和响应式样式
  js/api.js                # API 请求和统一错误处理
  js/app.js                # 页面状态、DOM 渲染和图表
  vendor/echarts.min.js    # 本地统计图表库
```

## 验收要点

- `/`、`/health` 和现有 `/api/...` 路由可同时访问。
- 页面不加载 CDN、字体或第三方资源。
- 邮件标题、正文、发件人、URL、附件名称和规则证据均使用安全文本渲染。
- 上传的 `.eml` 由既有后端继续执行 5 MiB、扩展名和 MIME 解析校验。
