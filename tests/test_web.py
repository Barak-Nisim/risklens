from pathlib import Path

from fastapi.testclient import TestClient

from risklens.loader import load_assessment
from risklens.web.app import app

client = TestClient(app)

SAMPLE_YAML = Path("examples/sample_answers.yaml").read_text(encoding="utf-8")
SAMPLE_ASSESSMENT = load_assessment("examples/sample_answers.yaml")


def _sample_form_data(**overrides):
    data = {"org_name": SAMPLE_ASSESSMENT.org_name, "date": SAMPLE_ASSESSMENT.date}
    for question_id, answer in SAMPLE_ASSESSMENT.answers.items():
        data[f"q_{question_id}"] = str(answer.score)
        if answer.notes:
            data[f"notes_{question_id}"] = answer.notes
    data.update(overrides)
    return data


def test_landing_page_shows_marketing_content():
    response = client.get("/")

    assert response.status_code == 200
    assert "RiskLens" in response.text
    assert "Try the live demo" in response.text
    assert "How it works" in response.text
    # the landing page is not the assessment form
    assert 'name="org_name"' not in response.text


def test_how_it_works_page_explains_methodology():
    response = client.get("/how-it-works")

    assert response.status_code == 200
    assert "How RiskLens works" in response.text
    assert "NIST CSF" in response.text


def test_app_form_is_a_real_questionnaire_prefilled_from_sample():
    response = client.get("/app")

    assert response.status_code == 200
    assert "<form" in response.text
    assert "<textarea" not in response.text  # no raw YAML box anymore
    assert "Acme Financial Services" in response.text
    assert "Govern" in response.text and "Protect" in response.text
    assert 'name="q_pr-01"' in response.text
    # every one of the 21 sample answers should be pre-checked
    assert response.text.count("checked") == len(SAMPLE_ASSESSMENT.answers)


def test_assess_renders_deterministic_report_from_structured_form():
    response = client.post("/assess", data=_sample_form_data())

    assert response.status_code == 200
    assert "RiskLens Security Readiness Report" in response.text
    assert "Acme Financial Services" in response.text
    assert "Findings (prioritized)" in response.text
    assert "2.04 / 4.0 (Defined)" in response.text
    # no AI narrative requested -> no executive summary section
    assert "Executive summary" not in response.text


def test_assess_with_no_answers_still_scores_as_all_zero():
    response = client.post("/assess", data={"org_name": "Empty Co", "date": ""})

    assert response.status_code == 200
    assert "Empty Co" in response.text
    assert "0.00 / 4.0 (Initial)" in response.text


def test_assess_ai_checkbox_ignored_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    response = client.post("/assess", data=_sample_form_data(use_ai="1"))

    assert response.status_code == 200
    assert "Executive summary" not in response.text


def test_report_includes_view_as_yaml_engineering_section():
    response = client.post("/assess", data=_sample_form_data())

    assert "View as YAML" in response.text
    assert "org_name: Acme Financial Services" in response.text


def test_jira_export_returns_csv_attachment():
    response = client.post("/jira-export", data={"answers_yaml": SAMPLE_YAML})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    body = response.text
    assert body.startswith("Summary,Issue Type,Priority,Description,Labels")
