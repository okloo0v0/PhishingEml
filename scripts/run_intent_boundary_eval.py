"""Run fixed intent boundary cases against the current V1.2 branch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES = [
    ("benign_mfa_notice", "MFA notice", "We will never ask for your verification code by email. No action is required.", ["benign_notice"]),
    ("credential_request", "MFA verification", "Reply with your verification code to complete the account review.", ["credential_request"]),
    ("benign_payment_notice", "Payment completed", "Your payment was received. The beneficiary account has not changed.", ["benign_notice"]),
    ("payment_change", "Updated payment details", "Please change the beneficiary bank account before sending payment.", ["payment_change"]),
    ("benign_document_notice", "Document shared", "A document was shared with you. Review it through your usual company portal.", ["benign_notice"]),
    ("external_document_action", "Document download", "Download the shared document from https://docs.example.invalid/file.", ["external_document_action"]),
    ("benign_login_notice", "Sign-in notice", "A sign-in was completed. If this was not you, use the normal support channel.", ["benign_notice"]),
    ("oauth_authorization", "Approve sign-in", "Approve sign-in using the device code 123456.", ["oauth_authorization"]),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=ROOT / "models/intent_branch_v1_2.joblib")
    parser.add_argument("--output", type=Path, default=ROOT / "data/v1.2/manifests/intent_boundary_eval.json")
    args = parser.parse_args()
    model = joblib.load(args.model)
    rows = [{"subject": subject, "text_body": body} for _, subject, body, _ in CASES]
    probabilities = model.predict_proba(rows)
    results = []
    for (case_id, _, _, expected), values in zip(CASES, probabilities):
        predicted = [name for name, value in zip(model.classes_, values) if value >= 0.5]
        results.append({"case_id": case_id, "expected_intents": expected, "predicted_intents": predicted, "probabilities": {name: round(float(value), 4) for name, value in zip(model.classes_, values)}})
    output = {"model_path": str(args.model), "case_count": len(results), "results": results, "note": "fixed boundary cases; not a generalization estimate"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
