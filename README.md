# PhishingEml

钓鱼邮件静态分析与检测系统课程项目。

## 项目文档

- 项目可行性分析与功能设计（方案参考）：钓鱼邮件检测系统项目可行性分析与功能设计.md
- 详细实现方案（工程参考）：钓鱼邮件检测系统详细实现方案.md
- GitHub 协作开发指南：CONTRIBUTING.md
- 项目开发规范：AGENTS.md
- 阶段 A 共享契约：docs/shared-contract.md

## 基础目录

    data/       数据集、演示样本和黑名单
    models/     模型文件和模型元数据
    scripts/    初始化、数据处理和训练脚本
    src/        应用源码
    tests/      自动化测试
    docs/       API、实验、测试和演示文档

当前仓库处于工程初始化阶段。安装、训练、启动和验收流程以后续实现为准，先参考详细实现方案和协作开发指南。

当前已完成阶段 A 的共享契约冻结。后续模块开发必须以 `docs/shared-contract.md` 和 `src/domain/` 为准，不得参考方案文档中的早期草案自行定义不兼容的数据结构、分数语义或 API 字段。

遗留决策项 `D-001` 已关闭：`POST /api/emails/analyze` 必须且只能接收 `file`、`raw_text`、`sample_id` 三者之一；多传返回 `400 INPUT_CONFLICT`，不使用隐式优先级。
