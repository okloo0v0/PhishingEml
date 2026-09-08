# V1.1 数据归档

V1.1 在 V1 基线之上增加多视图模型、`spam_other` hard-negative 训练分区，以及 V1.1.1 的受控结构视图验证数据。

`manifests/` 保存 V1.1/V1.1.1 训练、评测、消融和数据摘要；`processed/` 保存本地大型 JSONL/CSV，默认不纳入 Git。原始源文件与 V1 共用，仍以 `data/v1/manifests/sources.csv` 为来源登记基线。

V1.1.1 人工构造数据只用于受控回归和消融，不代表真实外部泛化能力。`spam_other` 的稳定 SHA-256 分桶策略保持不变，不能在 V1.2 数据导入时覆盖或重新解释。
