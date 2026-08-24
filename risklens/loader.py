"""Loads framework and assessment YAML files into the dataclasses in models.py."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import yaml

from risklens.models import Answer, Assessment, Category, Framework, Function, Question

BUILTIN_FRAMEWORKS = {"nist_csf"}


def _framework_path(name_or_path: str) -> Path:
    if name_or_path in BUILTIN_FRAMEWORKS:
        return resources.files("risklens.frameworks").joinpath(f"{name_or_path}.yaml")
    return Path(name_or_path)


def load_framework(name_or_path: str) -> Framework:
    path = _framework_path(name_or_path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    functions = []
    for func_raw in raw["functions"]:
        categories = []
        for cat_raw in func_raw["categories"]:
            questions = tuple(
                Question(
                    id=q["id"],
                    text=q["text"],
                    weight=float(q["weight"]),
                    rubric={int(k): v for k, v in q.get("rubric", {}).items()},
                )
                for q in cat_raw["questions"]
            )
            categories.append(
                Category(
                    id=cat_raw["id"],
                    name=cat_raw["name"],
                    weight=float(cat_raw["weight"]),
                    questions=questions,
                )
            )
        functions.append(
            Function(
                id=func_raw["id"],
                name=func_raw["name"],
                weight=float(func_raw["weight"]),
                categories=tuple(categories),
            )
        )

    return Framework(id=raw["id"], name=raw["name"], functions=tuple(functions))


def load_assessment(path: str | Path) -> Assessment:
    return parse_assessment(Path(path).read_text(encoding="utf-8"))


def parse_assessment(yaml_text: str) -> Assessment:
    raw = yaml.safe_load(yaml_text)

    answers = {}
    for question_id, entry in raw.get("answers", {}).items():
        if isinstance(entry, dict):
            answers[question_id] = Answer(
                question_id=question_id,
                score=int(entry["score"]),
                notes=entry.get("notes"),
            )
        else:
            answers[question_id] = Answer(question_id=question_id, score=int(entry))

    return Assessment(
        org_name=raw["org_name"],
        date=raw.get("date", ""),
        framework_id=raw.get("framework", "nist_csf"),
        answers=answers,
    )
