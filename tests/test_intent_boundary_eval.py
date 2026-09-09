from scripts.run_intent_boundary_eval import CASES


def test_boundary_suite_contains_paired_benign_and_action_cases():
    assert len(CASES) == 46
    for intent in ("credential_request", "oauth_authorization", "payment_change", "external_document_action", "reply_or_data_request", "social_pressure", "benign_notice"):
        assert sum(intent in expected for _, _, _, expected in CASES) >= 6
