# PhishingEml

钓鱼邮件静态分析与检测系统课程项目。

## 项目文档

- 项目可行性分析与功能设计：钓鱼邮件检测系统项目可行性分析与功能设计.md
- 详细实现方案：钓鱼邮件检测系统详细实现方案.md
- GitHub 协作开发指南：CONTRIBUTING.md
- 项目开发规范：AGENTS.md
- 阶段 A 共享契约：docs/shared-contract.md
- 平台真实测试报告：docs/test-report.md

## 基础目录

    data/       数据集、演示样本和黑名单
    models/     模型文件和模型元数据
    scripts/    初始化、数据处理和训练脚本
    src/        应用源码
    tests/      自动化测试
    docs/       API、实验、测试和演示文档

当前版本已经完成前端、后端、规则解析和模型推理的基础集成，可直接启动本地演示服务。

当前已完成阶段 A 的共享契约冻结。跨模块字段以 `src/domain/` 和 `docs/shared-contract.md` 为准。

## Python 环境

项目固定使用 Python 3.11，并由 uv 创建虚拟环境和锁定依赖：

```powershell
uv sync
uv run python --version
uv run pytest -q
```

## 启动本地服务

在项目根目录（包含 `pyproject.toml` 的目录）执行：

```powershell
# 首次运行或依赖发生变化时执行
uv sync

# 默认配置即可运行；如需自定义配置，先设置 PowerShell 环境变量，例如：
# $env:DATABASE_URL = "sqlite:///./data/phishing.db"

# 初始化或补齐 SQLite 表结构
uv run python scripts\init_db.py

# 启动 FastAPI + 原生前端
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
```

启动后访问：

- 前端页面：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/health`
- API 文档：`http://127.0.0.1:8000/docs`

当前仓库已包含 `models/phishing_model.joblib` 和模型元数据，通常不需要重新训练。若模型文件缺失，再按下方数据处理和训练命令生成模型。终止服务按 `Ctrl+C`。

## 测试集邮件与演示样本

演示样本位于 `data/samples/`，其中 `blacklist_hit_demo` 可配合黑名单页面演示 URL 命中。若要从本地公开归档恢复模型 `test` 集中可用的原始 MIME 邮件，执行：

```powershell
uv run python scripts\export_test_emails.py
```

邮件会输出到被 Git 忽略的 `tmp/testset_eml/`。该命令只恢复 Nazario 和 SpamAssassin ham 中能通过 `source_hash` 校验的邮件；批量平台联调结果见 `docs/test-report.md`。
