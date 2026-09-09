"""OOF late-fusion estimator for the V1.1 phishing model."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

import numpy as np
from scipy.optimize import minimize
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from sklearn.utils.validation import check_is_fitted

from src.detection.multiview_features import (
    select_char_text,
    select_intent_matrix,
    select_structure_matrix,
    select_word_text,
)


EXPECTED_CLASSES = ["legitimate", "phishing"]
BRANCH_NAMES = ("word", "char", "structure", "intent")


class NonNegativeLogisticRegression(ClassifierMixin, BaseEstimator):
    """Binary logistic regression with monotonic non-negative feature weights."""

    def __init__(self, *, c: float = 1.0, max_iter: int = 1000) -> None:
        self.c = c
        self.max_iter = max_iter

    def fit(self, X: np.ndarray, y: Sequence[str]):
        values = np.asarray(X, dtype=np.float64)
        labels = np.asarray([str(value) for value in y])
        if values.ndim != 2 or values.shape[0] != len(labels):
            raise ValueError("X must be a two-dimensional matrix aligned with y")
        if sorted(set(labels)) != EXPECTED_CLASSES:
            raise ValueError(f"training labels must be {EXPECTED_CLASSES}")
        actual = (labels == "phishing").astype(np.float64)
        prevalence = float(np.clip(np.mean(actual), 1e-6, 1.0 - 1e-6))
        initial = np.zeros(values.shape[1] + 1, dtype=np.float64)
        initial[0] = np.log(prevalence / (1.0 - prevalence))
        regularization = 1.0 / (max(self.c, 1e-12) * len(actual))

        def objective(parameters: np.ndarray) -> tuple[float, np.ndarray]:
            intercept = parameters[0]
            coefficients = parameters[1:]
            logits = intercept + values @ coefficients
            probabilities = 1.0 / (1.0 + np.exp(-np.clip(logits, -40.0, 40.0)))
            loss = float(np.mean(np.logaddexp(0.0, logits) - actual * logits))
            loss += 0.5 * regularization * float(coefficients @ coefficients)
            residual = probabilities - actual
            gradient = np.concatenate(
                (
                    [float(np.mean(residual))],
                    values.T @ residual / len(actual) + regularization * coefficients,
                )
            )
            return loss, gradient

        fitted = minimize(
            objective,
            initial,
            method="L-BFGS-B",
            jac=True,
            bounds=[(None, None)] + [(0.0, None)] * values.shape[1],
            options={"maxiter": self.max_iter},
        )
        if not fitted.success:
            raise ValueError(f"non-negative logistic fusion failed: {fitted.message}")
        self.intercept_ = np.asarray([fitted.x[0]], dtype=np.float64)
        self.coef_ = np.asarray([fitted.x[1:]], dtype=np.float64)
        self.classes_ = np.asarray(EXPECTED_CLASSES)
        self.n_iter_ = np.asarray([fitted.nit])
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        check_is_fitted(self, ("coef_", "intercept_", "classes_"))
        values = np.asarray(X, dtype=np.float64)
        logits = self.intercept_[0] + values @ self.coef_[0]
        phishing = 1.0 / (1.0 + np.exp(-np.clip(logits, -40.0, 40.0)))
        return np.column_stack((1.0 - phishing, phishing))

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.classes_[(self.predict_proba(X)[:, 1] >= 0.5).astype(int)]


def _text_branch(
    selector,
    *,
    analyzer: str,
    ngram_range: tuple[int, int],
    max_features: int,
    min_df: int,
    random_state: int,
) -> Pipeline:
    return Pipeline(
        [
            ("select", FunctionTransformer(selector, validate=False)),
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer=analyzer,
                    lowercase=True,
                    ngram_range=ngram_range,
                    min_df=min_df,
                    max_features=max_features,
                    sublinear_tf=True,
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=random_state,
                    solver="liblinear",
                ),
            ),
        ]
    )


def _numeric_branch(selector, random_state: int) -> Pipeline:
    return Pipeline(
        [
            ("select", FunctionTransformer(selector, validate=False)),
            ("scale", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=random_state,
                    solver="liblinear",
                ),
            ),
        ]
    )


class MultiViewPhishingClassifier(ClassifierMixin, BaseEstimator):
    """Train independent views and fuse their OOF probabilities."""

    def __init__(
        self,
        *,
        word_max_features: int = 50_000,
        char_max_features: int = 60_000,
        min_df: int = 2,
        cv_splits: int = 5,
        random_state: int = 42,
        enabled_views: tuple[str, ...] = BRANCH_NAMES,
    ) -> None:
        self.word_max_features = word_max_features
        self.char_max_features = char_max_features
        self.min_df = min_df
        self.cv_splits = cv_splits
        self.random_state = random_state
        self.enabled_views = enabled_views

    def _active_branch_names(self) -> tuple[str, ...]:
        active = tuple(self.enabled_views)
        if not active:
            raise ValueError("at least one model view must be enabled")
        if len(set(active)) != len(active) or any(name not in BRANCH_NAMES for name in active):
            raise ValueError(f"enabled_views must be unique members of {BRANCH_NAMES}")
        return active

    def _branch_templates(self) -> dict[str, Pipeline]:
        return {
            "word": _text_branch(
                select_word_text,
                analyzer="word",
                ngram_range=(1, 2),
                max_features=self.word_max_features,
                min_df=self.min_df,
                random_state=self.random_state,
            ),
            "char": _text_branch(
                select_char_text,
                analyzer="char_wb",
                ngram_range=(3, 5),
                max_features=self.char_max_features,
                min_df=self.min_df,
                random_state=self.random_state,
            ),
            "structure": _numeric_branch(select_structure_matrix, self.random_state),
            "intent": _numeric_branch(select_intent_matrix, self.random_state),
        }

    @staticmethod
    def _phishing_probability(estimator: Pipeline, records: Sequence[dict[str, Any]]) -> np.ndarray:
        classes = [str(value) for value in estimator.classes_]
        return estimator.predict_proba(records)[:, classes.index("phishing")]

    def fit(self, X: Sequence[dict[str, Any]], y: Sequence[str]):
        records = list(X)
        labels = np.asarray([str(value) for value in y])
        if len(records) != len(labels) or not records:
            raise ValueError("X and y must contain the same non-zero number of records")
        if sorted(set(labels)) != EXPECTED_CLASSES:
            raise ValueError(f"training labels must be {EXPECTED_CLASSES}")

        smallest_class = min(Counter(labels).values())
        splits = min(self.cv_splits, smallest_class)
        if splits < 2:
            raise ValueError("each class needs at least two records for OOF fusion")

        templates = self._branch_templates()
        active_branches = self._active_branch_names()
        oof_probabilities = np.zeros((len(records), len(active_branches)), dtype=np.float64)
        folds = StratifiedKFold(n_splits=splits, shuffle=True, random_state=self.random_state)
        dummy = np.zeros(len(records), dtype=np.uint8)
        for train_indices, valid_indices in folds.split(dummy, labels):
            train_records = [records[index] for index in train_indices]
            valid_records = [records[index] for index in valid_indices]
            train_labels = labels[train_indices]
            for column, name in enumerate(active_branches):
                estimator = clone(templates[name])
                estimator.fit(train_records, train_labels)
                oof_probabilities[valid_indices, column] = self._phishing_probability(
                    estimator, valid_records
                )

        self.meta_classifier_ = NonNegativeLogisticRegression(max_iter=1000).fit(
            oof_probabilities, labels
        )
        self.meta_calibrator_ = CalibratedClassifierCV(
            estimator=NonNegativeLogisticRegression(max_iter=1000),
            method="sigmoid",
            cv=min(3, splits),
        ).fit(oof_probabilities, labels)
        self.branches_ = {}
        for name in active_branches:
            estimator = clone(templates[name])
            estimator.fit(records, labels)
            self.branches_[name] = estimator

        self.classes_ = np.asarray([str(value) for value in self.meta_calibrator_.classes_])
        self.branch_names_ = active_branches
        self.oof_splits_ = splits
        return self

    def predict_view_proba(self, X: Sequence[dict[str, Any]]) -> dict[str, np.ndarray]:
        check_is_fitted(self, ("branches_", "meta_classifier_", "classes_"))
        records = list(X)
        return {
            name: self._phishing_probability(self.branches_[name], records)
            for name in self.branch_names_
        }

    def _view_matrix(self, X: Sequence[dict[str, Any]]) -> np.ndarray:
        probabilities = self.predict_view_proba(X)
        return np.column_stack([probabilities[name] for name in self.branch_names_])

    def predict_proba(self, X: Sequence[dict[str, Any]]) -> np.ndarray:
        check_is_fitted(self, ("branches_", "meta_classifier_", "meta_calibrator_", "classes_"))
        return self.meta_calibrator_.predict_proba(self._view_matrix(X))

    def predict(self, X: Sequence[dict[str, Any]]) -> np.ndarray:
        probabilities = self.predict_proba(X)
        return self.classes_[np.argmax(probabilities, axis=1)]
