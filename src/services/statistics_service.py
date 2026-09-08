"""Dashboard statistics and offline model metrics."""

from __future__ import annotations

import json
from typing import Any

from src.config import get_settings
from src.db.repositories import StatisticsRepository
from src.domain.errors import DomainError, ErrorCode
from src.domain.schemas import (
    KnowledgeArticle,
    ModelMetrics,
    to_jsonable,
)


class StatisticsService:
    def __init__(self, statistics_repo: StatisticsRepository) -> None:
        self.statistics_repo = statistics_repo

    def overview(self) -> dict[str, Any]:
        data = self.statistics_repo.overview()
        return to_jsonable(data)

    def model_metrics(self) -> dict[str, Any]:
        meta_path = get_settings().model_dir / "model_meta.json"
        if not meta_path.is_file():
            raise DomainError(ErrorCode.MODEL_NOT_READY, "模型元数据不存在", 503)
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise DomainError(
                ErrorCode.MODEL_NOT_READY, "模型元数据读取失败", 503
            ) from exc

        metrics = ModelMetrics(
            model_name=payload.get("model_name", ""),
            model_version=payload.get("model_version", ""),
            feature_version=payload.get("feature_version", ""),
            trained_at=payload.get("trained_at", ""),
            sample_counts={
                "train": payload.get("train_count", 0),
                "valid": payload.get("valid_count", 0),
                "test": payload.get("test_count", 0),
            },
            metrics={str(k): float(v) for k, v in payload.get("metrics", {}).items()},
            confusion_matrix=payload.get("test_confusion_matrix", [[], []]),
        )
        return to_jsonable(metrics)


def _article(
    article_id: int,
    category: str,
    title: str,
    summary: str,
    content: str,
    *,
    topic_type: str = "指南",
    reading_time: str = "3 分钟",
    featured: bool = False,
    key_points: list[str] | None = None,
    steps: list[str] | None = None,
    comparison: dict[str, list[str]] | None = None,
) -> KnowledgeArticle:
    return KnowledgeArticle(
        id=article_id,
        category=category,
        title=title,
        summary=summary,
        content=content,
        sort_order=article_id,
        topic_type=topic_type,
        reading_time=reading_time,
        featured=featured,
        key_points=key_points or [],
        steps=steps or [],
        comparison=comparison or {},
    )


