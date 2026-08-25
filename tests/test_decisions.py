import pytest

from risklens.decisions import clear_decision, load_decisions, record_decision


def test_load_decisions_is_empty_for_unknown_org(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path))

    assert load_decisions("Nobody Inc.") == {}


def test_record_decision_persists_it(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path))

    record_decision("Acme Co", "gov-04", "accepted", "Compensating control in place")

    decisions = load_decisions("Acme Co")
    assert decisions["gov-04"].status == "accepted"
    assert decisions["gov-04"].rationale == "Compensating control in place"


def test_recording_a_decision_twice_replaces_it(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path))

    record_decision("Acme Co", "gov-04", "deferred", "Revisit next quarter")
    record_decision("Acme Co", "gov-04", "mitigated", "Fixed in sprint 12")

    decisions = load_decisions("Acme Co")
    assert len(decisions) == 1
    assert decisions["gov-04"].status == "mitigated"
    assert decisions["gov-04"].rationale == "Fixed in sprint 12"


def test_multiple_findings_are_tracked_independently(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path))

    record_decision("Acme Co", "gov-04", "accepted", "")
    record_decision("Acme Co", "pr-01", "transferred", "Covered by cyber insurance")

    decisions = load_decisions("Acme Co")
    assert set(decisions) == {"gov-04", "pr-01"}


def test_rejects_an_unknown_status(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path))

    with pytest.raises(ValueError):
        record_decision("Acme Co", "gov-04", "ignored", "")


def test_clear_decision_removes_it(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path))
    record_decision("Acme Co", "gov-04", "accepted", "")

    clear_decision("Acme Co", "gov-04")

    assert load_decisions("Acme Co") == {}


def test_clear_decision_on_unrecorded_finding_is_a_no_op(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path))

    clear_decision("Acme Co", "gov-04")  # should not raise

    assert load_decisions("Acme Co") == {}


def test_different_orgs_have_independent_decisions(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path))

    record_decision("Acme Co", "gov-04", "accepted", "")
    record_decision("Other Co", "gov-04", "deferred", "")

    assert load_decisions("Acme Co")["gov-04"].status == "accepted"
    assert load_decisions("Other Co")["gov-04"].status == "deferred"
