from risklens.loader import load_assessment, load_framework
from risklens.models import Answer, Assessment, Category, Framework, Function, Question
from risklens.scoring import MAX_SCORE, score_assessment, tier_for_score

EXAMPLE_ANSWERS_PATH = "examples/sample_answers.yaml"


def _tiny_framework() -> Framework:
    """A minimal two-question, single-category, single-function framework for edge-case tests."""
    q1 = Question(id="q1", text="Question 1", weight=1.0)
    q2 = Question(id="q2", text="Question 2", weight=2.0)
    category = Category(id="cat1", name="Category 1", weight=1.0, questions=(q1, q2))
    function = Function(id="func1", name="Function 1", weight=1.0, categories=(category,))
    return Framework(id="tiny", name="Tiny", functions=(function,))


def test_all_max_answers_score_optimized():
    framework = _tiny_framework()
    assessment = Assessment(
        org_name="Test Org",
        date="2026-01-01",
        framework_id="tiny",
        answers={"q1": Answer("q1", 4), "q2": Answer("q2", 4)},
    )

    result = score_assessment(framework, assessment)

    assert result.overall_score == MAX_SCORE
    assert result.tier == "Optimized"
    assert result.findings == ()


def test_all_zero_answers_score_initial_and_flag_all_findings():
    framework = _tiny_framework()
    assessment = Assessment(
        org_name="Test Org",
        date="2026-01-01",
        framework_id="tiny",
        answers={"q1": Answer("q1", 0), "q2": Answer("q2", 0)},
    )

    result = score_assessment(framework, assessment)

    assert result.overall_score == 0.0
    assert result.tier == "Initial"
    assert {f.question.id for f in result.findings} == {"q1", "q2"}


def test_missing_answer_is_treated_as_zero():
    framework = _tiny_framework()
    assessment = Assessment(
        org_name="Test Org",
        date="2026-01-01",
        framework_id="tiny",
        answers={"q1": Answer("q1", 4)},  # q2 unanswered
    )

    result = score_assessment(framework, assessment)

    category_score = result.function_scores[0].category_scores[0]
    q2_score = next(qs for qs in category_score.question_scores if qs.question.id == "q2")

    assert q2_score.score == 0.0
    assert q2_score.answer is None
    assert any(f.question.id == "q2" for f in result.findings)


def test_higher_weight_question_moves_category_score_more():
    framework = _tiny_framework()  # q2 has weight 2.0, q1 has weight 1.0
    assessment = Assessment(
        org_name="Test Org",
        date="2026-01-01",
        framework_id="tiny",
        answers={"q1": Answer("q1", 4), "q2": Answer("q2", 0)},
    )

    result = score_assessment(framework, assessment)
    category_score = result.function_scores[0].category_scores[0]

    # weighted average: (4*1 + 0*2) / 3 = 1.333..., pulled toward the heavier q2
    assert category_score.score < 2.0


def test_finding_threshold_is_configurable():
    framework = _tiny_framework()
    assessment = Assessment(
        org_name="Test Org",
        date="2026-01-01",
        framework_id="tiny",
        answers={"q1": Answer("q1", 3), "q2": Answer("q2", 3)},
    )

    default_result = score_assessment(framework, assessment)
    assert default_result.findings == ()

    strict_result = score_assessment(framework, assessment, finding_threshold=3.5)
    assert len(strict_result.findings) == 2


def test_findings_are_sorted_by_priority_descending():
    framework = _tiny_framework()
    assessment = Assessment(
        org_name="Test Org",
        date="2026-01-01",
        framework_id="tiny",
        # q1 (weight 1.0, score 1) -> priority 1*(4-1)=3
        # q2 (weight 2.0, score 1) -> priority 2*(4-1)=6, should rank first
        answers={"q1": Answer("q1", 1), "q2": Answer("q2", 1)},
    )

    result = score_assessment(framework, assessment)

    assert [f.question.id for f in result.findings] == ["q2", "q1"]


def test_tier_for_score_boundaries():
    assert tier_for_score(0.0) == "Initial"
    assert tier_for_score(0.79) == "Initial"
    assert tier_for_score(0.8) == "Developing"
    assert tier_for_score(1.6) == "Defined"
    assert tier_for_score(2.4) == "Managed"
    assert tier_for_score(3.2) == "Optimized"
    assert tier_for_score(4.0) == "Optimized"


def test_full_nist_csf_framework_with_example_answers_runs_end_to_end():
    framework = load_framework("nist_csf")
    assessment = load_assessment(EXAMPLE_ANSWERS_PATH)

    result = score_assessment(framework, assessment)

    assert 0.0 < result.overall_score < MAX_SCORE
    assert len(result.function_scores) == 6
    assert len(result.findings) > 0
    # every question in the framework should have been scored
    scored_ids = {
        qs.question.id
        for fs in result.function_scores
        for cs in fs.category_scores
        for qs in cs.question_scores
    }
    assert scored_ids == {q.id for q in framework.all_questions()}
