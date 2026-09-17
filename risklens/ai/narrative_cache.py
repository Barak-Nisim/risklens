"""Caches AI narratives so re-running an identical assessment doesn't
re-spend tokens on a response that would come back identical.

Keyed by a hash of the exact payload the narrator sends to the model
(`prompts.build_findings_payload`: the org name, overall score and tier,
every function score, and each finding's question, function, category,
score and weight). That payload is the whole of what varies between calls
-- the system prompt and instruction text are fixed -- so there's no
separate TTL to reason about: any real change to the answers, or to what
the scoring engine made of them, is itself a cache miss. That includes a
changed finding threshold, which changes which questions surface as
findings at all.

One file per distinct assessment, at ~/.risklens/narrative_cache/ by
default, outside the repo since this is real assessment data. Overridable
via RISKLENS_NARRATIVE_CACHE_DIR, which the test suite uses so tests never
touch a real user's home directory (mirrors history.py/decisions.py's
storage pattern).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from risklens.ai.prompts import build_findings_payload
from risklens.models import ScoreResult


def _cache_dir() -> Path:
    override = os.environ.get("RISKLENS_NARRATIVE_CACHE_DIR")
    base = Path(override) if override else Path.home() / ".risklens" / "narrative_cache"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _input_key(result: ScoreResult) -> str:
    blob = json.dumps(build_findings_payload(result), sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _cache_path(input_key: str) -> Path:
    return _cache_dir() / f"{input_key}.json"


def get_cached_narrative(result: ScoreResult) -> dict | None:
    input_key = _input_key(result)
    path = _cache_path(input_key)
    if not path.exists():
        return None
    cached = json.loads(path.read_text(encoding="utf-8"))
    if cached.get("input_key") != input_key:
        return None
    return cached["narrative"]


def store_narrative(result: ScoreResult, narrative: dict) -> None:
    input_key = _input_key(result)
    payload = {"input_key": input_key, "narrative": narrative}
    _cache_path(input_key).write_text(json.dumps(payload, indent=2), encoding="utf-8")
