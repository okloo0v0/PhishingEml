from scripts.calibrate_intent_thresholds import calibrate


def test_threshold_calibration_is_explicitly_provisional(tmp_path):
    result = calibrate(__import__("pathlib").Path("models/intent_branch_v1_2.joblib"), tmp_path / "calibration.json")
    assert result["provisional"] is True
    assert result["use_as_final_fusion_weight"] is False
    assert result["case_count"] == 46
    assert all(item["positive_support"] >= 6 for item in result["metrics"].values())
    assert result["accepted_for_intent_decision"] is True
    assert result["calibrated_exact_match_rate"] >= result["default_exact_match_rate"]
