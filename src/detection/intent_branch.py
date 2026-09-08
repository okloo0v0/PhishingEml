"""Behavior-intent labels and a lightweight multilabel intent predictor."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


INTENT_ONTOLOGY: dict[str, tuple[str, ...]] = {
    "credential_request": ("password", "passcode", "verification code", "security code", "密码", "验证码", "口令", "登录信息"),
    "oauth_authorization": ("oauth", "authorize", "authorization", "device code", "approve sign-in", "设备代码", "授权", "批准登录"),
    "payment_change": ("wire transfer", "bank account", "beneficiary", "payment", "invoice", "付款", "收款账户", "银行账户", "发票", "转账"),
    "external_document_action": ("shared document", "open the attachment", "download", "enable macros", "cloud document", "共享文件", "打开附件", "下载", "启用宏", "云文档"),
    "reply_or_data_request": ("reply", "respond", "send me", "provide the", "confirm by email", "回复", "回信", "发送给我", "提供", "邮件确认"),
    "social_pressure": ("urgent", "immediately", "within 24 hours", "final warning", "act now", "紧急", "立即", "马上", "限时", "最后通知", "confidential", "do not discuss", "保密"),
    "benign_notice": ("no action is required", "for your records", "this is an automated notification", "无需操作", "仅供参考", "自动通知"),
}

_ACTION_INTENTS = {"credential_request", "oauth_authorization", "payment_change", "external_document_action", "reply_or_data_request"}
_NEGATION_MARKERS = ("no action is required", "not required", "never ask", "will never ask", "do not request", "has not changed", "no change", "usual company portal", "normal support channel", "无需操作", "不会索取", "不会要求", "不要求回复", "没有变更", "正常渠道")


def infer_intent_labels(subject: str, body: str) -> tuple[list[str], str]:
    """Return weak behavior labels and a transparent provenance marker."""

    text = f"{subject or ''}\n{body or ''}".casefold()
    labels: list[str] = []
    for name, patterns in INTENT_ONTOLOGY.items():
        if any(pattern.casefold() in text for pattern in patterns):
            labels.append(name)
    if any(marker in text for marker in _NEGATION_MARKERS):
        labels = [name for name in labels if name not in _ACTION_INTENTS]
        if not labels:
            labels.append("benign_notice")
    # A benign disclaimer wins only when no action request is present.
    if "benign_notice" in labels and _ACTION_INTENTS.intersection(labels):
        labels.remove("benign_notice")
    return sorted(labels), "weak_pattern_v1"


def multilabel_matrix(rows: Sequence[dict[str, Any]]) -> np.ndarray:
    names = tuple(INTENT_ONTOLOGY)
    return np.asarray(
        [[1 if name in set(row.get("intent_labels", [])) else 0 for name in names] for row in rows],
        dtype=np.uint8,
    )


class IntentBranch:
    """Small text multilabel model used as an auxiliary fusion branch."""

    def __init__(self, *, max_features: int = 30_000, random_state: int = 42) -> None:
        self.max_features = max_features
        self.random_state = random_state

    def fit(self, rows: Sequence[dict[str, Any]]) -> "IntentBranch":
        records = list(rows)
        labels = multilabel_matrix(records)
        if not records or labels.shape[1] != len(INTENT_ONTOLOGY):
            raise ValueError("intent training rows are empty or malformed")
        self.vectorizer_ = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=self.max_features, sublinear_tf=True)
        texts = [f"{row.get('subject', '')}\n{row.get('text_body', '')}" for row in records]
        matrix = self.vectorizer_.fit_transform(texts)
        self.estimators_: dict[str, Pipeline | None] = {}
        self.constants_: dict[str, float] = {}
        for index, name in enumerate(INTENT_ONTOLOGY):
            target = labels[:, index]
            positives = int(target.sum())
            if positives < 2 or positives == len(target):
                self.estimators_[name] = None
                self.constants_[name] = float(np.mean(target))
                continue
            estimator = LogisticRegression(max_iter=500, class_weight="balanced", random_state=self.random_state)
            estimator.fit(matrix, target)
            self.estimators_[name] = estimator
            self.constants_[name] = 0.0
        self.classes_ = tuple(INTENT_ONTOLOGY)
        return self

    def predict_raw_proba(self, rows: Sequence[dict[str, Any]]) -> np.ndarray:
        """Return model-only intent probabilities before semantic guardrails."""

        if not hasattr(self, "vectorizer_"):
            raise RuntimeError("intent branch is not fitted")
        texts = [f"{row.get('subject', '')}\n{row.get('text_body', '')}" for row in rows]
        matrix = self.vectorizer_.transform(texts)
        columns = []
        for name in self.classes_:
            estimator = self.estimators_[name]
            if estimator is None:
                columns.append(np.full(len(texts), self.constants_[name], dtype=np.float64))
            else:
                columns.append(estimator.predict_proba(matrix)[:, 1])
        return np.column_stack(columns) if columns else np.empty((len(texts), 0), dtype=np.float64)

    def predict_proba(self, rows: Sequence[dict[str, Any]]) -> np.ndarray:
        """Return model probabilities with conservative semantic guardrails."""

        texts = [f"{row.get('subject', '')}\n{row.get('text_body', '')}" for row in rows]
        probabilities = self.predict_raw_proba(rows)
        for index, text in enumerate(texts):
            labels, _ = infer_intent_labels("", text)
            if labels == ["benign_notice"]:
                probabilities[index, : len(self.classes_) - 1] = np.minimum(probabilities[index, : len(self.classes_) - 1], 0.2)
                benign_index = self.classes_.index("benign_notice")
                probabilities[index, benign_index] = max(probabilities[index, benign_index], 0.8)
            for label in labels:
                if label in self.classes_:
                    intent_index = self.classes_.index(label)
                    probabilities[index, intent_index] = max(probabilities[index, intent_index], 0.8)
        return probabilities

    def predict_labels(
        self,
        rows: Sequence[dict[str, Any]],
        thresholds: dict[str, float] | None = None,
    ) -> list[list[str]]:
        """Predict labels using per-intent thresholds without producing fusion weights."""

        thresholds = thresholds or {}
        probabilities = self.predict_proba(rows)
        return [
            [name for name, value in zip(self.classes_, values) if value >= thresholds.get(name, 0.5)]
            for values in probabilities
        ]
