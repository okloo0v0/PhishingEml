# PhishingEml V1.1 多视图模型实施与评估报告

> 实施日期：2026-09-08
> 模型版本：`v1.1.0`
> 特征版本：`text-structure-v2`
> 状态：本地制品和元数据校验通过时默认启用；V1.0 制品保留为声明式回退

## 一、闭环范围

本轮已经完成以下工程闭环：

1. 训练与在线推理共用同一套多视图特征构造逻辑；
2. word、char、static structure、intent 四分支独立训练；
3. 使用 5 折 OOF 概率训练后期融合器，避免训练集内概率泄漏；
4. 融合器采用非负权重约束，分支风险升高不会反向降低最终概率；
5. `spam_other` 按稳定 SHA-256 划分为 train/valid/test，保留测试分区不参与拟合和调阈值；
6. V1.1 与 V1.0 在相同测试记录上比较，并报告 PR-AUC、Brier、FPR 和配对 bootstrap；
7. `ModelPredictor` 同时支持 V1.0/V1.1，V1.1 文件对不存在时回退 V1.0；
8. 模型版本、依赖、数据数量、SHA-256、阈值和指标写入独立元数据。

系统仍然只做静态分析，不访问 URL，不下载、解压、执行或渲染附件。

## 二、算法设计

```text
subject + text_body + ParsedEmail
  ├─ word TF-IDF (1,2)                -> Logistic Regression
  ├─ char_wb TF-IDF (3,5)             -> Logistic Regression
  ├─ 33 个静态结构特征                 -> StandardScaler + Logistic Regression
  └─ 21 个社会工程意图特征             -> StandardScaler + Logistic Regression

各分支 5 折 OOF phishing probability
  -> 非负约束 Logistic Regression
  -> sigmoid CalibratedClassifierCV（基于 OOF 融合分数）
  -> phishing_probability
  -> 保持原 0.65 模型 + 0.35 规则融合契约
```

字符视图保留 URL、邮箱、标点和 Unicode 形态；词视图继续使用脱敏后的 `text-v1` 文本。结构视图包括长度、字符比例、URL 协议/IP/短链/punycode/嵌套参数、From/Reply-To 关系、MIME、HTML、附件元数据和解析告警。意图视图覆盖凭据、付款、下载、回复、授权、紧迫、权威、保密和绕流程请求。

模型不输入 `rule_score`、`final_score` 或黑名单命中，避免与最终规则融合重复计分。

## 三、数据划分

| 数据角色 | 数量 | 用途 |
|---|---:|---|
| 原二分类 train | 10,175 | word/char/structure/intent 主训练 |
| hard-negative train | 1,011 | 学习普通 spam 与 phishing 边界 |
| 总训练 | 11,186 | 仅用于拟合及 OOF 融合 |
| 原 valid + hard-negative valid | 2,548 | 阈值诊断，不修改 0.50 契约阈值 |
| 原 test | 2,181 | 主指标，与 V1.0 同集比较 |
| hard-negative test | 317 | 保留误报测试，不参与拟合或调阈值 |
| cross-source test | 1,611 | 当前跨来源抽样测试 |
| Ling external | 2,859 | 精确去重后的外部 hard-negative 回放 |
| 人工边界样本 | 12 | 中文与语义边界诊断，不作为稳定统计结论 |

hard-negative 使用 `source|id|dedup_group|content_fingerprint` 的 SHA-256 结果分桶，比例约为 60/20/20。原二分类 split 和测试样本保持不变。

## 四、真实结果

以下均使用生产契约阈值 0.50：

| 指标 | V1.0 | V1.1 | 变化 |
|---|---:|---:|---:|
| 主测试 Precision | 0.9924 | 0.9953 | +0.0029 |
| 主测试 Recall | 0.9766 | 0.9850 | +0.0084 |
| 主测试 F1 | 0.9844 | 0.9901 | +0.0057 |
| 主测试 Accuracy | 0.9849 | 0.9904 | +0.0055 |
| 主测试 PR-AUC | 0.99902 | 0.99925 | +0.00023 |
| 主测试 Brier | 0.01652 | 0.00832 | -49.6%（越低越好） |
| 跨来源 F1 | 0.9841 | 0.9886 | +0.0045 |
| 保留 hard-negative FPR | 31.23% | 6.31% | 相对下降 79.8% |
| Ling 全集 phishing 判定率 | 4.20% | 2.34% | 相对下降 44.2% |

