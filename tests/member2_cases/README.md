# Member 2 解析器与规则测试案例

此文件夹包含用于测试**邮件解析器、URL 分析器、附件元数据提取器以及规则引擎**的静态邮件样本。

运行全部测试：

```bash
python -m unittest -q
```

仅运行这些测试案例：

```bash
python -m unittest tests.test_member2_sample_cases -q
```

运行测试案例后，完整的提取结果会写入：

```text
tests/member2_cases/actual_outputs/
```

预期结果（`expected`）中的 JSON 文件只会检查一些**稳定且重要的字段**。

实际输出文件（`actual_outputs`）则会包含更加完整的 `ParsedEmail` 和 `RuleEvaluation` 数据，方便进行检查和调试。
