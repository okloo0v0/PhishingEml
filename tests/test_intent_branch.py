from src.detection.intent_branch import INTENT_ONTOLOGY, IntentBranch, infer_intent_labels, multilabel_matrix


def test_behavior_intent_labels_are_action_oriented():
    labels, provenance = infer_intent_labels("Urgent account verification", "Reply with your password and approve sign-in using the device code.")
    assert "credential_request" in labels
    assert "oauth_authorization" in labels
    assert "social_pressure" in labels
    assert provenance == "weak_pattern_v1"


def test_benign_notice_does_not_coexist_with_action_request():
    labels, _ = infer_intent_labels("Notice", "This is an automated notification. No action is required.")
    assert labels == ["benign_notice"]


def test_intent_branch_fits_multilabel_rows():
    rows = [
        {"subject": "Verify", "text_body": "Reply with your password", "intent_labels": ["credential_request", "reply_or_data_request"]},
        {"subject": "Notice", "text_body": "No action is required", "intent_labels": ["benign_notice"]},
        {"subject": "Approve", "text_body": "Authorize with device code", "intent_labels": ["oauth_authorization"]},
        {"subject": "Invoice", "text_body": "Change bank account for payment", "intent_labels": ["payment_change"]},
    ]
    matrix = multilabel_matrix(rows)
    assert matrix.shape == (4, len(INTENT_ONTOLOGY))
    model = IntentBranch(max_features=200)
    model.fit(rows)
    probabilities = model.predict_proba(rows)
    assert probabilities.shape == matrix.shape
