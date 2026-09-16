"""Data model for RiskLens: framework definitions, answers, and computed scores.

Framework classes (Question/Category/Function/Framework) describe a question
bank loaded from YAML. Assessment/Answer describe a filled-out questionnaire.
The Score* classes and Finding are computed by risklens.scoring and are pure
data; no logic lives on them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MATURITY_LEVELS = {
    0: "Not started",
    1: "Ad hoc",
    2: "Defined",
    3: "Managed",
    4: "Optimized",
}

# Lives here (not scoring.py, which imports it back) so Assessment can use it
# as a field default without a models -> scoring -> models import cycle.
DEFAULT_FINDING_THRESHOLD = 2.0

# How well-supported a note is, ordered weakest -> strongest. A policy doc says
# what is supposed to happen; an audit log shows it actually did, so the log
# outranks the policy. "unspecified" is the default and sorts weakest: an
# untagged note is unverified until someone says otherwise, and treating it as
# the floor keeps it from outranking a note the assessor explicitly tagged.
# Nothing here feeds the score -- this ranks the *support* behind an answer,
# not the answer itself.
EVIDENCE_TYPES = {
    "unspecified": "Unspecified",
    "verbal": "Verbal confirmation",
    "policy_doc": "Policy doc",
    "audit_log": "Audit log",
}
DEFAULT_EVIDENCE_TYPE = "unspecified"
_EVIDENCE_STRENGTH = {key: rank for rank, key in enumerate(EVIDENCE_TYPES)}


def normalize_evidence_type(value: str | None) -> str:
    """Maps anything off the form or out of a YAML file onto a known key.

    Unknown or missing values become the default rather than raising, so a
    hand-edited answers file with a typo still loads.
    """
    if value in EVIDENCE_TYPES:
        return str(value)
    return DEFAULT_EVIDENCE_TYPE


def evidence_type_label(value: str | None) -> str:
    return EVIDENCE_TYPES[normalize_evidence_type(value)]


def evidence_strength(value: str | None) -> int:
    """Sort key for 'how well-supported is this?' -- higher is stronger."""
    return _EVIDENCE_STRENGTH[normalize_evidence_type(value)]


@dataclass(frozen=True)
class Question:
    id: str
    text: str
    weight: float
    rubric: dict[int, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    weight: float
    questions: tuple[Question, ...]
    business_impact: str = ""
    suggested_owner: str = ""


@dataclass(frozen=True)
class Function:
    id: str
    name: str
    weight: float
    categories: tuple[Category, ...]


@dataclass(frozen=True)
class Framework:
    id: str
    name: str
    functions: tuple[Function, ...]

    def question_by_id(self, question_id: str) -> Question | None:
        for function in self.functions:
            for category in function.categories:
                for question in category.questions:
                    if question.id == question_id:
                        return question
        return None

    def all_questions(self) -> list[Question]:
        return [
            question
            for function in self.functions
            for category in function.categories
            for question in category.questions
        ]


@dataclass(frozen=True)
class Answer:
    question_id: str
    score: int
    notes: str | None = None
    # What backs the note up (see EVIDENCE_TYPES). Sibling of `notes`, not a
    # replacement for it: the note says what was found, this says how solidly
    # it was established. Defaults to "unspecified" so nothing is forced and
    # answer files written before this field still load.
    evidence_type: str = DEFAULT_EVIDENCE_TYPE


@dataclass(frozen=True)
class Assessment:
    org_name: str
    date: str
    framework_id: str
    answers: dict[str, Answer]
    # Finding sensitivity chosen for this assessment -- carried on the
    # Assessment (not passed around separately) so it survives the
    # YAML round-trip and every later re-score (recording a decision,
    # simulating a fix, exporting to Jira) uses the same threshold the
    # questionnaire was submitted with, not silently the default.
    finding_threshold: float = DEFAULT_FINDING_THRESHOLD


@dataclass(frozen=True)
class QuestionScore:
    question: Question
    answer: Answer | None
    score: float


@dataclass(frozen=True)
class CategoryScore:
    category: Category
    score: float
    question_scores: tuple[QuestionScore, ...]


@dataclass(frozen=True)
class FunctionScore:
    function: Function
    score: float
    category_scores: tuple[CategoryScore, ...]


@dataclass(frozen=True)
class Finding:
    question: Question
    category: Category
    function: Function
    score: float
    priority: float


@dataclass(frozen=True)
class ScoreResult:
    assessment: Assessment
    framework: Framework
    overall_score: float
    tier: str
    function_scores: tuple[FunctionScore, ...]
    findings: tuple[Finding, ...]
