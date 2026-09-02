from risklens.dashboard import build_executive_view
from risklens.loader import load_assessment, load_framework
from risklens.report.markdown import render
from risklens.scoring import score_assessment


def _sample_result():
    framework = load_framework("nist_csf")
    assessment = load_assessment("examples/sample_answers.yaml")
    return score_assessment(framework, assessment)


def test_render_deterministic_report_contains_key_sections():
    report = render(_sample_result())

    assert "RiskLens Security Readiness Report: Acme Financial Services" in report
    assert "## Function Scores" in report
    assert "## Findings (prioritized)" in report
    assert "## Executive Summary" not in report  # no AI narrative passed


def test_render_includes_ai_narrative_when_provided():
    ai_narrative = {
        "executive_summary": "Overall posture is developing, with vendor and IR gaps.",
        "remediation_plan": [
            {
                "title": "Reassess existing vendors",
                "rationale": "Highest-priority gap by weight.",
                "next_step": "Schedule Q3 vendor risk review.",
            }
        ],
        "risk_register": [
            {
                "risk": "Unreviewed vendors introduce unmanaged third-party risk",
                "likelihood": "Medium",
                "impact": "High",
                "owner": "TBD",
            }
        ],
    }

    report = render(_sample_result(), ai_narrative=ai_narrative)

    assert "## Executive Summary" in report
    assert "Overall posture is developing" in report
    assert "## Remediation Plan" in report
    assert "Reassess existing vendors" in report
    assert "## Risk Register" in report


def test_render_includes_executive_dashboard_when_view_provided():
    result = _sample_result()
    view = build_executive_view(result, {})

    report = render(result, executive_view=view)

    assert "## Executive Risk Dashboard" in report
    # dashboard leads the report, above the function scores
    assert report.index("## Executive Risk Dashboard") < report.index("## Function Scores")
    # deterministic columns are populated from framework metadata
    assert "Regulatory and audit exposure" in report  # gov-07 category impact
    assert "Compliance / GRC lead" in report


def test_dashboard_overlays_ai_next_step_onto_recommended_action():
    result = _sample_result()
    view = build_executive_view(result, {})
    top_id = view.risks[0].question_id
    ai_narrative = {
        "executive_summary": "Posture is developing.",
        "remediation_plan": [
            {
                "question_id": top_id,
                "title": "Fix audit evidence",
                "rationale": "Top gap.",
                "next_step": "Stand up an evidence automation pipeline in Q3.",
            }
        ],
        "risk_register": [],
    }

    report = render(result, ai_narrative=ai_narrative, executive_view=view)

    assert "Stand up an evidence automation pipeline in Q3." in report


def test_render_has_no_findings_message_when_none():
    framework = load_framework("nist_csf")
    assessment = load_assessment("examples/sample_answers.yaml")
    result = score_assessment(framework, assessment, finding_threshold=0.0)

    report = render(result)

    assert "No findings below the configured threshold." in report
