"""Create a manually adjudicated seven-intent split from the external holdout."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Human adjudication of the fixed 100-row external sample. Labels describe the
# requested action, not merely words appearing in the message.
MANUAL_LABELS: dict[int, list[str]] = {
    0: [], 1: ["credential_request", "reply_or_data_request", "social_pressure"], 2: [],
    3: ["credential_request", "social_pressure"], 4: ["credential_request", "reply_or_data_request"],
    5: [], 6: [], 7: [], 8: [], 9: ["credential_request", "social_pressure"],
    10: ["credential_request", "social_pressure"], 11: [], 12: ["external_document_action"],
    13: [], 14: [], 15: ["payment_change", "reply_or_data_request"],
    16: ["credential_request", "reply_or_data_request"], 17: [], 18: ["credential_request", "social_pressure"],
    19: ["reply_or_data_request", "social_pressure"], 20: ["benign_notice"],
    21: ["credential_request", "reply_or_data_request"], 22: [], 23: ["credential_request", "social_pressure"],
    24: ["credential_request", "external_document_action", "social_pressure"], 25: [],
    26: ["external_document_action", "social_pressure"], 27: ["reply_or_data_request"], 28: [],
    29: ["reply_or_data_request"], 30: ["credential_request", "social_pressure"],
    31: ["credential_request", "external_document_action", "social_pressure"], 32: [],
    33: ["payment_change", "reply_or_data_request"], 34: ["credential_request", "external_document_action"],
    35: ["credential_request", "oauth_authorization", "social_pressure"], 36: ["external_document_action"],
    37: [], 38: ["reply_or_data_request"], 39: ["credential_request", "social_pressure"],
    40: [], 41: [], 42: [], 43: [], 44: ["credential_request", "social_pressure"],
    45: [], 46: ["benign_notice"], 47: ["reply_or_data_request"], 48: [],
    49: ["credential_request", "external_document_action", "social_pressure"], 50: [], 51: [],
    52: ["credential_request", "payment_change", "social_pressure"], 53: ["credential_request", "social_pressure"],
    54: [], 55: [], 56: ["external_document_action", "social_pressure"], 57: [], 58: [],
    59: ["reply_or_data_request"], 60: ["credential_request", "payment_change", "social_pressure"],
    61: ["credential_request", "social_pressure"], 62: ["reply_or_data_request", "social_pressure"],
    63: [], 64: ["credential_request", "social_pressure"], 65: ["credential_request", "reply_or_data_request"],
    66: ["credential_request", "social_pressure"], 67: [], 68: ["reply_or_data_request"], 69: [], 70: [], 71: [],
    72: ["credential_request", "reply_or_data_request"], 73: ["credential_request", "social_pressure"], 74: [],
    75: ["credential_request", "social_pressure"], 76: ["reply_or_data_request", "social_pressure"],
    77: ["external_document_action"], 78: ["credential_request", "social_pressure"], 79: [],
    80: ["reply_or_data_request", "social_pressure"], 81: ["credential_request", "reply_or_data_request"],
    82: ["reply_or_data_request"], 83: [], 84: ["external_document_action"],
    85: ["credential_request", "social_pressure"], 86: [], 87: ["reply_or_data_request", "social_pressure"],
    88: [], 89: [], 90: [], 91: ["credential_request", "reply_or_data_request"], 92: [],
    93: ["benign_notice"], 94: ["reply_or_data_request"], 95: [], 96: ["payment_change", "reply_or_data_request"],
    97: ["reply_or_data_request", "social_pressure"], 98: [], 99: ["credential_request", "social_pressure"],
}


def annotate(input_path: Path, labeled_path: Path, train_path: Path, test_path: Path, *, seed: int = 1202) -> dict[str, object]:
    rows = [json.loads(line) for line in input_path.open(encoding="utf-8") if line.strip()]
    if len(rows) != len(MANUAL_LABELS):
        raise ValueError(f"expected {len(MANUAL_LABELS)} fixed rows, got {len(rows)}")
    labeled = []
    for index, row in enumerate(rows):
        labels = MANUAL_LABELS[index]
        labeled.append({**row, "manual_intent_labels": labels, "intent_labels": labels, "intent_label_provenance": "manual_adjudication_difraud_v1"})
    rng = random.Random(seed)
    shuffled = list(labeled)
    rng.shuffle(shuffled)
    split = int(len(shuffled) * 0.7)
    train_rows, test_rows = shuffled[:split], shuffled[split:]
    for path, output in ((labeled_path, labeled), (train_path, train_rows), (test_path, test_rows)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in output), encoding="utf-8")
    counts = Counter(label for row in labeled for label in row["manual_intent_labels"])
    return {"labeled_count": len(labeled), "train_count": len(train_rows), "test_count": len(test_rows), "seed": seed, "intent_counts": dict(sorted(counts.items())), "provenance": "manual_adjudication_difraud_v1"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/v1.2/processed/difraud_external_holdout.jsonl")
    parser.add_argument("--labeled", type=Path, default=ROOT / "data/v1.2/processed/difraud_manual_intents.jsonl")
    parser.add_argument("--train", type=Path, default=ROOT / "data/v1.2/processed/difraud_manual_intents_train.jsonl")
    parser.add_argument("--test", type=Path, default=ROOT / "data/v1.2/processed/difraud_manual_intents_test.jsonl")
    args = parser.parse_args()
    print(json.dumps(annotate(args.input, args.labeled, args.train, args.test), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