主测试 PR-AUC 配对 bootstrap 差值均值为 `+0.000237`，95% 区间为 `[-0.000210, +0.000807]`，未观察到显著退化。V1.1 主测试 Brier 和 ECE 均明显低于旧模型，说明概率可信度也有改善。人工边界集 12 条样本的 F1 为 `0.8571`（V1.0 为 `0.8333`），但其规模过小，仅作回归诊断。

本机对 50 封邮件逐封运行模型的 P95 约为 5.69 ms，仅代表模型推理，不包含 MIME 解析、数据库和 HTTP 开销。

## 五、分支结果与解释

主测试单分支 F1：

| 分支 | F1 | PR-AUC | 结论 |
|---|---:|---:|---|
| word | 0.9849 | 0.99886 | 保留了旧基线能力 |
| char | 0.9891 | 0.99926 | 当前最强单分支，证明字符视图有效 |
| structure | 0.7662 | 0.81152 | 有独立信息，但不能单独判定 |
| intent | 0.7673 | 0.83408 | 历史语料中的意图标签仍不足 |

OOF 融合基准分类器的非负权重约为：word `4.33`、char `6.68`、structure `0.85`、intent `0.00`；生产输出再经过 sigmoid 校准器的交叉验证集成。意图权重为 0 表示现有数据没有证明它在其他分支之外存在稳定增益；模型没有强行加入这一信号，也不会让它成为反向证据。

## 六、已知限制

1. 当前 `cross_source_test` 是按来源和标签平衡抽样，不是真正的 leave-one-source-out；不能据此声称适应全新来源。
2. 当前训练数据仍以历史英文公开语料为主，尚未完成严格的 2024--2025 时间留出训练实验。
3. 结构分支在现有 CSV 训练集中主要学到正文可恢复的 URL、长度和字符结构。From/Reply-To、附件和 HTML 特征在线可提取，但训练覆盖不足，相关系数可能为 0。
4. 12 条人工边界集 V1.1 F1 为 0.8571，略高于 V1.0 的 0.8333，但仍出现 2 条正常样本误报；样本太少不能形成稳定百分比，必须保留为回归诊断集。
5. 调优阈值为 0.69，但未修改冻结的生产阈值 0.50；阈值变更需要单独契约评审。

## 七、后续优化方向

工程管线已经完成，下一轮不应继续堆算法，而应补齐当前没有被模型学到的数据：

1. 为原始 MIME 训练样本保存脱敏的 From/Reply-To、URL、MIME、HTML 和附件元数据；
2. 增加中文正常收据、账号通知、项目更新与对应钓鱼样本；
3. 增加付款变更、device code、无 URL BEC、合法云域名和 AI 改写样本；
4. 建立 phishing-only 的 2024--2025 时间回放，并补充同时间窗口正常邮件后再形成完整时间测试；
5. 数据补齐后重新训练，要求意图/结构分支证明独立增益，并消除 12 条边界样本的回归。

在上述数据缺口补齐前，V1.1 适合作为本地 MVP 的默认模型，但报告和展示中不得称为已验证的新型攻击生产检测器。

## 八、复现命令

```powershell
uv run python scripts\train_model_v1_1.py
uv run python scripts\evaluate_model_v1_1.py
uv run python scripts\run_extra_evaluation_v1_1.py
uv run python scripts\generate_model_metadata_v1_1.py
uv run pytest -q
```

关键产物：

- `models/model_meta_v1_1.json`
- `data/manifests/model_training_summary_v1_1.json`
- `data/manifests/model_evaluation_summary_v1_1.json`
- `data/manifests/extra_evaluation_summary_v1_1.json`
- `docs/experiments.csv`
