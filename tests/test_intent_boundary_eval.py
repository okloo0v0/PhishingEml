from scripts.run_intent_boundary_eval import CASES


def test_boundary_suite_contains_paired_benign_and_action_cases():
    assert len(CASES) == 8
    assert sum(not expected for _, _, _, expected in CASES) == 4
    assert sum(bool(expected) for _, _, _, expected in CASES) == 4
