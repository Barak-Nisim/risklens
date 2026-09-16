from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from risklens.loader import dump_assessment, load_assessment, load_framework
from risklens.scoring import score_assessment
from risklens.web.app import app

client = TestClient(app)

SAMPLE_YAML = Path("examples/sample_answers.yaml").read_text(encoding="utf-8")
SAMPLE_ASSESSMENT = load_assessment("examples/sample_answers.yaml")
# how many rows the default-threshold findings table renders
SAMPLE_FINDING_COUNT = len(
    score_assessment(load_framework("nist_csf"), SAMPLE_ASSESSMENT).findings
)


def _sample_form_data(**overrides):
    data = {"org_name": SAMPLE_ASSESSMENT.org_name, "date": SAMPLE_ASSESSMENT.date}
    for question_id, answer in SAMPLE_ASSESSMENT.answers.items():
        data[f"q_{question_id}"] = str(answer.score)
        if answer.notes:
            data[f"notes_{question_id}"] = answer.notes
        data[f"evidence_{question_id}"] = answer.evidence_type
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
    # every sample answer should be pre-checked (checked="checked", not the
    # bare "checked" substring, since the live progress-indicator script
    # also contains a ":checked" CSS selector elsewhere on the page)
    assert response.text.count('checked="checked"') == len(SAMPLE_ASSESSMENT.answers)


def test_assess_renders_deterministic_report_from_structured_form(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))

    response = client.post("/assess", data=_sample_form_data())

    assert response.status_code == 200
    assert "RiskLens Security Readiness Report" in response.text
    assert "Acme Financial Services" in response.text
    assert "Findings (prioritized)" in response.text
    assert "2.04 / 4.0 (Defined)" in response.text
    # no AI narrative requested -> no executive summary section
    assert "Executive summary" not in response.text
    # default finding sensitivity, unrequested
    assert "Standard (below &#34;Defined&#34;)" in response.text


def test_app_form_offers_finding_sensitivity_with_standard_preselected():
    response = client.get("/app")

    assert response.status_code == 200
    assert 'name="finding_threshold"' in response.text
    assert '<option value="2.0" selected>' in response.text
    assert "Lenient" in response.text
    assert "Very strict" in response.text


def test_assess_with_a_lenient_threshold_produces_zero_findings(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))

    response = client.post("/assess", data=_sample_form_data(finding_threshold="1"))

    assert response.status_code == 200
    assert "No findings below the configured threshold." in response.text
    assert "Lenient (below &#34;Ad hoc&#34;)" in response.text


def test_assess_with_a_stricter_threshold_surfaces_more_findings(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))

    response = client.post("/assess", data=_sample_form_data(finding_threshold="4"))

    assert response.status_code == 200
    assert "No findings below the configured threshold." not in response.text
    assert "Very strict (below &#34;Optimized&#34;)" in response.text


def test_finding_threshold_persists_through_a_decision_record_rescore(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))
    strict_yaml = dump_assessment(replace(SAMPLE_ASSESSMENT, finding_threshold=4.0))

    response = client.post(
        "/decisions/record",
        data={
            "answers_yaml": strict_yaml,
            "question_id": "gov-04",
            "status": "accepted",
            "rationale": "Compensating control in place",
        },
    )

    assert response.status_code == 200
    # the threshold chosen at submission time survives the re-score, rather
    # than silently resetting to the default
    assert "Very strict (below &#34;Optimized&#34;)" in response.text


def test_app_form_offers_an_evidence_type_per_question():
    response = client.get("/app")

    assert response.status_code == 200
    assert 'name="evidence_gov-04"' in response.text
    assert "Verbal confirmation" in response.text
    assert "Policy doc" in response.text
    assert "Audit log" in response.text
    # the sample prefills gov-04 as verbal, so that option comes back selected
    assert '<option value="verbal" selected>' in response.text


def test_report_findings_table_shows_an_evidence_badge_per_finding(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))

    response = client.post("/assess", data=_sample_form_data())

    assert response.status_code == 200
    # one badge per finding, with the finding's note rendered alongside it
    assert response.text.count('class="evidence-badge') == SAMPLE_FINDING_COUNT
    assert "Existing vendors are almost never reassessed after onboarding" in response.text
    assert 'class="evidence-badge evidence-1">Verbal confirmation<' in response.text
    assert 'class="evidence-badge evidence-3">Audit log<' in response.text
    # rc-02 carries a note but no evidence type, so it falls back to the default
    assert 'class="evidence-badge evidence-0">Unspecified<' in response.text


def test_report_findings_table_can_be_sorted_by_evidence_strength(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))

    response = client.post("/assess", data=_sample_form_data())

    assert "Evidence: weakest support first" in response.text
    assert "Evidence: strongest support first" in response.text
    # every row carries both sort keys, so switching back to priority is lossless
    assert response.text.count("data-evidence-strength=") == SAMPLE_FINDING_COUNT
    assert response.text.count("data-priority-rank=") == SAMPLE_FINDING_COUNT


def test_evidence_type_chosen_on_the_form_survives_into_the_report_yaml(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))

    response = client.post(
        "/assess", data=_sample_form_data(**{"evidence_gov-04": "audit_log"})
    )

    assert response.status_code == 200
    assert "evidence_type: audit_log" in response.text


