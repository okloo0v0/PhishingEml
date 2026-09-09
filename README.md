# PhishingEml

钓鱼邮件静态分析与检测系统课程项目。

## 项目文档

- 项目可行性分析与功能设计：钓鱼邮件检测系统项目可行性分析与功能设计.md
- 详细实现方案：钓鱼邮件检测系统详细实现方案.md
- GitHub 协作开发指南：CONTRIBUTING.md
- 项目开发规范：AGENTS.md
- 阶段 A 共享契约：docs/shared-contract.md
- 平台真实测试报告：docs/test-report.md
- MVP 阶段差异分析与优化路线：docs/mvp-report.md
- 模型调研与实验路线：docs/model-capability-improvement-research.md
- V1.1.1 数据补齐与多视图验证：docs/model-v1.1.1-data-and-ablation-report.md
- V1.2 Intent 重设计与公开数据路线：docs/model-v1.2-intent-redesign-and-data-route.md
- V1/V1.1/V1.2 数据归档入口：data/README.md

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

本地存在完整的 V1.2 模型和元数据时，服务优先加载 `phishing_model_v1_2.joblib`；否则依次回退到已声明的 V1.1、V1.0 制品。模型文件被 Git 忽略，不会随代码仓库分发。终止服务按 `Ctrl+C`。

## V1.1 模型训练与评估

V1.2 Phase 1 数据布局审计：

```powershell
uv run python scripts\audit_v1_2_data_layout.py
```

V1.2 公开数据获取（仅访问脚本中的 allowlist，邮件内 URL 不会被访问）：

```powershell
uv run python scripts\download_v1_2_sources.py --list
uv run python scripts\download_v1_2_sources.py
```

在已有 `data/processed/emails.csv` 和 hard-negative 数据的环境中执行：

```powershell
uv run python scripts\train_model_v1_1.py
uv run python scripts\evaluate_model_v1_1.py
uv run python scripts\run_extra_evaluation_v1_1.py
uv run python scripts\generate_model_metadata_v1_1.py
```

训练会生成独立的版本化制品，不覆盖 V1.0/V1.1。V1.2 默认制品为 `models/phishing_model_v1_2.joblib` 与 `models/model_meta_v1_2.json`；两者同时存在且通过版本、标签顺序和 SHA-256 校验时，默认推理才会启用 V1.2。

V1.1.1 的定向数据补齐、消融和候选评测命令如下。补充语料为安全人工构造数据，只用于验证模型分支和回归流程；它不替代真实、脱敏来源的独立评测。

```powershell
uv run python scripts\build_v1_1_1_curated_dataset.py
uv run python scripts\ablate_model_v1_1.py
uv run python scripts\train_model_v1_1.py `
  --supplement data\processed\v1_1_1_curated_train.jsonl `
  --model-version v1.1.1-candidate `
  --model models\phishing_model_v1_1_1.joblib `
  --summary data\manifests\model_training_summary_v1_1_1.json
uv run python scripts\evaluate_model_v1_1.py `
  --model models\phishing_model_v1_1_1.joblib `
  --chinese-test data\processed\v1_1_1_chinese_test.jsonl `
  --modern-attack-test data\processed\v1_1_1_modern_attack_test.jsonl `
  --boundary-test data\processed\v1_1_1_boundary_test.jsonl
```

## 测试集邮件与演示样本

演示样本位于 `data/samples/`，其中 `blacklist_hit_demo` 可配合黑名单页面演示 URL 命中。若要从本地公开归档恢复模型 `test` 集中可用的原始 MIME 邮件，执行：

```powershell
uv run python scripts\export_test_emails.py
```

邮件会输出到被 Git 忽略的 `tmp/testset_eml/`。该命令只恢复 Nazario 和 SpamAssassin ham 中能通过 `source_hash` 校验的邮件；批量平台联调结果见 `docs/test-report.md`。
