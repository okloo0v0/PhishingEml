# PhishingEml

钓鱼邮件静态分析与检测系统课程项目。

## 项目文档

- 项目可行性分析与功能设计：钓鱼邮件检测系统项目可行性分析与功能设计.md
- 详细实现方案：钓鱼邮件检测系统详细实现方案.md
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

当前已完成阶段 A 的共享契约冻结。后续模块开发必须以 src/domain/ 和 docs/shared-contract.md 为准，不得各自定义不兼容的数据结构、分数语义或 API 字段。

## Python 环境

项目固定使用 Python 3.11，并由 uv 创建虚拟环境和锁定依赖：

```powershell
uv sync
uv run python --version
uv run pytest -q
```

成员1的数据收集命令：

```powershell
uv run python scripts\download_datasets.py --list
uv run python scripts\download_datasets.py
uv run python scripts\inventory_datasets.py
```

公开原始邮件保存在 `data/raw/` 且不提交 Git；来源、许可证、哈希和样本库存记录在 `data/manifests/`。
