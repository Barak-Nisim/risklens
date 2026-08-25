from risklens.loader import load_assessment, load_framework
from risklens.models import Answer, Assessment, Category, Framework, Function, Question
from risklens.simulate import render_simulation, simulate_improvement


def _tiny_framework() -> Framework:
    q1 = Question(id="q1", text="Question 1", weight=1.0)
    q2 = Question(id="q2", text="Question 2", weight=2.0)
    category = Category(id="cat1", name="Category 1", weight=1.0, questions=(q1, q2))
    function = Function(id="func1", name="Function 1", weight=1.0, categories=(category,))
    return Framework(id="tiny", name="Tiny", functions=(function,))


def _tiny_assessment(q1_score: int, q2_score: int) -> Assessment:
    return Assessment(
        org_name="Test Org",
        date="2026-01-01",
        framework_id="tiny",
        answers={"q1": Answer("q1", q1_score), "q2": Answer("q2", q2_score)},
    )


def test_simulation_leaves_baseline_assessment_untouched():
    framework = _tiny_framework()
    assessment = _tiny_assessment(0, 0)

    simulate_improvement(framework, assessment, ["q1"])

    assert assessment.answers["q1"].score == 0  # original object is immutable, unmodified


def test_simulating_a_low_weight_question_barely_moves_the_score():
    framework = _tiny_framework()
    # q1 (weight 1.0) is already fine; q2 (weight 2.0) is the real problem
    assessment = _tiny_assessment(4, 0)

    sim = simulate_improvement(framework, assessment, ["q1"])

    assert sim.overall_score_delta == 0.0  # q1 was already at target_score=4


def test_simulating_the_real_problem_question_resolves_its_finding():
    framework = _tiny_framework()
    assessment = _tiny_assessment(4, 0)

    sim = simulate_improvement(framework, assessment, ["q2"])

    assert sim.overall_score_delta > 0
    assert "q2" in sim.resolved_finding_ids
    assert sim.remaining_finding_ids == ()
    assert sim.hypothetical.overall_score == 4.0
    assert sim.hypothetical.tier == "Optimized"


def test_simulating_a_subset_of_findings_leaves_the_rest_open():
    framework = _tiny_framework()
    assessment = _tiny_assessment(0, 0)

    sim = simulate_improvement(framework, assessment, ["q1"])

    assert "q1" in sim.resolved_finding_ids
    assert "q2" in sim.remaining_finding_ids


def test_target_score_is_configurable():
    framework = _tiny_framework()
    assessment = _tiny_assessment(0, 0)

    sim = simulate_improvement(framework, assessment, ["q1"], target_score=2)

    assert sim.hypothetical.function_scores[0].category_scores[0].question_scores[0].score == 2.0


def test_preserves_existing_notes_on_simulated_answers():
    framework = _tiny_framework()
    assessment = Assessment(
        org_name="Test Org",
        date="2026-01-01",
        framework_id="tiny",
        answers={"q1": Answer("q1", 0, notes="MFA not enforced"), "q2": Answer("q2", 0)},
    )

    sim = simulate_improvement(framework, assessment, ["q1"])

    hypothetical_answer = sim.hypothetical.assessment.answers["q1"]
    assert hypothetical_answer.notes == "MFA not enforced"
    assert hypothetical_answer.score == 4


def test_simulate_against_the_real_sample_assessment():
    framework = load_framework("nist_csf")
    assessment = load_assessment("examples/sample_answers.yaml")
    a_finding_id = score_result_first_finding_id(framework, assessment)

    sim = simulate_improvement(framework, assessment, [a_finding_id])

    assert sim.overall_score_delta >= 0
    assert a_finding_id in sim.resolved_finding_ids


def score_result_first_finding_id(framework, assessment) -> str:
    from risklens.scoring import score_assessment

    baseline = score_assessment(framework, assessment)
    assert baseline.findings, "sample assessment should have at least one finding"
    return baseline.findings[0].question.id


def test_render_simulation_includes_before_after_and_resolved_findings():
    framework = _tiny_framework()
    assessment = _tiny_assessment(4, 0)

    sim = simulate_improvement(framework, assessment, ["q2"])
    text = render_simulation(sim)

    assert "What-If Simulation" in text
    assert f"{sim.baseline.overall_score:.2f}" in text
    assert f"{sim.hypothetical.overall_score:.2f}" in text
    assert "Question 2" in text
