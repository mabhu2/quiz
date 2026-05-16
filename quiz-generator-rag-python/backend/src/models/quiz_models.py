from __future__ import annotations

import re
from typing import Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

AnswerOption = Literal["A", "B", "C", "D"]
Difficulty = Literal["easy", "medium", "hard"]
DifficultyMode = Literal["easy", "medium", "hard", "mixed"]
QuizMode = Literal["exam", "learning", "practice"]
SkillTag = Literal["logic", "syntax", "concept", "application"]

ALLOWED_QUESTION_COUNTS = {5, 10, 15, 20, 30, 50}
OPTION_KEYS = {"A", "B", "C", "D"}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def fingerprint(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


class QuizGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    topic: str = Field(..., min_length=2, max_length=160)
    difficulty_mode: DifficultyMode = Field(
        default="mixed",
        validation_alias=AliasChoices("difficulty_mode", "difficulty"),
    )
    total_questions: int = Field(
        default=10,
        validation_alias=AliasChoices(
            "total_questions",
            "question_count",
            "num_questions",
            "number_of_questions",
        ),
    )
    mode: QuizMode = "practice"

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, value: str) -> str:
        value = normalize_text(value)
        if not value:
            raise ValueError("Topic is required.")
        return value

    @field_validator("difficulty_mode", mode="before")
    @classmethod
    def normalize_difficulty_mode(cls, value: str) -> str:
        if isinstance(value, str):
            return normalize_text(value).lower().replace(" mode", "")
        return value

    @field_validator("mode", mode="before")
    @classmethod
    def normalize_mode(cls, value: str) -> str:
        if isinstance(value, str):
            normalized = normalize_text(value).lower().replace(" mode", "")
            if normalized in {"exam", "learning", "practice"}:
                return normalized
        return value

    @field_validator("total_questions")
    @classmethod
    def validate_total_questions(cls, value: int) -> int:
        if value not in ALLOWED_QUESTION_COUNTS:
            allowed = ", ".join(str(count) for count in sorted(ALLOWED_QUESTION_COUNTS))
            raise ValueError(f"Question count must be one of: {allowed}.")
        return value


class QuizMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=3, max_length=120)
    topic: str = Field(..., min_length=2, max_length=160)
    difficulty_mode: DifficultyMode
    total_questions: int

    @field_validator("title", "topic")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = normalize_text(value)
        if not value:
            raise ValueError("Value cannot be blank.")
        return value


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., ge=1)
    question: str = Field(..., min_length=8, max_length=420)
    options: dict[AnswerOption, str]
    correct_answer: AnswerOption
    explanation: str = Field(..., min_length=12, max_length=600)
    difficulty: Difficulty
    skill_tag: SkillTag

    @field_validator("question", "explanation")
    @classmethod
    def validate_question_text(cls, value: str) -> str:
        value = normalize_text(value)
        if not value:
            raise ValueError("Question text cannot be blank.")
        return value

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: dict[AnswerOption, str]) -> dict[AnswerOption, str]:
        if set(value) != OPTION_KEYS:
            raise ValueError("Options must include exactly A, B, C, and D.")

        cleaned = {
            key: normalize_text(option)
            for key, option in value.items()
        }
        if any(not option for option in cleaned.values()):
            raise ValueError("Option text cannot be blank.")

        option_fingerprints = [fingerprint(option) for option in cleaned.values()]
        if len(set(option_fingerprints)) != len(option_fingerprints):
            raise ValueError("Options must be distinct.")

        return cleaned

    @model_validator(mode="after")
    def validate_correct_answer(self) -> "Question":
        if self.correct_answer not in self.options:
            raise ValueError("Correct answer must reference one of A, B, C, or D.")
        return self


class QuizResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quiz_meta: QuizMeta
    questions: list[Question]

    @model_validator(mode="after")
    def validate_quiz(self) -> "QuizResponse":
        expected_total = self.quiz_meta.total_questions
        if len(self.questions) != expected_total:
            raise ValueError("Question count does not match quiz metadata.")

        expected_ids = list(range(1, expected_total + 1))
        actual_ids = [question.id for question in self.questions]
        if actual_ids != expected_ids:
            raise ValueError("Question ids must be sequential starting at 1.")

        fingerprints = [fingerprint(question.question) for question in self.questions]
        if len(set(fingerprints)) != len(fingerprints):
            raise ValueError("Duplicate questions are not allowed.")

        return self


class UserAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: int = Field(..., ge=1)
    selected_answer: AnswerOption | None = None
    response_time_ms: int | None = Field(default=None, ge=0)


class QuizSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quiz: QuizResponse
    answers: list[UserAnswer]

    @model_validator(mode="after")
    def validate_answers(self) -> "QuizSubmission":
        quiz_question_ids = {question.id for question in self.quiz.questions}
        answer_ids = [answer.question_id for answer in self.answers]

        if len(set(answer_ids)) != len(answer_ids):
            raise ValueError("Duplicate answers are not allowed.")

        unknown_ids = set(answer_ids) - quiz_question_ids
        if unknown_ids:
            raise ValueError("Answers include question ids that do not exist in the quiz.")

        return self


class WeakArea(BaseModel):
    skill_tag: SkillTag
    difficulty: Difficulty
    missed_questions: int


class QuestionOutcome(BaseModel):
    question_id: int
    selected_answer: AnswerOption | None
    correct_answer: AnswerOption
    is_correct: bool
    skill_tag: SkillTag
    difficulty: Difficulty
    response_time_ms: int | None = None


class QuizResult(BaseModel):
    score: int
    total_questions: int
    accuracy_percent: float
    topic_mastery_level: str
    weak_areas: list[WeakArea]
    suggested_next_topics: list[str]
    outcomes: list[QuestionOutcome]
