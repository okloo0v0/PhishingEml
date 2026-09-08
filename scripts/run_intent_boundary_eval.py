"""Run manually labeled intent boundary cases against the V1.2 branch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Manually authored and labeled pairs. They are calibration cases, never training rows.
CASES = [
    ("benign_mfa_en", "MFA reminder", "Support will never ask for your verification code. No action is required.", ["benign_notice"]),
    ("benign_mfa_zh", "多因素认证提醒", "客服不会通过邮件索取验证码，本通知无需操作。", ["benign_notice"]),
    ("benign_payment_en", "Payment receipt", "Payment was received and the beneficiary account has not changed.", ["benign_notice"]),
    ("benign_payment_zh", "付款完成通知", "款项已到账，收款账户没有变更，本邮件仅供参考。", ["benign_notice"]),
    ("benign_doc_en", "Document notice", "The file is archived in the usual company portal. No email action is required.", ["benign_notice"]),
    ("benign_doc_zh", "文档归档通知", "文件已归档至公司正常渠道，无需下载附件或回复。", ["benign_notice"]),
    ("benign_login_en", "Sign-in completed", "A sign-in completed. Contact support through the normal channel if unfamiliar.", ["benign_notice"]),
    ("benign_login_zh", "登录完成通知", "登录已经完成，如非本人操作请通过正常渠道联系支持。", ["benign_notice"]),
    ("benign_invoice_en", "Invoice processed", "Invoice 4815 was processed successfully for your records. No action is required.", ["benign_notice"]),
    ("benign_invoice_zh", "发票处理完成", "发票已处理完成，仅供留存，无需回复或付款。", ["benign_notice"]),
    ("credential_en_1", "Account review", "Send your password and verification code to complete the review.", ["credential_request"]),
    ("credential_en_2", "Mailbox validation", "Enter the one-time passcode in the verification form today.", ["credential_request"]),
    ("credential_en_3", "Security check", "Reply with your login credentials so access can be restored.", ["credential_request", "reply_or_data_request"]),
    ("credential_zh_1", "账户审核", "请发送密码和验证码以完成账户审核。", ["credential_request"]),
    ("credential_zh_2", "邮箱验证", "请在验证表单中填写一次性口令。", ["credential_request"]),
    ("credential_zh_3", "安全检查", "请回复登录信息，以便恢复账户访问。", ["credential_request", "reply_or_data_request"]),
    ("oauth_en_1", "Device login", "Approve the sign-in request with device code 483921.", ["oauth_authorization"]),
    ("oauth_en_2", "Application consent", "Authorize this application to access your work account.", ["oauth_authorization"]),
    ("oauth_en_3", "Consent pending", "Grant OAuth consent to continue with the shared workspace.", ["oauth_authorization"]),
    ("oauth_zh_1", "设备登录", "请使用设备代码 483921 批准本次登录。", ["oauth_authorization"]),
    ("oauth_zh_2", "应用授权", "请授权此应用访问你的工作账户。", ["oauth_authorization"]),
    ("oauth_zh_3", "授权待处理", "请批准应用授权后继续访问共享空间。", ["oauth_authorization"]),
    ("payment_en_1", "Bank detail update", "Change the beneficiary account before the next transfer.", ["payment_change"]),
    ("payment_en_2", "Revised invoice", "Use the replacement bank account for this invoice payment.", ["payment_change"]),
    ("payment_en_3", "Urgent transfer", "Immediately wire the funds to the new account and keep this confidential.", ["payment_change", "social_pressure"]),
    ("payment_zh_1", "收款信息更新", "请在下一笔转账前更改收款账户。", ["payment_change"]),
    ("payment_zh_2", "发票已修订", "本次付款请使用新的银行账户。", ["payment_change"]),
    ("payment_zh_3", "紧急转账", "请立即将款项转入新账户并对本次操作保密。", ["payment_change", "social_pressure"]),
    ("document_en_1", "Shared file", "Download the shared file from https://docs.example.invalid/4815.", ["external_document_action"]),
    ("document_en_2", "Spreadsheet update", "Open the attachment and enable macros to view the report.", ["external_document_action"]),
    ("document_en_3", "Cloud document", "Review the external cloud document and confirm its contents.", ["external_document_action"]),
    ("document_zh_1", "共享文件", "请从 https://docs.example.invalid/4815 下载共享文件。", ["external_document_action"]),
    ("document_zh_2", "表格更新", "请打开附件并启用宏以查看报告。", ["external_document_action"]),
    ("document_zh_3", "云文档", "请访问外部云文档并确认其中内容。", ["external_document_action"]),
    ("reply_en_1", "Employee details", "Reply with your employee number and current address.", ["reply_or_data_request"]),
    ("reply_en_2", "Confirmation needed", "Respond with the requested contact details by email.", ["reply_or_data_request"]),
    ("reply_en_3", "Private request", "Send me the project roster and do not discuss this request.", ["reply_or_data_request", "social_pressure"]),
    ("reply_zh_1", "员工信息", "请回复你的员工编号和当前地址。", ["reply_or_data_request"]),
    ("reply_zh_2", "需要确认", "请通过邮件提供所需联系方式。", ["reply_or_data_request"]),
    ("reply_zh_3", "保密请求", "请把项目名单发送给我，并且不要讨论此请求。", ["reply_or_data_request", "social_pressure"]),
    ("pressure_en_1", "Final warning", "Act immediately; this is the final warning before suspension.", ["social_pressure"]),
    ("pressure_en_2", "Confidential", "Keep this private and do not call anyone about it.", ["social_pressure"]),
    ("pressure_en_3", "Director request", "The director needs this handled within 24 hours outside the normal process.", ["social_pressure"]),
    ("pressure_zh_1", "最后通知", "请立即处理，这是停用前的最后通知。", ["social_pressure"]),
    ("pressure_zh_2", "保密事项", "此事需要保密，不要电话确认。", ["social_pressure"]),
    ("pressure_zh_3", "领导要求", "领导要求在 24 小时内绕过正常流程完成。", ["social_pressure"]),
]


def evaluate(model_path: Path, output_path: Path, thresholds: dict[str, float] | None = None) -> dict[str, object]:
    model = joblib.load(model_path)
    rows = [{"subject": subject, "text_body": body} for _, subject, body, _ in CASES]
    probabilities = model.predict_proba(rows)
    predicted = model.predict_labels(rows, thresholds)
    results = []
    exact = 0
    for (case_id, _, _, expected), labels, values in zip(CASES, predicted, probabilities):
        is_exact = set(labels) == set(expected)
        exact += is_exact
        results.append({"case_id": case_id, "expected_intents": expected, "predicted_intents": labels, "exact_match": is_exact, "probabilities": {name: round(float(value), 4) for name, value in zip(model.classes_, values)}})
    report = {"model_path": str(model_path), "case_count": len(results), "exact_match_count": exact, "exact_match_rate": exact / len(results), "thresholds": thresholds or {name: 0.5 for name in model.classes_}, "results": results, "note": "manually labeled fixed boundary cases; excluded from training"}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=ROOT / "models/intent_branch_v1_2.joblib")
    parser.add_argument("--output", type=Path, default=ROOT / "data/v1.2/manifests/intent_boundary_eval.json")
    parser.add_argument("--thresholds", type=Path)
    args = parser.parse_args()
    thresholds = json.loads(args.thresholds.read_text(encoding="utf-8"))["thresholds"] if args.thresholds else None
    print(json.dumps(evaluate(args.model, args.output, thresholds), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
