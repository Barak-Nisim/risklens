"""Builds and exports the prioritized remediation backlog as a Jira-importable CSV.

Columns match Jira's standard CSV importer field names (Summary, Issue Type,
Priority, Description, Labels) so the file can be dragged straight into
Jira's "Import issues from CSV" flow with no field mapping required beyond
the defaults.
"""

from __future__ import annotations

import csv
from pathlib import Path

from risklens.models import ScoreResult

FIELDNAMES = ["Summary", "Issue Type", "Priority", "Description", "Labels"]


def priority_tier(rank: int, total: int) -> str:
    if total <= 1:
        return "Highest"
    position = rank / (total - 1)  # 0.0 (first) .. 1.0 (last)
    if position <= 1 / 3:
        return "Highest"
    if position <= 2 / 3:
        return "High"
    return "Medium"


def build_rows(result: ScoreResult) -> list[dict[str, str]]:
    total = len(result.findings)
    rows = []

    for rank, finding in enumerate(result.findings):
        description = (
            f"Organization: {result.assessment.org_name}\n"
            f"Function / Category: {finding.function.name} / {finding.category.name}\n"
            f"Current maturity: {finding.score:.0f}/4\n"
            f"Question weight: {finding.question.weight:.1f}\n"
            f"Priority score: {finding.priority:.2f}"
        )
        rows.append(
            {
                "Summary": f"[RiskLens] {finding.question.text}",
                "Issue Type": "Task",
                "Priority": priority_tier(rank, total),
                "Description": description,
                "Labels": f"risklens,{finding.function.id},{finding.category.id}",
            }
        )

    return rows


def write_jira_csv(result: ScoreResult, path: str) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(build_rows(result))