def test_unknown_evidence_type_posted_to_the_form_falls_back_to_default(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))

    response = client.post("/assess", data=_sample_form_data(**{"evidence_gov-04": "bogus"}))

    assert response.status_code == 200
    assert "evidence_type: bogus" not in response.text


def test_assess_report_leads_with_executive_dashboard(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))

    response = client.post("/assess", data=_sample_form_data())

    assert response.status_code == 200
    assert "Executive risk dashboard" in response.text
    assert "Regulatory and audit exposure" in response.text  # deterministic impact metadata
    assert "Compliance / GRC lead" in response.text
    # dashboard reads before the demoted findings detail view
    assert response.text.index("Executive risk dashboard") < response.text.index(
        "Detailed findings and risk decisions"
    )


def test_assess_findings_table_is_demoted_into_a_collapsible_details(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))

    response = client.post("/assess", data=_sample_form_data())

    # the detail view is wrapped in a <details> but the simulate + decision
    # controls it depends on are still present in the DOM
    assert "<details class=\"findings-detail\">" in response.text
    assert "Findings (prioritized)" in response.text
    assert 'name="question_ids"' in response.text
    assert "Save decision" in response.text


def test_dashboard_residual_band_reflects_a_recorded_decision(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))
    client.post("/assess", data=_sample_form_data())

    response = client.post(
        "/decisions/record",
        data={
            "answers_yaml": SAMPLE_YAML,
            "question_id": "gov-07",
            "status": "accepted",
            "rationale": "Compensating control",
        },
    )

    assert response.status_code == 200
    assert "Accepted (retained)" in response.text


def test_assess_with_no_answers_still_scores_as_all_zero(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))

    response = client.post("/assess", data={"org_name": "Empty Co", "date": ""})

    assert response.status_code == 200
    assert "Empty Co" in response.text
    assert "0.00 / 4.0 (Initial)" in response.text


def test_assess_ai_checkbox_ignored_without_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))

    response = client.post("/assess", data=_sample_form_data(use_ai="1"))

    assert response.status_code == 200
    assert "Executive summary" not in response.text


def test_report_includes_view_as_yaml_engineering_section(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))

    response = client.post("/assess", data=_sample_form_data())

    assert "View as YAML" in response.text
    assert "org_name: Acme Financial Services" in response.text


def test_assess_shows_no_trend_on_first_run(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))

    response = client.post("/assess", data=_sample_form_data())

    assert "Posture over time" not in response.text


def test_assess_shows_trend_on_second_run(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))

    client.post("/assess", data=_sample_form_data())
    response = client.post("/assess", data=_sample_form_data())

    assert "Posture over time" in response.text
    assert "held steady" in response.text


def test_report_shows_a_decision_form_for_each_finding(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))

    response = client.post("/assess", data=_sample_form_data())

    assert "Risk decisions" in response.text
    assert 'action="/decisions/record"' in response.text
    assert "Save decision" in response.text


def test_decisions_record_shows_the_saved_decision_on_the_report(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))
    assess_response = client.post("/assess", data=_sample_form_data())

    response = client.post(
        "/decisions/record",
        data={
            "answers_yaml": SAMPLE_YAML,
            "question_id": "gov-04",
            "status": "accepted",
            "rationale": "Compensating control in place",
        },
    )

    assert response.status_code == 200
    assert "Accepted" in response.text
    assert "Compensating control in place" in response.text
    assert "Clear decision" in response.text
    assert assess_response.status_code == 200  # baseline call sanity check


def test_decisions_clear_removes_the_decision(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))
    client.post(
        "/decisions/record",
        data={
            "answers_yaml": SAMPLE_YAML,
            "question_id": "gov-04",
            "status": "deferred",
            "rationale": "Revisit next quarter",
        },
    )

    response = client.post(
        "/decisions/clear",
        data={"answers_yaml": SAMPLE_YAML, "question_id": "gov-04"},
    )

    assert response.status_code == 200
    assert "Revisit next quarter" not in response.text
    assert "Save decision" in response.text  # form is back, no decision recorded


def test_jira_export_returns_csv_attachment():
    response = client.post("/jira-export", data={"answers_yaml": SAMPLE_YAML})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    body = response.text
    assert body.startswith("Summary,Issue Type,Priority,Description,Labels")


def test_report_findings_table_has_simulate_checkboxes_and_button(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path / "decisions"))

    response = client.post("/assess", data=_sample_form_data())

    assert 'name="question_ids"' in response.text
    assert "Simulate fixing checked findings" in response.text


def test_simulate_shows_before_after_comparison():
    response = client.post(
        "/simulate",
        data={"answers_yaml": SAMPLE_YAML, "question_ids": ["gov-04"]},
    )

    assert response.status_code == 200
    assert "What if these findings were fixed" in response.text
    assert "Overall score (before)" in response.text
    assert "Overall score (after)" in response.text
    assert "1 finding(s) simulated" in response.text


def test_simulate_with_no_findings_selected_shows_zero_findings_simulated():
    response = client.post("/simulate", data={"answers_yaml": SAMPLE_YAML})

    assert response.status_code == 200
    assert "0 finding(s) simulated" in response.text
