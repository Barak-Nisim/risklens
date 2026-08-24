from pathlib import Path

from fastapi.testclient import TestClient

from risklens.web.app import app

client = TestClient(app)

SAMPLE_YAML = Path("examples/sample_answers.yaml").read_text(encoding="utf-8")


def test_landing_page_shows_marketing_content():
    response = client.get("/")

    assert response.status_code == 200
    assert "RiskLens" in response.text
    assert "Try the live demo" in response.text
    assert "How it works" in response.text
    # the landing page is not the assessment form
    assert '<textarea id="answers_yaml"' not in response.text


def test_how_it_works_page_explains_methodology():
    response = client.get("/how-it-works")

    assert response.status_code == 200
    assert "How RiskLens works" in response.text
    assert "NIST CSF" in response.text


def test_app_form_shows_sample_answers():
    response = client.get("/app")

    assert response.status_code == 200
    assert "Acme Financial Services" in response.text
    assert "<form" in response.text


def test_assess_renders_deterministic_report():
    response = client.post("/assess", data={"answers_yaml": SAMPLE_YAML})

    assert response.status_code == 200
    assert "RiskLens Security Readiness Report" in response.text
    assert "Acme Financial Services" in response.text
    assert "Findings (prioritized)" in response.text
    # no AI narrative requested -> no executive summary section
    assert "Executive summary" not in response.text


def test_assess_with_invalid_yaml_shows_error_on_index():
    response = client.post("/assess", data={"answers_yaml": "not: [valid, yaml: structure"})

    assert response.status_code == 200
    assert "Could not parse or score" in response.text
    assert "<form" in response.text


def test_assess_ai_checkbox_ignored_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    response = client.post("/assess", data={"answers_yaml": SAMPLE_YAML, "use_ai": "1"})

    assert response.status_code == 200
    assert "Executive summary" not in response.text


def test_jira_export_returns_csv_attachment():
    response = client.post("/jira-export", data={"answers_yaml": SAMPLE_YAML})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    body = response.text
    assert body.startswith("Summary,Issue Type,Priority,Description,Labels")
