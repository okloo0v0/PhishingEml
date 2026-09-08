from scripts.calibrate_intent_thresholds import calibrate


def test_threshold_calibration_is_explicitly_provisional(tmp_path):
    result = calibrate(__import__("pathlib").Path("models/intent_branch_v1_2.joblib"), tmp_path / "calibration.json")
    assert result["provisional"] is True
    assert result["use_as_final_fusion_weight"] is False
