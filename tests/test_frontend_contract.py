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


def test_frontend_api_module_covers_contract_endpoints():
    source = Path("src/web/js/api.js").read_text(encoding="utf-8")
    for endpoint in (
        "/health",
        "/api/emails/analyze",
        "/api/detections",
        "/api/blacklist",
        "/api/statistics/overview",
        "/api/model/metrics",
        "/api/knowledge",
        "/api/feedback",
    ):
        assert endpoint in source


def test_sample_input_uses_explicit_not_found_error():
    response = client.post(
        "/api/emails/analyze",
        data={"sample_id": "missing_demo_sample"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RECORD_NOT_FOUND"
