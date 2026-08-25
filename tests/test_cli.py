from risklens.cli import main


def test_assess_no_ai_prints_report(capsys):
    exit_code = main(["assess", "examples/sample_answers.yaml", "--no-ai"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "RiskLens Security Readiness Report: Acme Financial Services" in captured.out
    assert "Overall Score:" in captured.out


def test_assess_no_ai_writes_to_output_file(tmp_path):
    output_path = tmp_path / "report.md"
    exit_code = main(
        ["assess", "examples/sample_answers.yaml", "--no-ai", "--output", str(output_path)]
    )

    assert exit_code == 0
    assert output_path.exists()
    assert "RiskLens Security Readiness Report" in output_path.read_text(encoding="utf-8")


def test_assess_with_simulate_prints_a_what_if_comparison(capsys):
    exit_code = main(
        ["assess", "examples/sample_answers.yaml", "--no-ai", "--simulate", "gov-04"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "What-If Simulation" in captured.out
    assert "Overall score:" in captured.out


def test_assess_with_simulate_target_uses_the_configured_score(capsys):
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
