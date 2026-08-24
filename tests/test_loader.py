from risklens.loader import load_assessment, load_framework


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
    assert sso_question.rubric[4] == "Optimized — continuously improved, integrated into operations"


def test_load_assessment_parses_answers_with_notes():
    assessment = load_assessment("examples/sample_answers.yaml")

    assert assessment.org_name == "Acme Financial Services"
    assert assessment.framework_id == "nist_csf"
    assert assessment.answers["pr-01"].score == 4
    assert assessment.answers["gov-04"].score == 1
    assert assessment.answers["gov-04"].notes is not None
