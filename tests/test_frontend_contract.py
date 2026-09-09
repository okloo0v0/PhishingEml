"""Basic checks that the native frontend is mounted and follows API input names."""

from pathlib import Path

from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_frontend_entry_and_static_assets_are_served():
    page = client.get("/")
    assert page.status_code == 200
    assert "选择邮件来源" in page.text
    assert "data-source=\"sample\"" in page.text

    css = client.get("/static/css/app.css")
    js = client.get("/static/js/app.js")
    api_js = client.get("/static/js/api.js")
    assert css.status_code == 200
    assert js.status_code == 200
    assert api_js.status_code == 200
    assert "textContent" in js.text
    assert "innerHTML" not in js.text
    assert "可疑邮件快速处置流程" in page.text
    assert "knowledge-feature" in page.text
    assert "典型案例" in js.text
    assert "处理与应急" in js.text
    assert "knowledge-comparison" in js.text


def test_frontend_api_module_covers_contract_endpoints():
    source = Path("src/web/js/api.js").read_text(encoding="utf-8")
    for endpoint in (
        "/health",
        "/api/emails/analyze",
        "/api/detections",
        "/api/detections/${encodeURIComponent(id)}/llm-assessment",
        "/api/blacklist",
        "/api/statistics/overview",
        "/api/model/metrics",
        "/api/knowledge",
        "/api/feedback",
    ):
        assert endpoint in source

    assert "智能辅助解读" in Path("src/web/js/app.js").read_text(encoding="utf-8")
    assert "llm_status" in Path("src/web/js/app.js").read_text(encoding="utf-8")
    assert "./api.js?v=20260909-llm-2" in Path("src/web/js/app.js").read_text(encoding="utf-8")
    assert "grid.append(evidence, renderLlmAssessment" in Path("src/web/js/app.js").read_text(encoding="utf-8")
    assert "处理建议" not in Path("src/web/js/app.js").read_text(encoding="utf-8")


def test_sample_input_uses_explicit_not_found_error():
    response = client.post(
        "/api/emails/analyze",
        data={"sample_id": "missing_demo_sample"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RECORD_NOT_FOUND"
