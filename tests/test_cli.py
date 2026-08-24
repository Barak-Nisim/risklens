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
