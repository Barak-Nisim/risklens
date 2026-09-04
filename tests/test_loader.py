from risklens.loader import dump_assessment, load_assessment, load_framework, parse_assessment
from risklens.models import DEFAULT_FINDING_THRESHOLD, Assessment


def test_load_framework_parses_nist_csf():
    framework = load_framework("nist_csf")

    assert framework.id == "nist_csf"
    assert {f.id for f in framework.functions} == {
        "govern",
        "identify",
        "protect",
        "detect",
        "respond",
        "recover",
    }

    sso_question = framework.question_by_id("pr-01")
    assert sso_question is not None
    assert "SSO" in sso_question.text or "single sign-on" in sso_question.text.lower()
    assert sso_question.rubric[4] == "Optimized: continuously improved, integrated into operations"


def test_load_assessment_parses_answers_with_notes():
    assessment = load_assessment("examples/sample_answers.yaml")

    assert assessment.org_name == "Acme Financial Services"
    assert assessment.framework_id == "nist_csf"
    assert assessment.answers["pr-01"].score == 4
    assert assessment.answers["gov-04"].score == 1
    assert assessment.answers["gov-04"].notes is not None


def test_dump_assessment_round_trips_through_parse_assessment():
    original = load_assessment("examples/sample_answers.yaml")

    dumped = dump_assessment(original)
    reloaded = parse_assessment(dumped)

    assert reloaded.org_name == original.org_name
    assert reloaded.date == original.date
    assert reloaded.framework_id == original.framework_id
    assert reloaded.answers.keys() == original.answers.keys()
    for question_id, answer in original.answers.items():
        assert reloaded.answers[question_id].score == answer.score
        assert reloaded.answers[question_id].notes == answer.notes


def test_dump_assessment_omits_notes_key_when_no_notes():
    assessment = Assessment(
        org_name="Test Org", date="2026-01-01", framework_id="nist_csf", answers={}
    )
    dumped = dump_assessment(assessment)

    assert "org_name: Test Org" in dumped
    assert "answers: {}" in dumped


def test_load_assessment_defaults_finding_threshold_for_older_files():
    # examples/sample_answers.yaml predates this field
    assessment = load_assessment("examples/sample_answers.yaml")

    assert assessment.finding_threshold == DEFAULT_FINDING_THRESHOLD


def test_finding_threshold_round_trips_through_parse_assessment():
    original = Assessment(
        org_name="Test Org",
        date="2026-01-01",
        framework_id="nist_csf",
        answers={},
        finding_threshold=3.0,
    )

    reloaded = parse_assessment(dump_assessment(original))

    assert reloaded.finding_threshold == 3.0
