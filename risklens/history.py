"""Persists assessment score snapshots between runs, keyed by org name, so
security posture over time can be shown.

Mirrors marketsignal/history.py's proven pattern: ~/.risklens/history/
<org-slug>.json by default, one append-only JSON array per org, outside the
repo entirely since this is real assessment data, not sample data.
Overridable via RISKLENS_HISTORY_DIR, which the test suite uses so tests
never touch a real user's home directory.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from risklens.models import ScoreResult


@dataclass(frozen=True)
class Snapshot:
    org_name: str
    date: str
    overall_score: float
    tier: str
    function_scores: dict[str, float]  # function id -> score


def _history_dir() -> Path:
    override = os.environ.get("RISKLENS_HISTORY_DIR")
    base = Path(override) if override else Path.home() / ".risklens" / "history"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _slug(org_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", org_name.lower()).strip("-") or "org"


def _history_path(org_name: str) -> Path:
    return _history_dir() / f"{_slug(org_name)}.json"


def _snapshot_from_result(result: ScoreResult) -> Snapshot:
    return Snapshot(
        org_name=result.assessment.org_name,
        date=result.assessment.date,
        overall_score=result.overall_score,
        tier=result.tier,
        function_scores={fs.function.id: fs.score for fs in result.function_scores},
    )


def load_history(org_name: str) -> list[Snapshot]:
    path = _history_path(org_name)
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Snapshot(**entry) for entry in raw]


def _save_history(org_name: str, snapshots: list[Snapshot]) -> None:
    path = _history_path(org_name)
    path.write_text(json.dumps([asdict(s) for s in snapshots], indent=2), encoding="utf-8")


def record_snapshot(result: ScoreResult) -> list[Snapshot]:
    """Appends the current result as a new snapshot and returns the full
    history for that org, including this run."""
    org_name = result.assessment.org_name
    history = load_history(org_name)
    history.append(_snapshot_from_result(result))
    _save_history(org_name, history)
    return history


def render_trend(history: list[Snapshot]) -> str:
    """Markdown table of an org's posture over time. Returns an empty
    string if there's fewer than two snapshots to compare."""
    if len(history) < 2:
        return ""

    lines = [
        "## Posture over time",
        "",
        "| Date | Overall Score | Tier |",
        "|---|---|---|",
    ]
    for snap in history:
        lines.append(f"| {snap.date or 'n/a'} | {snap.overall_score:.2f} | {snap.tier} |")

    first, last = history[0], history[-1]
    change = last.overall_score - first.overall_score
    direction = "improved" if change > 0 else "declined" if change < 0 else "held steady"
    lines.append("")
    lines.append(
        f"Overall score has {direction} by {change:+.2f} across {len(history)} assessments."
    )
    return "\n".join(lines)
