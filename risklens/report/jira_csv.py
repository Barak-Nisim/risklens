"""Exports the prioritized remediation backlog as a Jira-importable CSV.

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


def _priority_tier(rank: int, total: int) -> str:
    if total <= 1:
        return "Highest"
    position = rank / (total - 1)  # 0.0 (first) .. 1.0 (last)
    if position <= 1 / 3:
        return "Highest"
    if position <= 2 / 3:
        return "High"
    return "Medium"


def write_jira_csv(result: ScoreResult, path: str) -> None:
    rows = []
    total = len(result.findings)

    for rank, finding in enumerate(result.findings):
        summary = f"[RiskLens] {finding.question.text}"
        description = (
            f"Organization: {result.assessment.org_name}\n"
            f"Function / Category: {finding.function.name} / {finding.category.name}\n"
            f"Current maturity: {finding.score:.0f}/4\n"
            f"Question weight: {finding.question.weight:.1f}\n"
            f"Priority score: {finding.priority:.2f}"
        )
        labels = f"risklens,{finding.function.id},{finding.category.id}"
        rows.append(
            {
                "Summary": summary,
                "Issue Type": "Task",
                "Priority": _priority_tier(rank, total),
                "Description": description,
                "Labels": labels,
            }
        )

    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
