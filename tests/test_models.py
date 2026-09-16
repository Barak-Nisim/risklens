from risklens.models import (
    DEFAULT_EVIDENCE_TYPE,
    EVIDENCE_TYPES,
    Answer,
    evidence_strength,
    evidence_type_label,
    normalize_evidence_type,
)


def test_answer_defaults_to_unspecified_evidence():
    answer = Answer(question_id="gov-01", score=2, notes="Some note")

    assert answer.evidence_type == DEFAULT_EVIDENCE_TYPE == "unspecified"


def test_evidence_strength_ranks_weakest_support_lowest():
    ranks = [evidence_strength(key) for key in EVIDENCE_TYPES]

    # unspecified < verbal < policy doc < audit log
    assert ranks == sorted(ranks)
    assert evidence_strength("unspecified") < evidence_strength("verbal")
    assert evidence_strength("verbal") < evidence_strength("policy_doc")
    assert evidence_strength("policy_doc") < evidence_strength("audit_log")


def test_unknown_evidence_type_falls_back_to_the_default():
    # a hand-edited answers file with a typo should still load
    assert normalize_evidence_type("policy-doc") == DEFAULT_EVIDENCE_TYPE
    assert normalize_evidence_type(None) == DEFAULT_EVIDENCE_TYPE
    assert normalize_evidence_type("") == DEFAULT_EVIDENCE_TYPE
    assert evidence_strength("nonsense") == evidence_strength(DEFAULT_EVIDENCE_TYPE)


def test_evidence_type_label_is_human_readable():
    assert evidence_type_label("verbal") == "Verbal confirmation"
    assert evidence_type_label("audit_log") == "Audit log"
    assert evidence_type_label("nonsense") == "Unspecified"
