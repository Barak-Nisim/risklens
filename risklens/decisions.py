"""Persists risk acceptance decisions (accept/mitigate/transfer/defer) per
finding, so a leader's disposition and rationale for an open risk is
captured and shown alongside the assessment it belongs to.

Mirrors history.py's storage pattern: ~/.risklens/decisions/<org-slug>.json,
one file per org holding the latest decision for each question id (not an
append-only log -- recording a new decision for the same finding replaces
the old one). Overridable via RISKLENS_DECISIONS_DIR for test isolation.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

DECISION_STATUSES = {"accepted", "mitigated", "transferred", "deferred"}


@dataclass(frozen=True)
class Decision:
    question_id: str
    status: str  # one of DECISION_STATUSES
    rationale: str
    decided_at: str = ""


def _decisions_dir() -> Path:
    override = os.environ.get("RISKLENS_DECISIONS_DIR")
    base = Path(override) if override else Path.home() / ".risklens" / "decisions"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _slug(org_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", org_name.lower()).strip("-") or "org"


def _decisions_path(org_name: str) -> Path:
    return _decisions_dir() / f"{_slug(org_name)}.json"


def load_decisions(org_name: str) -> dict[str, Decision]:
    path = _decisions_path(org_name)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {question_id: Decision(**entry) for question_id, entry in raw.items()}


def _save_decisions(org_name: str, decisions: dict[str, Decision]) -> None:
    path = _decisions_path(org_name)
    path.write_text(
        json.dumps({qid: asdict(d) for qid, d in decisions.items()}, indent=2),
        encoding="utf-8",
    )


def record_decision(
    org_name: str, question_id: str, status: str, rationale: str = "", decided_at: str = ""
) -> Decision:
    if status not in DECISION_STATUSES:
        raise ValueError(f"Unknown decision status: {status!r}. Must be one of {DECISION_STATUSES}")

    decisions = load_decisions(org_name)
    decision = Decision(
        question_id=question_id, status=status, rationale=rationale, decided_at=decided_at
    )
    decisions[question_id] = decision
    _save_decisions(org_name, decisions)
    return decision


def clear_decision(org_name: str, question_id: str) -> None:
    decisions = load_decisions(org_name)
    if question_id in decisions:
        del decisions[question_id]
        _save_decisions(org_name, decisions)
