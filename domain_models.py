from typing import TypedDict


class QuestionData(TypedDict, total=False):
    id: int
    category: str
    content: str
    answer: str
    solution: str


class AssessmentResult(TypedDict):
    question_data: QuestionData
    user_answer: str
    is_correct: bool


class LeakageEvaluation(TypedDict):
    is_leaking: bool
    score: int
    reason: str


class ControlledHintResult(TypedDict, total=False):
    hint: str
    is_leaking: int
    leakage_score: int
    rewrite_count: int
    leakage_reason: str
    hint_strength: str
    generation_status: str
    generation_elapsed_ms: int
    generation_error: str
    stage_timings: dict[str, int]
