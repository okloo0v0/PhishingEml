# PhishingEml GitHub 协作开发指南

本文档说明项目组成员如何加入仓库、同步代码、开发功能、提交 Pull Request 和完成代码审核。

## 1. 协作模型

项目采用以下分支模型：

    main：稳定、可验收版本
    dev：日常集成分支
    feat/*：个人功能分支
    fix/*：缺陷修复分支

日常功能优先合并到 dev，最终验收版本再合并到 main。不要直接在 main 上开发。

## 2. 加入仓库与首次配置

由仓库所有者邀请每名成员加入 GitHub 仓库。成员接受邀请后，使用自己的 GitHub 账号、SSH 密钥或 HTTPS 凭据。

禁止共享：

- GitHub 密码；
- Personal Access Token；
- SSH 私钥；
- .env 文件；
- 真实邮箱密码和未脱敏邮件数据。

推荐使用 SSH 克隆：

    cd D:\CodeSpace
    git clone git@github.com:okloo0v0/PhishingEml.git
    cd PhishingEml
    ssh -T git@github.com

也可以使用 HTTPS：

    git clone https://github.com/okloo0v0/PhishingEml.git
    cd PhishingEml

配置提交身份：

    git config --global user.name "你的 GitHub 用户名"
    git config --global user.email "你的 GitHub 邮箱"

HTTPS 推送使用 Personal Access Token，不使用 GitHub 登录密码。Windows 环境建议使用 Git Credential Manager 保存凭据。

## 3. 项目分工

| 成员 | 推荐分支 | 主要负责内容 |
|---|---|---|
| 成员 1 | feat/member1-model | 数据集、清洗、模型训练、评价指标 |
| 成员 2 | feat/member2-parser | MIME、HTML、URL、附件解析和规则引擎 |
| 成员 3 | feat/member3-api | FastAPI、SQLite、历史、黑名单和统计接口 |
| 成员 4 | feat/member4-web | 页面、交互、看板、联调、演示和文档 |

分工不限制互相协助，但跨模块修改必须提前通知对应负责人。

## 4. 标准开发流程

### 4.0 开发依赖顺序与阶段门

四人不是从第一天开始完全独立开发。项目必须按照以下顺序推进：

    需求和范围确认
      -> 共享数据结构、API 和数据库字段冻结
      -> 邮件解析器和模型输入格式确定
      -> 四人并行开发各自模块
      -> 后端接入解析器、规则和模型
      -> 前端接入稳定 API
      -> 端到端测试
      -> 基本版验收
      -> 高级功能

#### 阶段 A：全组共同确认

第 1 天由全组共同完成，不分散开发：

- 确认基本版功能和明确不做的内容；
- 确认风险等级、评分阈值和结果标签；
- 确认 ParsedEmail、ParsedUrl、AttachmentMeta 和 DetectionResult；
- 确认分析接口、历史接口和黑名单接口；
- 确认数据库表字段、模型文件名和启动命令；
- 确认演示样本类型和测试样本类型。

阶段产出：共享 schema 初版、API 字段表、数据库字段表、任务分工和验收清单。

没有完成阶段 A，不得开始跨模块功能开发。

#### 阶段 B：先完成基础产出

阶段 B 的任务有明确依赖：

1. 成员 2 先完成 ParsedEmail、ParsedUrl 和 AttachmentMeta 的最小版本；
2. 成员 1 根据确定的文本字段完成数据清洗和模型输入格式；
3. 成员 3 根据 DetectionResult 完成 API、数据库和服务层骨架；
4. 成员 4 根据 DetectionResult 使用 Mock JSON 完成页面。

阶段 B 可以并行，但成员 1、3、4 必须使用阶段 A 冻结的字段，不能各自重新定义数据结构。

阶段 B 的阶段门：

- 成员 2 能解析至少一封纯文本、HTML、multipart 和带附件邮件；
- 成员 1 能用固定文本格式完成模型训练或提供可调用的 Mock Predictor；
- 成员 3 的分析接口能够接收请求并返回固定格式结果；
- 成员 4 的结果页能够展示固定格式结果。

#### 阶段 C：完成单封邮件检测闭环

阶段 C 必须按以下顺序集成：

1. 成员 2 将解析器输出和 URL/附件特征提交到 dev；
2. 成员 2 完成规则引擎，输出规则分数和解释项；
3. 成员 1 提交可加载的模型 Pipeline 和 ModelPredictor；
4. 成员 3 将解析器、规则引擎、模型推理和数据库保存编排进 AnalysisService；
5. 成员 4 接入稳定的 POST /api/emails/analyze；
6. 全组使用真实 .eml 完成一次端到端测试。

成员 4 不应在 API 字段尚未稳定前绑定真实页面数据；成员 3 不应在解析器和模型输出尚未确认前自行猜测字段。

阶段 C 的阶段门：上传一封 .eml 后，能够完成解析、检测、解释、保存和页面展示。

#### 阶段 D：基本版验收后再做高级功能

只有阶段 C 通过后，才能实现：

- 黑名单导入和管理；
- 历史筛选；
- 统计看板；
- 模型对比；
- 防范知识库；
- 用户反馈；
- 批量检测和导出。

如果阶段 C 未通过，所有成员优先修复 MVP，不得继续堆加页面或外部数据源。

#### 四人的实际启动顺序

可以按以下顺序理解各成员的依赖关系：

    全组：冻结契约
      -> 成员 2：确定解析输出
      -> 成员 1：确定模型输入和推理输出
      -> 成员 3：接入解析、规则、模型和数据库
      -> 成员 4：接入稳定 API 并完成页面联调
      -> 全组：集成测试和验收

其中成员 1、3、4 可以在成员 2 开发解析器的同时做准备工作，但不能绕过共享契约直接形成各自独立的数据格式。

### 4.1 开始工作前同步

    git switch main
    git pull --ff-only origin main
    git switch -c feat/member2-parser

如果分支已经存在：

    git switch feat/member2-parser
    git merge main

### 4.2 编码和测试

编码前确认：

- 修改属于当前任务和模块边界；
- 是否涉及共享 schema、API 或数据库字段；
- 是否需要新增测试样本；
- 是否会接触邮件原文、URL 或附件；
- 是否引入新的依赖。

提交前执行相关测试：

    pytest -q

### 4.3 提交和推送

    git status
    git diff
    git add 修改的文件
    git commit -m "feat: add MIME email parser"
    git push -u origin feat/member2-parser

不要使用 git add . 盲目提交，避免把数据库、日志、原始邮件和本地配置加入仓库。

## 5. Pull Request 规则

功能完成并通过测试后，在 GitHub 中创建 Pull Request：

    源分支：feat/个人分支
    目标分支：dev

基本版或最终版本由负责人从 dev 创建到 main 的 Pull Request。

Pull Request 描述至少包含：

    ## 修改内容
    - 完成的功能
    - 修改的模块
    - 是否修改共享 schema、API 或数据库

    ## 测试命令
    pytest -q

    ## 安全检查
    - [ ] 未访问邮件 URL
    - [ ] 未执行或解压附件
    - [ ] 邮件内容已转义展示
    - [ ] 未提交敏感数据

    ## 已知问题
    - 暂未支持的内容

至少一名其他成员审核通过后再合并。审核重点包括功能正确性、接口兼容性、测试覆盖、安全风险和文档同步。

## 6. 共享契约修改

以下内容属于高影响修改：

- src/domain/schemas.py；
- 风险等级、评分阈值和模型输出；
- API 请求、响应和错误码；
- 数据库表字段；
- .gitignore、AGENTS.md 和 requirements.txt。

修改前在小组群中说明：

    修改对象：
    修改原因：
    影响成员：
    兼容方案：
    测试方式：

共享字段变化必须同步修改后端、前端、测试和 API 文档。

## 7. 冲突处理

合并前同步目标分支：

    git fetch origin
    git merge origin/dev

解决冲突后：

    git add 冲突文件
    git commit -m "fix: resolve merge conflicts"
    git push

解决共享 schema、数据库或 API 冲突时必须通知相关负责人。

禁止使用以下命令覆盖他人工作：

    git reset --hard
    git push --force

## 8. 目录与数据规则

    data/raw/          原始数据，不提交
    data/processed/    清洗后数据，不提交大文件
    data/samples/      脱敏演示邮件
    data/blacklist/    离线黑名单快照
    models/            模型元数据和模型文件
    scripts/           初始化、清洗、训练和导入脚本
    src/               应用源码
    tests/             自动化测试和测试夹具
    docs/              API、实验、测试和演示文档

.gitkeep 只用于维护空目录，不代表可以提交原始数据。选题 PDF 保留在本地，但不纳入 Git。

## 9. 安全要求

- 不访问邮件中的真实可疑 URL；
- 不打开、执行或解压未知附件；
- URL 只以文本展示，不设置真实 href；
- 前端不得使用 innerHTML 直接展示邮件 HTML；
- 不提交真实邮箱、密码、Token、私钥或未脱敏邮件；
- 使用虚构域名、脱敏样本和离线黑名单完成演示；
- 检测结果使用“疑似钓鱼”“风险提示”等表述。

## 10. 每日协作同步

每名成员每天同步：

    已完成：
    进行中：
    遇到的问题：
    需要谁配合：
    下一步计划：

每天至少形成一个可以启动或测试的集成版本。问题优先记录在 GitHub Issue 或 Pull Request 中。

## 11. 合并前检查

- [ ] 分支已同步最新目标分支；
- [ ] 相关测试通过；
- [ ] 没有调试输出和临时文件；
- [ ] 没有提交 .env、数据库、日志或原始数据；
- [ ] 没有访问 URL 或执行附件；
- [ ] API、schema 和前端调用保持一致；
- [ ] 相关 README、API 或测试文档已更新；
- [ ] Pull Request 已写明测试命令和已知问题。

## 12. 两周协作节奏

| 时间 | 目标 |
|---|---|
| 第 1 天 | 冻结范围、分工、schema、API 和数据库字段 |
| 第 2--3 天 | 四人并行完成基础模块和 Mock 页面 |
| 第 4 天 | 第一次集成，接入真实解析和模型结果 |
| 第 5--6 天 | 完成单封邮件检测 MVP |
| 第 7 天 | 基本版验收并打 v0.2-mvp 标签 |
| 第 8--10 天 | 黑名单、历史、看板、模型对比和知识库 |
| 第 11--12 天 | 安全测试、异常测试和集成冻结 |
| 第 13--14 天 | 报告、PPT、演示和最终 v1.0-demo 标签 |
