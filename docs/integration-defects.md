# 当前联调缺陷与不足

## 已修复

- 后端原先通过 `RuleEngine.evaluate()` 返回固定 `0` 分，现已接入成员 2 的 `evaluate_rules()`，并在调用规则前完成 URL/域名黑名单静态匹配。
- 黑名单命中结果现在会回填 `blacklist_hit`、`blacklist_match_type`、`blacklist_indicator_id`、`blacklist_source` 和 `blacklist_confidence`，历史详情也会保留这些字段。
- 域名黑名单同时支持注册域名和完整主机名匹配；完整 URL 匹配仍优先。
- `src/api/deps.py` 依赖的 `EmailParser.parse()` 适配器已补齐。

## 仍需优化

1. `BlacklistService` 对 `indicator_type=url` 的输入目前没有统一调用 URL 规范化函数；用户录入大小写、默认端口或 fragment 不一致的 URL 时，可能影响精确命中。建议新增 URL 规范化和格式校验，并同步增加 API 测试。
2. `blacklist_indicators.indicator` 当前数据库约束是单列唯一，而共享契约要求“规范化指标值 + 类型”共同判重。建议迁移为联合唯一约束，避免 URL 指标与 domain 指标互相冲突。
3. 成员 2 的敏感信息词表包含较宽泛的 `account`、`verification` 等词，可能带来正常邮件误报。建议改为短语/上下文匹配，并在报告中增加误报样本。
4. `R10` 品牌冒充规则使用固定品牌词表，未区分正文引用、签名和发件人显示名。建议增加字段级证据和可配置品牌词表。
5. 解析器对 HTML 只保留安全文本和 URL 元数据，当前 `DetectionResult` 不返回邮件快照；若前端需要检测后立即展示完整邮件头/正文，应新增契约允许的脱敏摘要字段，或继续通过历史详情读取。
6. 当前历史接口前端一次读取最多 50 条记录，尚未实现分页控件；数据量增大后应按 `pagination` 做翻页。

## 本轮联调结论

- MVP 闭环已具备：上传/粘贴 -> MIME 解析 -> URL/附件提取 -> R01--R10 规则 -> 模型推理 -> 分数融合 -> SQLite 持久化 -> 前端展示。
- 当前测试集全部通过；真实模型和黑名单命中链路已使用本地脱敏邮件完成验证。
- 上述未修复项不阻塞课程版单封邮件演示，但会影响黑名单数据一致性、误报分析和规模化使用。
