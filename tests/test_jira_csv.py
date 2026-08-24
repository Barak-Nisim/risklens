import csv

from risklens.loader import load_assessment, load_framework
from risklens.report.jira_csv import FIELDNAMES, write_jira_csv
from risklens.scoring import score_assessment


def _sample_result():
    framework = load_framework("nist_csf")
    assessment = load_assessment("examples/sample_answers.yaml")
    return score_assessment(framework, assessment)


def test_write_jira_csv_has_one_row_per_finding(tmp_path):
    result = _sample_result()
    out_path = tmp_path / "backlog.csv"

    write_jira_csv(result, str(out_path))

    with out_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == len(result.findings)
    assert list(rows[0].keys()) == FIELDNAMES


def test_write_jira_csv_priority_tiers_are_valid(tmp_path):
    result = _sample_result()
    out_path = tmp_path / "backlog.csv"

    write_jira_csv(result, str(out_path))

    with out_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert all(row["Priority"] in {"Highest", "High", "Medium"} for row in rows)
    # highest-priority finding (first in the sorted list) should be tier "Highest"
    assert rows[0]["Priority"] == "Highest"


def test_write_jira_csv_labels_include_function_and_category(tmp_path):
    result = _sample_result()
    out_path = tmp_path / "backlog.csv"

    write_jira_csv(result, str(out_path))

    with out_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    first_finding = result.findings[0]
    assert first_finding.function.id in rows[0]["Labels"]
    assert first_finding.category.id in rows[0]["Labels"]


def test_write_jira_csv_handles_no_findings(tmp_path):
    out_path = tmp_path / "backlog.csv"

    # a permissive threshold produces zero findings
    framework = load_framework("nist_csf")
    assessment = load_assessment("examples/sample_answers.yaml")
    clean_result = score_assessment(framework, assessment, finding_threshold=0.0)

    write_jira_csv(clean_result, str(out_path))

    with out_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert rows == []
