from risklens.cli import main


def test_assess_no_ai_prints_report(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path))

    exit_code = main(["assess", "examples/sample_answers.yaml", "--no-ai"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "RiskLens Security Readiness Report: Acme Financial Services" in captured.out
    assert "Overall Score:" in captured.out


def test_assess_no_ai_writes_to_output_file(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path / "history"))
    output_path = tmp_path / "report.md"

    exit_code = main(
        ["assess", "examples/sample_answers.yaml", "--no-ai", "--output", str(output_path)]
    )

    assert exit_code == 0
    assert output_path.exists()
    assert "RiskLens Security Readiness Report" in output_path.read_text(encoding="utf-8")


def test_assess_with_simulate_prints_a_what_if_comparison(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path))

    exit_code = main(
        ["assess", "examples/sample_answers.yaml", "--no-ai", "--simulate", "gov-04"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "What-If Simulation" in captured.out
    assert "Overall score:" in captured.out


def test_assess_with_simulate_target_uses_the_configured_score(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path))

    exit_code = main(
        [
            "assess",
            "examples/sample_answers.yaml",
            "--no-ai",
            "--simulate",
            "gov-04",
            "--simulate-target",
            "3",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Questions improved to 3/4" in captured.out


def test_assess_records_a_snapshot_but_shows_no_trend_on_first_run(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path))

    exit_code = main(["assess", "examples/sample_answers.yaml", "--no-ai"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Posture over time" not in captured.out
    assert list(tmp_path.glob("*.json"))


def test_assess_shows_trend_on_second_run(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_HISTORY_DIR", str(tmp_path))

    main(["assess", "examples/sample_answers.yaml", "--no-ai"])
    exit_code = main(["assess", "examples/sample_answers.yaml", "--no-ai"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Posture over time" in captured.out
    assert "held steady" in captured.out


def test_decisions_list_when_empty(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path))

    exit_code = main(["decisions", "list", "Acme Co"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "No decisions recorded yet." in captured.err


def test_decisions_record_and_list(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path))

    main(
        [
            "decisions",
            "record",
            "Acme Co",
            "gov-04",
            "accepted",
            "--rationale",
            "Compensating control in place",
        ]
    )
    exit_code = main(["decisions", "list", "Acme Co"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "gov-04: accepted -- Compensating control in place" in captured.out


def test_decisions_rejects_unknown_status(monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path))

    try:
        main(["decisions", "record", "Acme Co", "gov-04", "ignored"])
        raise AssertionError("expected SystemExit from argparse choices validation")
    except SystemExit:
        pass


def test_decisions_clear(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("RISKLENS_DECISIONS_DIR", str(tmp_path))
    main(["decisions", "record", "Acme Co", "gov-04", "accepted"])

    main(["decisions", "clear", "Acme Co", "gov-04"])
    exit_code = main(["decisions", "list", "Acme Co"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "No decisions recorded yet." in captured.err