KNOWLEDGE_ARTICLES: list[KnowledgeArticle] = [
    _article(
        1, "识别风险", "30 秒完成邮件初筛", "先判断这封邮件是否值得继续相信",
        "钓鱼邮件常利用熟悉的身份、紧迫的语气和异常操作请求缩短你的判断时间。初筛的目标不是立刻定性，而是快速找到需要停下来核验的信号。",
        topic_type="核验清单", reading_time="2 分钟", featured=True,
        key_points=["完整地址是否与声称机构一致", "请求是否符合原有业务流程", "是否催促立即登录、付款或提交信息"],
        steps=["先不点击链接和附件", "展开查看完整发件人地址", "阅读请求内容并寻找异常紧迫感", "出现任一疑点时改用官方渠道核实"],
    ),
    _article(
        2, "识别风险", "发件人身份怎么核验", "显示名称、From、Reply-To 要一起看",
        "显示名称可以任意填写，真正需要核对的是完整邮箱地址和回复地址。即使域名看起来相近，也要注意多余单词、字母替换和不常见后缀。",
        topic_type="逐项核验",
        key_points=["不要只看显示名称", "比较 From 与 Reply-To 域名", "确认联系人是否曾使用该地址"],
    ),
    _article(
        3, "识别风险", "识别紧迫感与越权请求", "越催促，越需要回到正常流程",
        "冻结账号、限时退款、领导急需转账等内容会制造行动压力。真正的风险信号往往是要求你绕过审批、保密处理或提供本不应通过邮件提交的信息。",
        topic_type="风险信号",
        comparison={"正常请求": ["说明背景和可核验编号", "允许通过既有渠道确认"], "可疑请求": ["要求保密或绕过审批", "用倒计时迫使立即操作"]},
    ),
    _article(
        4, "链接与附件", "读懂链接中的真实域名", "从主机名中找到真正控制链接的一方",
        "域名应从右向左观察，先确认注册域名，再看前面的子域名。品牌词出现在很长的子域名里，并不代表链接属于该品牌。",
        topic_type="逐项核验", featured=True,
        key_points=["核对注册域名而不是整段文字", "警惕拼写替换和多级子域名", "HTTPS 只代表连接加密，不代表网站可信"],
        steps=["在静态分析结果中找到 host", "确认注册域名与机构官方域名一致", "检查是否为 IP、短链接或 Punycode", "有疑问时手动进入官方站点核实"],
    ),
    _article(
        5, "链接与附件", "显示文字和真实目标不一致", "按钮写着官网，目标可能是另一处",
        "HTML 邮件可以让按钮文字与真实目标完全不同。核验时应比较链接显示信息和实际主机名，不能依据按钮颜色、品牌图标或文字作判断。",
        topic_type="案例解读",
        comparison={"表面信息": ["按钮写着账号中心", "页面使用熟悉的品牌名称"], "静态证据": ["真实目标域名与品牌无关", "路径包含 login、verify 等诱导词"]},
    ),
    _article(
        6, "链接与附件", "IP、短链接与编码域名", "理解异常结构，不把单一特征当结论",
        "IP 地址、短链接、超长路径和 Punycode 都可能隐藏真实目标，但也可能有正常用途。应将这些结构信号与邮件身份、语气和操作请求组合判断。",
        topic_type="风险信号",
        key_points=["短链接会隐藏最终域名", "IP 主机缺少直观机构身份", "xn-- 开头的域名需要检查对应字符"],
    ),
    _article(
        7, "链接与附件", "附件打开前的四步检查", "文件名只是线索，来源和场景同样重要",
        "未知附件不应因为看起来像文档就直接打开。先确认是否预期收到、发件人是否可信、扩展名是否匹配，再通过组织规定的方式交给安全人员处理。",
        topic_type="核验清单", featured=True,
        steps=["确认自己是否在等待这份文件", "核对完整文件名和最后一个扩展名", "通过第二渠道向发件人确认", "无法确认时保留邮件并上报，不自行尝试打开"],
        key_points=["双扩展名可能掩盖真实类型", "图标不能证明文件类型", "压缩包内文件仍需单独核验"],
    ),
    _article(
        8, "链接与附件", "宏文档与双扩展名", "invoice.pdf.exe 并不是 PDF",
        "系统应关注文件最后一个扩展名、MIME 声明和文件名组合。带宏 Office 文档、脚本、快捷方式和伪装成图片或 PDF 的可执行文件都需要额外谨慎。",
        topic_type="案例解读",
        comparison={"较可信特征": ["文件类型与业务场景一致", "通过既有协作平台发送"], "高风险特征": ["双扩展名或可执行后缀", "要求启用宏或关闭安全软件"]},
    ),
    _article(
        9, "链接与附件", "压缩包与未知 MIME 怎么处理", "不要通过试着打开来判断附件是什么",
        "压缩包会隐藏内部文件类型，application/octet-stream 也只说明类型未明确。课程系统只记录元数据，不解压、不执行；用户同样应将未知文件交给受控流程处理。",
        topic_type="处理原则",
        key_points=["不解压来源不明的压缩包", "不运行要求安装或更新的文件", "记录文件名、大小和哈希便于上报"],
    ),
    _article(
        10, "识别风险", "冒充领导、同事与 IT 支持", "熟悉的名字并不能代替身份验证",
        "攻击者常从公开信息中获取姓名和岗位，再用紧急付款、权限变更或系统维护作为理由。判断重点是地址、流程和请求内容，而不是语气是否像熟人。",
        topic_type="场景专题", featured=True,
        comparison={"正常协作": ["通过既有工单或审批流程", "允许电话或即时通讯复核"], "冒充信号": ["临时更换收款账户", "要求绕过流程并对他人保密"]},
    ),
    _article(
        11, "识别风险", "账单、验证码与共享文档", "熟悉的业务通知也可能是入口",
        "发票逾期、验证码异常、云盘共享和会议邀请常被用于诱导登录。先确认自己是否发起过对应业务，再通过书签或手动输入官方地址查看真实状态。",
        topic_type="场景专题",
        key_points=["没有发起过的验证码需要警惕", "共享文档应核对发起人与收件范围", "账单变更必须走财务复核"],
    ),
    _article(
        12, "识别风险", "招聘、奖学金与客服退款", "机会和补偿也会制造判断压力",
        "高回报兼职、奖学金补录和主动退款容易诱导填写身份资料或支付手续费。正规流程通常有公开页面、明确联系人和可独立核验的申请记录。",
        topic_type="场景专题",
        comparison={"正规流程": ["可在官方站点独立查询", "不会索要密码或验证码"], "诱导信号": ["先付费才能领取", "要求转到私人聊天继续操作"]},
    ),
    _article(
        13, "账号保护", "让账号更难被接管", "唯一密码、多因素认证和恢复信息保护",
        "重要账号应使用不同的长密码并开启多因素认证。认证器或硬件密钥通常比短信验证码更能抵抗钓鱼，恢复码则应离线妥善保存。",
        topic_type="防护指南", featured=True,
        steps=["为关键账号设置唯一密码", "开启认证器或硬件密钥", "检查恢复邮箱和手机号", "定期查看登录会话和授权应用"],
    ),
    _article(
        14, "账号保护", "建立独立核验通道", "关键操作不要从邮件中的入口开始",
        "登录、付款、权限变更和敏感资料提交应通过书签、手动输入的官方地址、已有工单或已知联系电话完成核验。",
        topic_type="行为习惯",
        key_points=["邮件只作为通知，不作为唯一入口", "回拨使用通讯录中的号码", "重大操作采用双人复核"],
    ),
    _article(
        15, "账号保护", "识别账号已被接管的迹象", "异常登录、自动转发和陌生授权都值得检查",
        "如果出现未知地点登录、密码重置通知、陌生应用授权或邮箱自动转发规则，应立即从可信设备检查账号安全状态。",
        topic_type="风险信号",
        steps=["查看近期登录和设备列表", "撤销陌生会话与第三方授权", "检查自动转发和邮箱规则", "修改密码并通知组织安全人员"],
    ),
    _article(
        16, "处理与应急", "已经点击可疑链接怎么办", "停止继续操作，保留现场信息",
        "仅点击并不代表一定造成损失，但应立即停止后续输入和下载。关闭页面，记录时间与页面提示，并按照组织流程联系安全人员。",
        topic_type="应急步骤", reading_time="2 分钟", featured=True,
        steps=["关闭页面并停止后续操作", "记录点击时间、设备和页面现象", "检查是否发生下载或跳转", "联系安全人员并按指引继续处理"],
    ),
    _article(
        17, "处理与应急", "已经输入密码或验证码", "从可信设备立即控制账号风险",
        "如果提交过密码、验证码或恢复码，应将其视为可能泄露。从可信设备修改密码、撤销会话，并检查多因素认证和恢复信息是否被改变。",
        topic_type="应急步骤",
        steps=["从可信设备修改受影响账号密码", "退出全部会话并撤销陌生授权", "检查多因素认证和恢复信息", "同步排查复用同一密码的其他账号"],
    ),
    _article(
        18, "处理与应急", "已经打开或运行附件", "隔离设备并交由专业人员检查",
        "不要自行反复运行文件验证现象，也不要随意删除证据。停止使用设备处理敏感业务，按组织要求隔离设备并报告附件名称和发生时间。",
        topic_type="应急步骤",
        steps=["停止运行附件及相关程序", "断开不必要的网络连接", "不要继续登录重要账号", "报告附件名称、时间和设备信息并等待处置"],
    ),
    _article(
        19, "上报协作", "上报时应该保留哪些证据", "完整邮件比转发截图更有分析价值",
        "建议保留原始 .eml、检测编号、收到时间、发件人地址、链接文本和附件元数据。不要为了取证去访问链接或再次运行附件。",
        topic_type="上报清单", featured=True,
        key_points=["原始 .eml 和检测编号", "收到及操作发生的时间", "点击、输入或下载过什么", "涉及的账号和设备范围"],
    ),
    _article(
        20, "上报协作", "把风险说明清楚的上报结构", "事实、影响、已采取措施和待协助事项",
        "有效上报应区分已确认事实和个人判断，说明是否点击、是否输入信息、是否下载附件，并明确当前需要安全人员协助的事项。",
        topic_type="沟通模板",
        steps=["说明邮件来源和收到时间", "列出系统提示的主要风险证据", "说明自己已执行过的操作", "提出需要封禁、排查或恢复账号等协助"],
    ),
    _article(
        21, "上报协作", "避免可疑邮件二次扩散", "不要直接转发给更多同事围观",
        "直接转发可能让更多人接触可疑链接和附件。应使用组织规定的上报入口，或先删除链接可点击性并明确标注风险。",
        topic_type="协作原则",
        key_points=["优先提交原始邮件给指定安全渠道", "不要在群聊中传播可点击链接", "提醒可能收到同类邮件的人员但不复制诱导内容"],
    ),
    _article(
        22, "典型案例", "案例：账号异常通知", "同样是安全提醒，证据结构完全不同",
        "正常通知通常允许用户从官方应用独立查看安全状态；钓鱼通知则常要求从邮件链接立即登录，并通过陌生域名收集凭据。",
        topic_type="案例对比", reading_time="4 分钟", featured=True,
        comparison={"正常邮件": ["完整地址属于官方域名", "提示从官方应用查看", "不索要密码和验证码"], "疑似钓鱼": ["Reply-To 指向无关域名", "限时点击陌生登录链接", "要求输入密码或验证码"]},
    ),
    _article(
        23, "典型案例", "案例：发票与收款账户变更", "财务场景必须依靠流程而不是邮件语气",
        "攻击者可能冒充供应商发送新账户，或利用真实往来邮件的上下文。即使附件和签名看起来正常，也必须通过原有联系人和审批流程确认。",
        topic_type="案例对比", reading_time="4 分钟",
        comparison={"正常变更": ["有正式合同或工单依据", "原联系人可通过既有号码确认"], "高风险变更": ["突然要求支付到新账户", "催促保密并跳过复核"]},
    ),
    _article(
        24, "典型案例", "案例：共享文档与会议邀请", "熟悉界面不代表登录页面真实",
        "伪造的共享文档通知常把用户带到仿冒登录页。正常流程可以在已有云盘或日历中独立找到记录，而不必依赖邮件中的按钮。",
        topic_type="案例对比", reading_time="4 分钟",
        comparison={"正常邀请": ["在官方应用内可找到同一记录", "发起人和协作背景明确"], "可疑邀请": ["登录页域名与服务商不一致", "要求重新输入密码或下载插件"]},
    ),
    _article(
        25, "处理与应急", "收到邮件后的标准核验顺序", "把判断拆成固定动作，减少被语气带着走",
        "面对任何要求登录、付款、下载或提交资料的邮件，都可以沿用同一套顺序：先暂停，再看身份和请求，最后通过独立渠道确认。",
        topic_type="操作流程",
        steps=["暂停点击、回复和下载", "核对 From、Reply-To 与真实域名", "确认请求是否符合已有流程", "通过官方渠道完成核验后再决定"],
    ),
    _article(
        26, "处理与应急", "如何记录一次可疑邮件判断", "让之后的复核有事实可追溯",
        "记录判断时应区分观察到的事实、系统给出的证据和自己的处理动作。清晰的记录能帮助安全人员快速复现风险，也能避免凭印象下结论。",
        topic_type="记录方法",
        key_points=["记录收到时间和原始主题", "保留发件人、Reply-To、URL 与附件元数据", "写明是否点击、输入或下载", "不要把密码等敏感内容复制到备注"],
    ),
    _article(
        27, "处理与应急", "核验完成后如何安全结束", "确认安全也要回到正常业务入口",
        "完成核验后，不要继续使用邮件中的按钮作为长期入口。将后续操作切回书签、官方应用或既有工单，并清理不再需要的下载文件。",
        topic_type="操作流程",
        steps=["从官方应用或书签重新进入业务", "确认操作结果和通知来源一致", "删除不需要的下载文件", "将可疑邮件按组织规定归档或删除"],
    ),
]


def list_knowledge(keyword: str | None, category: str | None) -> list[dict[str, Any]]:
    articles = KNOWLEDGE_ARTICLES
    if category:
        articles = [article for article in articles if article.category == category]
    if keyword:
        needle = keyword.strip().lower()
        articles = [
            article
            for article in articles
            if needle in " \n".join(
                [
                    article.title,
                    article.summary,
                    article.content,
                    *article.key_points,
                    *article.steps,
                    *(
                        item
                        for values in article.comparison.values()
                        for item in values
                    ),
                ]
            ).lower()
        ]
    return to_jsonable(sorted(articles, key=lambda article: article.sort_order))
