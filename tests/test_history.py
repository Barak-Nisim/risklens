from risklens.history import load_history, record_snapshot, render_trend
from risklens.loader import load_assessment, load_framework
from risklens.scoring import score_assessment


def _sample_result():
    framework = load_framework("nist_csf")
    assessment = load_assessment("examples/sample_answers.yaml")
    return score_assessment(framework, assessment)


def test_load_history_returns_empty_list_for_unknown_org(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path))

    assert load_history("Nobody Inc.") == []


def test_record_snapshot_persists_and_returns_full_history(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path))
    result = _sample_result()

    history = record_snapshot(result)

    assert len(history) == 1
    assert history[0].org_name == result.assessment.org_name
    assert history[0].overall_score == result.overall_score
    assert history[0].tier == result.tier


def test_record_snapshot_appends_across_multiple_runs(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path))
    result = _sample_result()

    record_snapshot(result)
    history = record_snapshot(result)

    assert len(history) == 2
    loaded = load_history(result.assessment.org_name)
    assert len(loaded) == 2


def test_org_name_is_slugified_for_the_filename(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path))
    result = _sample_result()
    assert result.assessment.org_name == "Acme Financial Services"

    record_snapshot(result)

    assert (tmp_path / "acme-financial-services.json").exists()


def test_history_storage_is_isolated_from_real_user_home(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path))

    record_snapshot(_sample_result())

    assert list(tmp_path.glob("*.json"))


def test_render_trend_is_empty_with_fewer_than_two_snapshots(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path))
    history = record_snapshot(_sample_result())

    assert render_trend(history) == ""


def test_render_trend_shows_a_table_and_direction_with_two_or_more(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path))
    result = _sample_result()
    record_snapshot(result)
    history = record_snapshot(result)

    text = render_trend(history)

    assert "Posture over time" in text
    assert f"{result.overall_score:.2f}" in text
    assert "held steady" in text  # same result recorded twice, no change


def test_render_trend_reports_improvement_direction(monkeypatch, tmp_path):
    from dataclasses import replace

    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path))
    result = _sample_result()
    record_snapshot(replace(result, overall_score=1.0, tier="Developing"))
    history = record_snapshot(replace(result, overall_score=3.0, tier="Managed"))

    text = render_trend(history)

    assert "improved" in text
    assert "+2.00" in text
