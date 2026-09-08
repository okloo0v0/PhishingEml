import numpy as np

from src.detection.multiview_features import build_multiview_record
from src.detection.multiview_model import BRANCH_NAMES, MultiViewPhishingClassifier


def _training_records():
    samples = [
        ("Urgent account", "Verify password immediately", "phishing"),
        ("Payment change", "Confidential wire transfer request", "phishing"),
        ("Device authorization", "Approve sign-in using this device code", "phishing"),
        ("Shared document", "Download and open the attachment", "phishing"),
        ("Team meeting", "Weekly project meeting agenda", "legitimate"),
        ("Lunch plan", "Can we have lunch tomorrow", "legitimate"),
        ("Release notes", "The release was completed successfully", "legitimate"),
        ("Course update", "Lecture room changed for next week", "legitimate"),
    ]
    return [build_multiview_record(subject, body) for subject, body, _ in samples], [
        label for _, _, label in samples
    ]


def test_multiview_classifier_fits_oof_branches_and_returns_probabilities():
    records, labels = _training_records()
    model = MultiViewPhishingClassifier(
        word_max_features=100,
        char_max_features=200,
        min_df=1,
        cv_splits=2,
    ).fit(records, labels)

    probabilities = model.predict_proba(records)
    views = model.predict_view_proba(records)

    assert list(model.classes_) == ["legitimate", "phishing"]
    assert model.oof_splits_ == 2
    assert probabilities.shape == (len(records), 2)
    assert np.allclose(probabilities.sum(axis=1), 1.0)
    assert tuple(views) == BRANCH_NAMES
    assert all(values.shape == (len(records),) for values in views.values())
    assert np.all(model.meta_classifier_.coef_ >= 0.0)
    assert len(model.meta_calibrator_.calibrated_classifiers_) == 2
