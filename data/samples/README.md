# EML 演示样本

这些邮件是人工构造的脱敏测试夹具，只用于本地静态解析和规则检测，不包含真实邮箱、凭据或可访问的业务链接。

| 文件 | 覆盖场景 |
| --- | --- |
| `clean_plain.eml` | 纯文本正常邮件，作为低风险基线 |
| `suspicious_urgent.eml` | HTML、紧急措辞、敏感信息请求、Reply-To 域名不一致、IP 链接和品牌提及 |
| `multipart_html.eml` | `multipart/alternative`，同时包含纯文本和 HTML |
| `risky_attachment.eml` | `multipart/mixed` 和 `.docm` 宏文档附件，仅验证附件元数据 |
| `chinese_encoded.eml` | RFC 2047 中文主题和发件人编码解码 |
| `blacklist_hit_demo.eml` | 配合离线黑名单指标，演示 URL 命中和 R03 解释 |

在前端选择“演示样本”时，`sample_id` 使用不带后缀的文件名，例如 `suspicious_urgent`。

如需验证黑名单命中，可先在黑名单页面添加精确 URL `http://203.0.113.10/login?verify=1`（类型选择 `url`），再分析 `blacklist_hit_demo`；也可以添加域名指标 `example.invalid` 后分析包含该域名的样本。样本中的 URL 只会作为文本展示，系统不会访问它。
