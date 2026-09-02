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


@dataclass(frozen=True)
class Assessment:
    org_name: str
    date: str
    framework_id: str
    answers: dict[str, Answer]


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
