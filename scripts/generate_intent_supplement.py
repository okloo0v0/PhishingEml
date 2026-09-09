"""Generate safe, explicitly synthetic intent examples for branch coverage."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())

TEMPLATES: dict[str, tuple[str, ...]] = {
    "benign_notice": (
        "Automated notice: your monthly statement is available for your records. No action is required.",
        "系统通知：本月对账单已生成，仅供你留存查看，无需任何操作。",
        "Service update completed successfully. This message is informational only; please do not reply.",
        "会议纪要已归档，供你参考。本邮件不要求回复，也不会索取验证码或密码。",
    ),
    "oauth_authorization": (
        "Approve the sign-in request using the displayed device code {code}.",
        "请使用设备代码 {code} 批准本次登录授权。",
        "Authorize the connected application to continue the account setup.",
        "在继续之前，请批准该应用访问你的工作账户。",
    ),
    "credential_request": (
        "Reply with your password and verification code to complete the review.",
        "请回复密码和验证码，以完成账户审核。",
        "Enter your security code in the verification form to avoid suspension.",
        "请提供登录信息和一次性验证码，我们才能恢复访问。",
    ),
    "external_document_action": (
        "Download the shared document from the secure file portal at https://files.example.invalid/{token}.",
        "请打开共享云文档 https://docs.example.invalid/{token} 查看并确认内容。",
        "Enable macros in the attached spreadsheet to display the updated report.",
        "请下载附件并打开文档，以完成项目资料确认。",
    ),
    "payment_change": (
        "Please change the beneficiary bank account before the next wire transfer.",
        "请在下一笔付款前将收款账户更改为新账户。",
        "The invoice is updated; send payment to the replacement account listed below.",
        "发票信息已更新，请将本次款项转入新的收款账户。",
    ),
}


def generate(output: Path, per_intent: int = 200, seed: int = 42) -> dict[str, object]:
    rng = random.Random(seed)
    rows: list[dict[str, object]] = []
    for intent, templates in TEMPLATES.items():
        for index in range(per_intent):
            text = rng.choice(templates).format(code=f"{rng.randint(100000, 999999)}", token=f"{rng.randint(1000, 9999)}")
            subject = {
                "benign_notice": "Automated notice",
                "oauth_authorization": "Sign-in authorization required",
                "credential_request": "Account verification",
                "external_document_action": "Shared document update",
                "payment_change": "Payment instruction update",
            }[intent]
            rows.append({
                "id": f"synthetic-intent-{intent}-{index:04d}",
                "source": "synthetic_intent_v1",
                "label": "legitimate" if intent == "benign_notice" else "phishing",
                "subject": subject,
                "text_body": text,
                "content_fingerprint": f"synthetic-{intent}-{index:04d}",
                "intent_labels": [intent],
                "intent_label_provenance": "synthetic_template_v1",
                "data_origin": "synthetic_template",
            })
    rng.shuffle(rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"output_path": _display_path(output), "record_count": len(rows), "per_intent": per_intent, "data_origin": "synthetic_template", "seed": seed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/v1.2/processed/intent_supplement_synthetic.jsonl")
    parser.add_argument("--per-intent", type=int, default=200)
    args = parser.parse_args()
    print(json.dumps(generate(args.output, args.per_intent), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
