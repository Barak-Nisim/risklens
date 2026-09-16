from risklens.loader import dump_assessment, load_assessment, load_framework, parse_assessment
from risklens.models import DEFAULT_FINDING_THRESHOLD, Answer, Assessment

# an answers file written before evidence_type existed
LEGACY_YAML = """
org_name: Legacy Co
date: "2026-01-01"
framework: nist_csf
answers:
  gov-01: { score: 3, notes: "Risk strategy documented" }
  gov-02: 2
"""


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
        assert reloaded.answers[question_id].evidence_type == answer.evidence_type


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


def test_load_assessment_parses_evidence_type_alongside_notes():
    assessment = load_assessment("examples/sample_answers.yaml")

    assert assessment.answers["gov-04"].evidence_type == "verbal"
    assert assessment.answers["pr-01"].evidence_type == "audit_log"
    assert assessment.answers["rs-01"].evidence_type == "policy_doc"
    # rc-02 has a note but no evidence_type
    assert assessment.answers["rc-02"].notes is not None
    assert assessment.answers["rc-02"].evidence_type == "unspecified"


def test_evidence_type_round_trips_through_dump_and_parse():
    original = Assessment(
        org_name="Test Org",
        date="2026-01-01",
        framework_id="nist_csf",
        answers={
            "gov-01": Answer("gov-01", 3, notes="Documented", evidence_type="policy_doc"),
            "gov-02": Answer("gov-02", 1, notes="Team said so", evidence_type="verbal"),
            "gov-03": Answer("gov-03", 2, evidence_type="audit_log"),  # tagged, no note
        },
    )

    reloaded = parse_assessment(dump_assessment(original))

    assert reloaded.answers["gov-01"].evidence_type == "policy_doc"
    assert reloaded.answers["gov-01"].notes == "Documented"
    assert reloaded.answers["gov-02"].evidence_type == "verbal"
    # an evidence type survives even without a note to hang it on
    assert reloaded.answers["gov-03"].evidence_type == "audit_log"
    assert reloaded.answers["gov-03"].notes is None


def test_legacy_answers_without_evidence_type_load_as_unspecified():
    assessment = parse_assessment(LEGACY_YAML)

    assert assessment.answers["gov-01"].notes == "Risk strategy documented"
    assert assessment.answers["gov-01"].evidence_type == "unspecified"
    # the bare-score shorthand still works too
    assert assessment.answers["gov-02"].score == 2
    assert assessment.answers["gov-02"].evidence_type == "unspecified"


def test_unknown_evidence_type_in_a_file_loads_as_unspecified():
    assessment = parse_assessment(
        'org_name: Typo Co\nanswers:\n  gov-01: { score: 3, evidence_type: "policy-doc" }\n'
    )

    assert assessment.answers["gov-01"].evidence_type == "unspecified"


def test_dump_assessment_omits_evidence_type_when_unspecified():
    assessment = Assessment(
        org_name="Test Org",
        date="2026-01-01",
        framework_id="nist_csf",
        answers={
            "gov-01": Answer("gov-01", 3, notes="Documented"),
            "gov-02": Answer("gov-02", 2),
        },
    )

    dumped = dump_assessment(assessment)

    assert "evidence_type" not in dumped
    # a score with nothing else recorded stays a bare scalar, as before
    assert "gov-02: 2" in dumped


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
