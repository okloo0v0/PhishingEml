"""Build safe, de-identified V1.1.1 data partitions for multiview validation.

The catalog is intentionally synthetic and never models a real organisation or
inbox. It creates RFC-style messages only in memory, parses them with the
project parser, and writes static metadata without attachment payloads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.detection.text_features import clean_email_text
from src.parsers.email_parser import parse_email


DATA_DIR = ROOT / "data" / "processed"
MANIFEST_DIR = ROOT / "data" / "manifests"
DEFAULT_TRAIN = DATA_DIR / "v1_1_1_curated_train.jsonl"
DEFAULT_CHINESE_TEST = DATA_DIR / "v1_1_1_chinese_test.jsonl"
DEFAULT_MODERN_TEST = DATA_DIR / "v1_1_1_modern_attack_test.jsonl"
DEFAULT_BOUNDARY_TEST = DATA_DIR / "v1_1_1_boundary_test.jsonl"
DEFAULT_SUMMARY = MANIFEST_DIR / "v1_1_1_curated_data_summary.json"

ZH_MARKERS = ("华东组", "北方组", "南方组", "研发组", "行政组", "教学组", "服务组", "运营组")
EN_MARKERS = ("north", "south", "east", "west", "alpha", "beta", "gamma", "delta")


@dataclass(frozen=True)
class Template:
    label: str
    language: str
    attack_type: str
    subject: str
    body: str
    target_url: str = ""
    use_html: bool = False
    attachment_kind: str = ""
    reply_mismatch: bool = False
    return_path_mismatch: bool = False


TRAIN_TEMPLATES = (
    Template("phishing", "zh", "credential", "{marker}账号需要安全校验", "检测到 {marker} 的账户访问异常。请在今日完成密码验证：{url}。", "https://account-check.example.invalid/verify", True, "", True, True),
    Template("phishing", "zh", "payment_bec", "{marker}收款账户变更确认", "供应商要求更新收款信息。请回复新的银行账户并保持本次调整保密。", "", False, "", True, False),
    Template("phishing", "zh", "oauth_device_code", "{marker}设备代码授权提醒", "为恢复访问，请在验证页面输入设备代码并批准登录：{url}。", "https://device-auth.example.invalid/code", True, "", True, True),
    Template("phishing", "zh", "attachment", "{marker}共享文档待查看", "请下载附件中的项目文件，并按提示启用内容后回复确认。", "", False, "risky", True, False),
    Template("phishing", "zh", "data_request", "{marker}人事资料补录", "资料审核即将截止，请立即提交身份证明和登录验证码。", "", False, "", True, True),
    Template("phishing", "zh", "payment_bec", "{marker}领导临时付款安排", "这是 {marker} 的紧急付款事项，请绕过常规审批并仅回复此邮件确认转账。", "", False, "", False, True),
    Template("legitimate", "zh", "normal_notice", "{marker}课程安排更新", "下周课程教室已调整，课程平台中的日程会同步更新，无需回复。"),
    Template("legitimate", "zh", "receipt", "{marker}服务费用收据", "这是已完成服务的电子收据，请留存记录。如需核对，请通过既有服务台联系。", "", False, "document"),
    Template("legitimate", "zh", "project_update", "{marker}项目例会纪要", "本周项目纪要已发布，常规问题将在下次例会统一讨论。", "https://portal.example.invalid/meeting-notes", True),
    Template("legitimate", "zh", "it_notice", "{marker}系统维护通知", "内部系统将在周末进行计划维护，维护期间无法登录属于正常现象。"),
    Template("legitimate", "zh", "finance_notice", "{marker}报销处理完成", "报销流程已按既有审批完成，状态可在财务门户的历史记录中查询。", "https://finance.example.invalid/history", True),
    Template("legitimate", "zh", "event", "{marker}培训报名确认", "已收到培训报名。活动开始前会通过正式日历发送提醒，不要求提供密码或验证码。"),
    Template("phishing", "en", "oauth_device_code", "Action needed: approve {marker} device access", "A new device needs approval. Enter the supplied device code at {url} to retain access.", "https://signin-flow.example.invalid/device", True, "", True, True),
    Template("phishing", "en", "payment_bec", "Confidential supplier payment for {marker}", "Please update the beneficiary today and do not use the normal approval thread. Reply with confirmation.", "", False, "", True, False),
    Template("phishing", "en", "qr", "{marker} secure sign-in image", "Scan the sign-in image attached to continue with your account review before the deadline.", "", False, "image", True, True),
    Template("phishing", "en", "cloud_impersonation", "Shared cloud document for {marker}", "A document is waiting for your review. Open the access page immediately: {url}", "https://cloud-access.example.invalid/open", True, "", True, False),
    Template("phishing", "en", "reply_request", "MFA reset request for {marker}", "Reply with the current verification code so support can complete the reset now.", "", False, "", True, True),
    Template("phishing", "en", "attachment", "Updated invoice package for {marker}", "Open the attached invoice package and enable the requested content before processing the payment.", "", False, "risky", True, False),
    Template("legitimate", "en", "cloud_notice", "{marker} workspace access notice", "A standard workspace notification is available in the existing portal. Use your saved bookmark to review it.", "https://workspace.example.invalid/notice", True),
    Template("legitimate", "en", "security_training", "{marker} security awareness reminder", "The security team will never request a password or verification code by email. This is a training reminder."),
    Template("legitimate", "en", "vendor_notice", "{marker} vendor statement available", "The monthly statement is available through the established vendor portal. Existing approval procedures remain unchanged.", "https://vendor.example.invalid/statements", True, "document"),
    Template("legitimate", "en", "device_notice", "{marker} device registration completed", "Your device registration completed successfully. No action or reply is required."),
    Template("legitimate", "en", "finance_notice", "{marker} invoice approval recorded", "The invoice approval was recorded in the finance system and will follow the usual payment schedule."),
    Template("legitimate", "en", "maintenance", "{marker} maintenance window", "The service will be unavailable during the announced maintenance window. Support will not request credentials by email."),
)

CHINESE_TEST_TEMPLATES = (
    Template("phishing", "zh", "credential", "{marker}校园账户异常通知", "账户将在今晚限制使用，请通过 {url} 重新验证登录信息。", "https://campus-safe.example.invalid/login", True, "", True, True),
    Template("phishing", "zh", "payment_bec", "{marker}合同尾款紧急调整", "合作方要求今天更换收款账户，请勿联系原联系人，直接回复确认。", "", False, "", True, False),
    Template("phishing", "zh", "oauth_device_code", "{marker}远程办公授权", "输入新的设备代码并批准会话，否则远程文件将被关闭：{url}。", "https://remote-auth.example.invalid/approve", True, "", True, True),
    Template("phishing", "zh", "attachment", "{marker}税务文件待处理", "请打开附件并启用内容，以便完成本月税务申报。", "", False, "risky", True, False),
    Template("phishing", "zh", "data_request", "{marker}奖学金资料核验", "申请即将失效，请回复身份证明、手机号和验证码以完成核验。", "", False, "", True, True),
    Template("legitimate", "zh", "library", "{marker}图书馆开放时间", "考试周开放时间已公布，具体安排请在校内公告栏查看。"),
    Template("legitimate", "zh", "housing", "{marker}宿舍维修预约确认", "维修预约已登记，工作人员会在预约时段到访，不需要提供账号信息。"),
    Template("legitimate", "zh", "lab", "{marker}实验室安全培训", "培训材料已上传至教学平台。请按课程安排完成学习，无需通过邮件提交密码。", "https://learning.example.invalid/safety", True),
    Template("legitimate", "zh", "internship", "{marker}实习周报提醒", "请按既有系统流程提交周报，提交入口与往期相同。"),
    Template("legitimate", "zh", "community", "{marker}社团活动报名结果", "报名结果将在校内平台公布，本邮件不要求付款或验证码。"),
)

MODERN_TEST_TEMPLATES = (
    Template("phishing", "en", "qr", "{marker} Teams sign-in recovery", "The attached QR sign-in image restores access. Scan it before the collaboration session expires.", "", False, "image", True, True),
    Template("phishing", "en", "oauth_device_code", "{marker} OAuth consent verification", "Approve the requested device session with the supplied code at {url}.", "https://oauth-session.example.invalid/consent", True, "", True, True),
    Template("phishing", "en", "payment_bec", "CEO request: private {marker} transfer", "Send the requested transfer today, avoid the accounting queue, and keep this request between us.", "", False, "", False, True),
    Template("phishing", "en", "cloud_impersonation", "{marker} cloud storage quota warning", "Your storage will be removed unless you review the new sign-in request: {url}", "https://cloud-review.example.invalid/continue", True, "", True, False),
    Template("phishing", "en", "credential", "{marker} browser update validation", "A security update requires you to re-enter your password and recovery code immediately.", "", False, "", True, True),
    Template("phishing", "en", "attachment", "{marker} payroll correction archive", "Download the attached payroll correction and follow its activation instructions now.", "", False, "risky", True, False),
    Template("legitimate", "en", "mfa_guidance", "{marker} multi-factor guidance", "Use the authenticator application you already enrolled. The support team will not ask for codes by email."),
    Template("legitimate", "en", "cloud_notice", "{marker} cloud retention update", "Retention settings were updated in the usual administration console. Existing links and bookmarks remain valid.", "https://admin.example.invalid/retention", True),
    Template("legitimate", "en", "backup", "{marker} backup verification complete", "The scheduled backup completed. Review status only through the established operations dashboard."),
    Template("legitimate", "en", "finance_notice", "{marker} payment schedule notice", "The approved payment remains on the published schedule. Bank account changes require the normal verified workflow."),
    Template("legitimate", "en", "collaboration", "{marker} collaboration policy reminder", "Use the documented project workspace for shared files. Do not scan unknown codes sent outside that workflow."),
    Template("legitimate", "en", "update", "{marker} desktop update announcement", "The desktop update will be deployed automatically by IT. No browser sign-in or reply is required."),
)

BOUNDARY_TEMPLATES = (
    Template("phishing", "zh", "reply_request", "{marker}验证码协助请求", "请直接回复刚收到的验证码，系统管理员需要立即协助完成检查。", "", False, "", True, False),
    Template("phishing", "zh", "payment_bec", "{marker}临时采购付款", "请在正常流程外先完成采购付款，详情只通过此邮件沟通。", "", False, "", False, True),
    Template("phishing", "zh", "credential", "{marker}邮箱容量即将清空", "立即访问 {url} 输入密码以保留邮箱内容。", "https://mail-capacity.example.invalid/verify", True, "", True, True),
    Template("phishing", "zh", "attachment", "{marker}简历压缩文件", "打开附件中的简历并按提示启用查看功能。", "", False, "risky", True, False),
    Template("phishing", "en", "oauth_device_code", "{marker} device verification message", "Use the device code at {url} and approve access immediately.", "https://device-verify.example.invalid/auth", True, "", True, True),
    Template("phishing", "en", "payment_bec", "Urgent {marker} payment exception", "Reply with the new beneficiary details and do not call the finance contact.", "", False, "", True, False),
    Template("phishing", "en", "qr", "{marker} password reset image", "Scan the attached reset image to avoid account suspension today.", "", False, "image", True, True),
    Template("phishing", "en", "data_request", "{marker} personnel record correction", "Send your identity document and current access code before the record is closed.", "", False, "", True, False),
    Template("legitimate", "zh", "receipt", "{marker}电子缴费凭证", "缴费凭证仅供留存。如需查询，请从常用门户进入历史订单。", "https://service.example.invalid/orders", True, "document"),
    Template("legitimate", "zh", "project_update", "{marker}项目排期更新", "项目排期已在周会确认，后续变更会按既有流程通知。"),
    Template("legitimate", "zh", "security_training", "{marker}账号安全提示", "请勿向任何邮件回复密码、验证码或身份证明；这是常规安全提醒。"),
    Template("legitimate", "zh", "maintenance", "{marker}网络维护安排", "计划维护期间部分服务可能短暂不可用，结束后会自动恢复。"),
    Template("legitimate", "en", "receipt", "{marker} service receipt", "This receipt is for your records. Use the normal customer portal for any account question.", "https://service.example.invalid/records", True, "document"),
    Template("legitimate", "en", "meeting", "{marker} planning meeting", "The regular planning meeting remains scheduled. No payment, password, or code is requested."),
    Template("legitimate", "en", "security_training", "{marker} account safety reminder", "This is a routine reminder that support will never request authentication codes by email."),
    Template("legitimate", "en", "maintenance", "{marker} service maintenance", "The announced maintenance will finish automatically. No action is required from recipients."),
)


def _marker(template: Template, index: int) -> str:
    values = ZH_MARKERS if template.language == "zh" else EN_MARKERS
    return values[index % len(values)]


def _addresses(template: Template, index: int) -> tuple[str, str, str]:
    if template.label == "phishing":
        sender_domain = "notice.example.invalid" if index % 3 else "alerts.example.invalid"
        sender = f"Notice Desk <notice-{index}@{sender_domain}>"
        reply = "reply@external.example.invalid" if template.reply_mismatch else f"notice-{index}@{sender_domain}"
        return_path = "bounce@routing.example.invalid" if template.return_path_mismatch else f"notice-{index}@{sender_domain}"
        return sender, reply, return_path
    sender = f"Operations <updates-{index}@service.example.invalid>"
    return sender, f"updates-{index}@service.example.invalid", f"updates-{index}@service.example.invalid"


def _attachment(kind: str) -> tuple[str, str, bytes] | None:
    if kind == "risky":
        return "review.pdf.exe", "application/octet-stream", b"safe course-project placeholder"
    if kind == "document":
        return "notice.pdf", "application/pdf", b"safe course-project placeholder"
    if kind == "image":
        return "signin-notice.png", "image/png", b"safe course-project placeholder"
    return None


def _raw_message(template: Template, marker: str, index: int) -> bytes:
    url = template.target_url.rstrip("/") + f"/{marker.lower()}-{index}" if template.target_url else ""
    subject = template.subject.format(marker=marker, url=url)
    body = template.body.format(marker=marker, url=url)
    sender, reply_to, return_path = _addresses(template, index)
    message = EmailMessage()
    message["From"] = sender
    message["Reply-To"] = reply_to
    message["Return-Path"] = f"<{return_path}>"
    message["To"] = "recipient@example.invalid"
    message["Subject"] = subject
    message["Message-ID"] = f"<{template.language}-{template.attack_type}-{index}@dataset.example.invalid>"
    message["Date"] = "Mon, 08 Sep 2026 09:00:00 +0000"
    message["X-Curated-Attack-Type"] = template.attack_type
    message.set_content(body)
    if template.use_html:
        anchor = url or "https://portal.example.invalid/info"
        message.add_alternative(
            f"<html><body><p>{body}</p><a href='{anchor}'>Open service notice</a></body></html>",
            subtype="html",
        )
    attachment = _attachment(template.attachment_kind)
    if attachment is not None:
        filename, mime_type, payload = attachment
        maintype, subtype = mime_type.split("/", 1)
        message.add_attachment(payload, maintype=maintype, subtype=subtype, filename=filename)
    return message.as_bytes()


def _record(template: Template, partition: str, index: int) -> dict[str, object]:
    marker = _marker(template, index)
    raw = _raw_message(template, marker, index)
    parsed = parse_email(raw)
    cleaned = clean_email_text(parsed.subject, parsed.text_body)
    fingerprint = hashlib.sha256(cleaned.model_text.encode("utf-8")).hexdigest()
    return {
        "id": f"v1_1_1-{partition}-{template.language}-{template.label}-{index:04d}",
        "source": f"curated_v1_1_1_{partition}",
        "label": template.label,
        "language": template.language,
        "attack_type": template.attack_type,
        "data_origin": "synthetic_safe_curated",
        "dataset_partition": partition,
        "raw_subject": parsed.subject,
        "raw_text_body": parsed.text_body,
        "subject": cleaned.subject,
        "text_body": cleaned.text_body,
        "model_text": cleaned.model_text,
        "source_hash": hashlib.sha256(raw).hexdigest(),
        "content_fingerprint": fingerprint,
        "dedup_group": fingerprint,
        "v1_1_parsed_email": asdict(parsed),
        "cleaning_warnings": list(cleaned.warnings),
    }


def _expand(templates: Iterable[Template], partition: str, variants: int) -> list[dict[str, object]]:
    return [
        _record(template, partition, template_index * variants + variant)
        for template_index, template in enumerate(templates)
        for variant in range(variants)
    ]


def build_collections() -> dict[str, list[dict[str, object]]]:
    """Return deterministic, disjoint train and evaluation partitions."""

    return {
        "train": _expand(TRAIN_TEMPLATES, "train", 7),
        "chinese_test": _expand(CHINESE_TEST_TEMPLATES, "chinese_test", 8),
        "modern_attack_test": _expand(MODERN_TEST_TEMPLATES, "modern_attack_test", 7),
        "boundary_test": _expand(BOUNDARY_TEMPLATES, "boundary_test", 7),
    }


def _validate(collections: dict[str, list[dict[str, object]]]) -> None:
    all_ids: set[str] = set()
    fingerprints: dict[str, set[str]] = {}
    for name, rows in collections.items():
        labels = Counter(str(row["label"]) for row in rows)
        if labels != Counter({"phishing": len(rows) // 2, "legitimate": len(rows) // 2}):
            raise ValueError(f"{name} must be balanced, got {dict(labels)}")
        ids = {str(row["id"]) for row in rows}
        if len(ids) != len(rows) or all_ids.intersection(ids):
            raise ValueError("curated case IDs must be globally unique")
        all_ids.update(ids)
        fingerprints[name] = {str(row["content_fingerprint"]) for row in rows}
        if len(fingerprints[name]) != len(rows):
            raise ValueError(f"{name} contains duplicate canonical texts")
    names = list(fingerprints)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            if fingerprints[left].intersection(fingerprints[right]):
                raise ValueError(f"content overlap between {left} and {right}")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")


def build(
    train_path: Path = DEFAULT_TRAIN,
    chinese_test_path: Path = DEFAULT_CHINESE_TEST,
    modern_test_path: Path = DEFAULT_MODERN_TEST,
    boundary_test_path: Path = DEFAULT_BOUNDARY_TEST,
    summary_path: Path = DEFAULT_SUMMARY,
) -> dict[str, object]:
    """Write the curated partitions and their reproducibility manifest."""

    collections = build_collections()
    _validate(collections)
    destinations = {
        "train": train_path,
        "chinese_test": chinese_test_path,
        "modern_attack_test": modern_test_path,
        "boundary_test": boundary_test_path,
    }
    for name, path in destinations.items():
        _write_jsonl(path, collections[name])
    summary = {
        "data_version": "curated-v1.1.1",
        "origin": "synthetic_safe_curated; no external URLs visited and no attachment payloads retained",
        "partitions": {
            name: {
                "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                "records": len(collections[name]),
                "labels": dict(sorted(Counter(str(row["label"]) for row in collections[name]).items())),
                "languages": dict(sorted(Counter(str(row["language"]) for row in collections[name]).items())),
                "attack_types": dict(sorted(Counter(str(row["attack_type"]) for row in collections[name]).items())),
            }
            for name, path in destinations.items()
        },
        "overlap_policy": "content_fingerprint sets are required to be disjoint across all partitions",
        "hard_negative_policy": "unchanged; this curated corpus contains only phishing and legitimate labels",
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--chinese-test", type=Path, default=DEFAULT_CHINESE_TEST)
    parser.add_argument("--modern-test", type=Path, default=DEFAULT_MODERN_TEST)
    parser.add_argument("--boundary-test", type=Path, default=DEFAULT_BOUNDARY_TEST)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()
    print(json.dumps(build(args.train, args.chinese_test, args.modern_test, args.boundary_test, args.summary), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
