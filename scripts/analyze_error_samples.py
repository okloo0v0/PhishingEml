"""Analyze model errors with non-sensitive structural features only."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTIONS = ROOT / "data" / "processed" / "evaluation_predictions.csv"
DEFAULT_DATA = ROOT / "data" / "processed" / "emails.csv"
DEFAULT_CROSS_SOURCE = ROOT / "data" / "processed" / "cross_source_test.jsonl"
DEFAULT_MODEL = ROOT / "models" / "phishing_model.joblib"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "error_analysis.csv"
DEFAULT_SUMMARY = ROOT / "data" / "manifests" / "error_analysis_summary.json"


def _read_csv(path: Path) -> list[dict[str, str]]:
    csv.field_size_limit(2**31 - 1)
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def analyze(
    predictions_path: Path,
    data_path: Path,
    model_path: Path,
    output_path: Path,
    summary_path: Path,
    cross_source_path: Path = DEFAULT_CROSS_SOURCE,
) -> dict[str, object]:
    predictions = _read_csv(predictions_path)
    rows = {row["id"]: row for row in _read_csv(data_path)}
    rows.update({str(row["id"]): row for row in _read_jsonl(cross_source_path)})
    errors = [row for row in predictions if row["dataset"] in {"test", "cross_source_test"} and row["is_error"] == "True"]
    output_rows: list[dict[str, object]] = []
    for error in errors:
        source = rows.get(error["id"], {})
        text = str(source.get("model_text", "") or "")
        subject = str(source.get("subject", "") or "")
        probability = float(error["phishing_probability"])
        output_rows.append({
            "dataset": error["dataset"], "id": error["id"], "source": error["source"],
            "label": error["label"], "predicted_label": error["predicted_label"],
            "phishing_probability": probability, "error_type": error["error_type"],
            "subject_chars": len(subject), "model_text_chars": len(text),
            "token_count": len(text.split()), "email_placeholder_count": text.count("<EMAIL>"),
            "url_placeholder_count": text.count("<URL>"), "number_placeholder_count": text.count("<NUMBER>"),
            "has_non_ascii": any(ord(char) > 127 for char in text),
            "probability_bucket": f"{int(probability * 10) / 10:.1f}-{int(probability * 10) / 10 + 0.1:.1f}",
        })
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(output_rows[0]) if output_rows else ["dataset", "id", "source", "label", "predicted_label", "phishing_probability", "error_type"]
    with output_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)
    model = joblib.load(model_path)
    classifier = model.named_steps["classifier"]
    vocabulary = model.named_steps["tfidf"].get_feature_names_out()
    coefficients = classifier.coef_[0]
    top_phishing = [str(vocabulary[index]) for index in coefficients.argsort()[-20:][::-1]]
    top_legitimate = [str(vocabulary[index]) for index in coefficients.argsort()[:20]]
    summary = {
        "prediction_input": predictions_path.relative_to(ROOT).as_posix(),
        "data_inputs": [
            data_path.relative_to(ROOT).as_posix(),
            cross_source_path.relative_to(ROOT).as_posix(),
        ],
        "error_output": output_path.relative_to(ROOT).as_posix(),
        "error_count": len(output_rows),
        "error_counts": dict(sorted(Counter(row["error_type"] for row in output_rows).items())),
        "by_dataset": dict(sorted(Counter(row["dataset"] for row in output_rows).items())),
        "by_source": dict(sorted(Counter(row["source"] for row in output_rows).items())),
        "by_label": dict(sorted(Counter(row["label"] for row in output_rows).items())),
        "length_buckets": dict(sorted(Counter("short" if row["model_text_chars"] < 500 else "medium" if row["model_text_chars"] < 5000 else "long" for row in output_rows).items())),
        "placeholder_presence": {
            "email": sum(row["email_placeholder_count"] > 0 for row in output_rows),
            "url": sum(row["url_placeholder_count"] > 0 for row in output_rows),
            "number": sum(row["number_placeholder_count"] > 0 for row in output_rows),
            "non_ascii": sum(row["has_non_ascii"] for row in output_rows),
        },
        "top_global_phishing_features": top_phishing,
        "top_global_legitimate_features": top_legitimate,
        "privacy_note": "No subject, body, URL, address, or attachment payload is written to the analysis output.",
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--cross-source", type=Path, default=DEFAULT_CROSS_SOURCE)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()
    print(json.dumps(analyze(args.predictions, args.data, args.model, args.output, args.summary, args.cross_source), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
