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


def test_render_has_no_findings_message_when_none():
    framework = load_framework("nist_csf")
    assessment = load_assessment("examples/sample_answers.yaml")
    result = score_assessment(framework, assessment, finding_threshold=0.0)

    report = render(result)

    assert "No findings below the configured threshold." in report
