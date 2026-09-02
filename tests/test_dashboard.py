from risklens.dashboard import (
    build_executive_view,
    enrich_executive_view,
    residual_band,
    severity_band,
)
from risklens.decisions import Decision
from risklens.loader import load_assessment, load_framework
from risklens.models import Answer, Assessment, Category, Framework, Function, Question
from risklens.scoring import score_assessment


def _framework_with_n_questions(n: int) -> Framework:
    questions = tuple(
        Question(id=f"q{i}", text=f"Question {i}", weight=1.0 + i * 0.1) for i in range(n)
    )
    category = Category(
        id="cat1",
        name="Category 1",
        weight=1.0,
        questions=questions,
        business_impact="Some business impact",
        suggested_owner="Some Owner",
    )
    function = Function(id="func1", name="Function 1", weight=1.0, categories=(category,))
    return Framework(id="tiny", name="Tiny", functions=(function,))


def _all_zero_assessment(n: int) -> Assessment:
    return Assessment(
        org_name="Test Org",
        date="2026-01-01",
        framework_id="tiny",
        answers={f"q{i}": Answer(f"q{i}", 0) for i in range(n)},
    )


def _sample_result():
    framework = load_framework("nist_csf")
    assessment = load_assessment("examples/sample_answers.yaml")
    return score_assessment(framework, assessment)


def test_build_executive_view_takes_only_top_n():
    framework = _framework_with_n_questions(8)
    assessment = _all_zero_assessment(8)
    result = score_assessment(framework, assessment)

    view = build_executive_view(result, {}, top_n=5)

    assert view.top_n == 5
    assert len(view.risks) == 5
    # ranks are 1-based and contiguous
    assert [r.rank for r in view.risks] == [1, 2, 3, 4, 5]


def test_executive_view_preserves_scoring_priority_order():
    framework = _framework_with_n_questions(6)
    assessment = _all_zero_assessment(6)
    result = score_assessment(framework, assessment)

    view = build_executive_view(result, {})

    # highest-weight question surfaces first, matching scoring.py's ranking
    assert view.risks[0].question_id == "q5"  # weight 1.5, the largest
    priorities = [r.inherent_priority for r in view.risks]
    assert priorities == sorted(priorities, reverse=True)


def test_executive_view_pulls_business_impact_and_owner_from_framework():
    framework = _framework_with_n_questions(3)
    assessment = _all_zero_assessment(3)
    result = score_assessment(framework, assessment)

    view = build_executive_view(result, {})

    assert view.risks[0].business_impact == "Some business impact"
    assert view.risks[0].suggested_owner == "Some Owner"


def test_recommended_action_default_is_templated_from_the_finding():
    framework = _framework_with_n_questions(3)
    assessment = _all_zero_assessment(3)
    result = score_assessment(framework, assessment)

    view = build_executive_view(result, {})

    assert "Raise Category 1 maturity from 0/4" in view.risks[0].recommended_action


def test_severity_band_splits_into_thirds():
    assert severity_band(0, 9) == "High"
    assert severity_band(3, 9) == "Medium"  # position 3/8 = 0.375 > 1/3 -> Medium
    assert severity_band(8, 9) == "Low"  # position 1.0 -> Low
    # explicit boundaries
    assert severity_band(0, 4) == "High"  # 0.0
    assert severity_band(1, 4) == "High"  # 0.25
    assert severity_band(2, 4) == "Medium"  # 0.5
    assert severity_band(3, 4) == "Low"  # 0.75
    assert severity_band(4, 4) == "Low"  # 1.0


def test_severity_band_single_finding_is_high():
    assert severity_band(0, 1) == "High"


def test_residual_band_no_decision_is_inherent():
    assert residual_band("High", None) == "High"
    assert residual_band("Medium", None) == "Medium"


def test_residual_band_deferred_leaves_inherent():
    assert residual_band("High", "deferred") == "High"


def test_residual_band_accepted_is_retained_label():
    assert residual_band("High", "accepted") == "Accepted (retained)"
    assert residual_band("Low", "accepted") == "Accepted (retained)"


def test_residual_band_mitigated_steps_down_one_level():
    assert residual_band("High", "mitigated") == "Medium"
    assert residual_band("Medium", "mitigated") == "Low"
    assert residual_band("Low", "mitigated") == "Low"  # floors at Low


def test_residual_band_transferred_steps_down_one_level():
    assert residual_band("High", "transferred") == "Medium"


def test_build_executive_view_applies_decision_to_residual_band():
    framework = _framework_with_n_questions(3)
    assessment = _all_zero_assessment(3)
    result = score_assessment(framework, assessment)
    top_id = result.findings[0].question.id
    decisions = {top_id: Decision(question_id=top_id, status="accepted", rationale="control")}

    view = build_executive_view(result, decisions)

    top = view.risks[0]
    assert top.decision_status == "accepted"
    assert top.residual_band == "Accepted (retained)"


def test_executive_view_on_real_sample_has_five_ranked_risks():
    view = build_executive_view(_sample_result(), {})

    assert len(view.risks) == 5
    assert view.risks[0].question_id == "gov-07"  # weight 1.1, top priority
    assert view.tier == _sample_result().tier


def test_enrich_overlays_ai_prose_but_keeps_bands_and_order():
    view = build_executive_view(_sample_result(), {})
    top_id = view.risks[0].question_id
    original_band = view.risks[0].severity_band
    narrative = {
        "remediation_plan": [
            {"question_id": top_id, "next_step": "Automate evidence collection this quarter."}
        ],
        "risk_register": [
            {"question_id": top_id, "impact": "Failed audits and lost customer trust."}
        ],
    }

    enriched = enrich_executive_view(view, narrative)

    assert enriched.risks[0].recommended_action == "Automate evidence collection this quarter."
    assert enriched.risks[0].business_impact == "Failed audits and lost customer trust."
    # order and bands are untouched by enrichment
    assert enriched.risks[0].question_id == top_id
    assert enriched.risks[0].severity_band == original_band
    assert [r.question_id for r in enriched.risks] == [r.question_id for r in view.risks]


def test_enrich_with_no_narrative_returns_deterministic_defaults():
    view = build_executive_view(_sample_result(), {})

    assert enrich_executive_view(view, None) == view


def test_enrich_falls_back_when_row_has_no_matching_id():
    view = build_executive_view(_sample_result(), {})
    default_action = view.risks[0].recommended_action
    narrative = {
        "remediation_plan": [{"question_id": "does-not-exist", "next_step": "Ignored."}],
        "risk_register": [],
    }

    enriched = enrich_executive_view(view, narrative)

    assert enriched.risks[0].recommended_action == default_action
