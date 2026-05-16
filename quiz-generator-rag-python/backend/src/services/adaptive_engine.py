from __future__ import annotations

from math import floor
from typing import Literal

Difficulty = Literal["easy", "medium", "hard"]
DifficultyMode = Literal["easy", "medium", "hard", "mixed"]
TopicComplexity = Literal["beginner", "standard", "advanced"]

ADVANCED_TOPIC_KEYWORDS = {
    "agent",
    "agents",
    "ai",
    "algorithm",
    "architecture",
    "blockchain",
    "compiler",
    "cryptography",
    "cybersecurity",
    "data science",
    "deep learning",
    "distributed",
    "kubernetes",
    "large language model",
    "llm",
    "machine learning",
    "ml",
    "neural",
    "quantum",
    "rag",
    "reinforcement learning",
    "systems design",
}

BEGINNER_TOPIC_KEYWORDS = {
    "101",
    "basics",
    "beginner",
    "class 1",
    "class 2",
    "class 3",
    "class 4",
    "class 5",
    "fundamentals",
    "intro",
    "introduction",
    "kids",
    "primary school",
}

MIXED_WEIGHTS: dict[TopicComplexity, dict[Difficulty, float]] = {
    "beginner": {"easy": 0.55, "medium": 0.35, "hard": 0.10},
    "standard": {"easy": 0.40, "medium": 0.40, "hard": 0.20},
    "advanced": {"easy": 0.25, "medium": 0.45, "hard": 0.30},
}


def detect_topic_complexity(topic: str) -> TopicComplexity:
    normalized = topic.lower()

    if any(keyword in normalized for keyword in BEGINNER_TOPIC_KEYWORDS):
        return "beginner"

    if any(keyword in normalized for keyword in ADVANCED_TOPIC_KEYWORDS):
        return "advanced"

    return "standard"


def build_difficulty_plan(
    topic: str,
    difficulty_mode: DifficultyMode,
    total_questions: int,
) -> dict[Difficulty, int]:
    if difficulty_mode != "mixed":
        return {
            "easy": total_questions if difficulty_mode == "easy" else 0,
            "medium": total_questions if difficulty_mode == "medium" else 0,
            "hard": total_questions if difficulty_mode == "hard" else 0,
        }

    complexity = detect_topic_complexity(topic)
    weights = MIXED_WEIGHTS[complexity]
    raw_counts = {
        difficulty: total_questions * weight
        for difficulty, weight in weights.items()
    }
    plan = {
        difficulty: floor(count)
        for difficulty, count in raw_counts.items()
    }

    remainder = total_questions - sum(plan.values())
    if remainder:
        fractional_order = sorted(
            raw_counts,
            key=lambda difficulty: raw_counts[difficulty] - plan[difficulty],
            reverse=True,
        )
        for difficulty in fractional_order[:remainder]:
            plan[difficulty] += 1

    return plan


def difficulty_sequence(plan: dict[Difficulty, int]) -> list[Difficulty]:
    sequence: list[Difficulty] = []
    for difficulty in ("easy", "medium", "hard"):
        sequence.extend([difficulty] * plan.get(difficulty, 0))
    return sequence
