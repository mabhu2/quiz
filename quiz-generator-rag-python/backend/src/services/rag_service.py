from __future__ import annotations

import json
from collections import Counter
from typing import Any

from openai import AsyncOpenAI, BadRequestError, OpenAIError, RateLimitError
from pydantic import ValidationError

from src.config.groq_config import (
    create_groq_http_client,
    get_groq_base_url,
    get_groq_models,
    require_groq_api_key,
    use_local_quiz_fallback,
)
from src.models.quiz_models import (
    QuestionOutcome,
    QuizGenerationRequest,
    QuizResponse,
    QuizResult,
    QuizSubmission,
    WeakArea,
    fingerprint,
)
from src.services.adaptive_engine import (
    Difficulty,
    build_difficulty_plan,
    difficulty_sequence,
)


class QuizGenerationError(RuntimeError):
    pass


class GroqRateLimitError(QuizGenerationError):
    pass


class QuizValidationError(ValueError):
    pass


class RAGService:
    def __init__(self):
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=require_groq_api_key(),
                base_url=get_groq_base_url(),
                http_client=create_groq_http_client(),
            )
        return self._client

    async def ingest_document(self, text: str):
        # Placeholder for future RAG ingestion. Keep the API stable while the
        # quiz engine already supports topic-only generation.
        return {"status": "ingested", "length": len(text)}

    async def generate_quiz(self, request: QuizGenerationRequest | str) -> QuizResponse:
        if isinstance(request, str):
            request = QuizGenerationRequest(topic=request)

        difficulty_plan = build_difficulty_plan(
            request.topic,
            request.difficulty_mode,
            request.total_questions,
        )

        last_error = ""
        last_payload: dict[str, Any] | None = None
        for attempt in range(1, 3):
            try:
                raw_content = await self._call_groq(request, difficulty_plan, last_error)
            except GroqRateLimitError:
                if use_local_quiz_fallback():
                    return self._generate_local_quiz(request, difficulty_plan)
                raise
            try:
                payload = self._parse_json(raw_content)
                last_payload = payload
                payload = self._normalize_payload_contract(payload, request, difficulty_plan)
                quiz = QuizResponse.model_validate(payload)
                self._validate_generation_contract(quiz, request, difficulty_plan)
                return quiz
            except (json.JSONDecodeError, ValidationError, QuizValidationError) as exc:
                last_error = f"Attempt {attempt} failed validation: {exc}"
                if last_payload and "vague shortcut" in str(exc).lower():
                    repaired_quiz = await self._repair_quiz(
                        last_payload,
                        request,
                        difficulty_plan,
                        last_error,
                    )
                    if repaired_quiz:
                        return repaired_quiz

        if last_payload:
            repaired_quiz = await self._repair_quiz(
                last_payload,
                request,
                difficulty_plan,
                last_error,
            )
            if repaired_quiz:
                return repaired_quiz

        raise QuizGenerationError(last_error or "Groq did not return a valid quiz.")

    async def evaluate_submission(self, submission: QuizSubmission) -> QuizResult:
        question_by_id = {
            question.id: question
            for question in submission.quiz.questions
        }
        answers_by_id = {
            answer.question_id: answer
            for answer in submission.answers
        }

        outcomes: list[QuestionOutcome] = []
        weak_counter: Counter[tuple[str, str]] = Counter()

        for question in submission.quiz.questions:
            answer = answers_by_id.get(question.id)
            selected_answer = answer.selected_answer if answer else None
            is_correct = selected_answer == question.correct_answer
            response_time_ms = answer.response_time_ms if answer else None

            if not is_correct:
                weak_counter[(question.skill_tag, question.difficulty)] += 1

            outcomes.append(
                QuestionOutcome(
                    question_id=question.id,
                    selected_answer=selected_answer,
                    correct_answer=question.correct_answer,
                    is_correct=is_correct,
                    skill_tag=question.skill_tag,
                    difficulty=question.difficulty,
                    response_time_ms=response_time_ms,
                )
            )

        total_questions = len(question_by_id)
        score = sum(1 for outcome in outcomes if outcome.is_correct)
        accuracy_percent = round((score / total_questions) * 100, 2) if total_questions else 0.0
        weak_areas = [
            WeakArea(
                skill_tag=skill_tag,
                difficulty=difficulty,
                missed_questions=missed_questions,
            )
            for (skill_tag, difficulty), missed_questions in weak_counter.most_common()
        ]

        return QuizResult(
            score=score,
            total_questions=total_questions,
            accuracy_percent=accuracy_percent,
            topic_mastery_level=self._mastery_level(accuracy_percent),
            weak_areas=weak_areas,
            suggested_next_topics=self._suggest_next_topics(
                submission.quiz.quiz_meta.topic,
                weak_areas,
                accuracy_percent,
            ),
            outcomes=outcomes,
        )

    async def _call_groq(
        self,
        request: QuizGenerationRequest,
        difficulty_plan: dict[Difficulty, int],
        previous_error: str,
    ) -> str:
        messages = self._build_messages(request, difficulty_plan, previous_error)
        max_tokens = self._max_completion_tokens(request)
        rate_limit_errors: list[str] = []

        for model in get_groq_models():
            try:
                completion = await self._create_chat_completion(
                    model=model,
                    messages=messages,
                    temperature=0.18,
                    top_p=0.9,
                    max_tokens=max_tokens,
                )
                content = completion.choices[0].message.content
                if not content:
                    raise QuizGenerationError("Groq returned an empty response.")
                return content
            except RateLimitError as exc:
                rate_limit_errors.append(self._rate_limit_message(model, exc))
                continue
            except BadRequestError as exc:
                raise QuizGenerationError(f"Groq request failed: {exc}") from exc
            except OpenAIError as exc:
                raise QuizGenerationError(f"Groq request failed: {exc}") from exc

        detail = " ".join(rate_limit_errors)
        raise GroqRateLimitError(
            detail
            or "Groq daily token limit reached for all configured models."
        )

    async def _create_chat_completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        top_p: float,
        max_tokens: int,
    ) -> Any:
        try:
            return await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_completion_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
        except BadRequestError as exc:
            if "response_format" not in str(exc).lower():
                raise
            return await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_completion_tokens=max_tokens,
            )

    def _max_completion_tokens(self, request: QuizGenerationRequest) -> int:
        return min(12000, 900 + request.total_questions * 180)

    def _rate_limit_message(self, model: str, exc: RateLimitError) -> str:
        retry_after = getattr(exc, "response", None)
        retry_after = retry_after.headers.get("retry-after") if retry_after else None
        retry_text = f" Retry after {retry_after} seconds." if retry_after else ""
        return f"Groq rate limit reached for {model}.{retry_text}"

    def _build_messages(
        self,
        request: QuizGenerationRequest,
        difficulty_plan: dict[Difficulty, int],
        previous_error: str,
    ) -> list[dict[str, str]]:
        target_sequence = difficulty_sequence(difficulty_plan)
        system_prompt = (
            "You are AI_SYSTEM_MASTER, a production quiz-generation engine. "
            "Return STRICT JSON only. No markdown, no prose, no comments. "
            "Generate MCQ quizzes that are accurate, non-repetitive, and ordered "
            "from easy to hard. Validate your answer before returning it."
        )
        user_payload: dict[str, Any] = {
            "task": "Generate a premium adaptive MCQ quiz.",
            "request": {
                "topic": request.topic,
                "difficulty_mode": request.difficulty_mode,
                "total_questions": request.total_questions,
                "mode": request.mode,
            },
            "difficulty_distribution": difficulty_plan,
            "required_difficulty_sequence": target_sequence,
            "schema": {
                "quiz_meta": {
                    "title": "string",
                    "topic": request.topic,
                    "difficulty_mode": request.difficulty_mode,
                    "total_questions": request.total_questions,
                },
                "questions": [
                    {
                        "id": 1,
                        "question": "string",
                        "options": {
                            "A": "string",
                            "B": "string",
                            "C": "string",
                            "D": "string",
                        },
                        "correct_answer": "A",
                        "explanation": "string",
                        "difficulty": "easy | medium | hard",
                        "skill_tag": "logic | syntax | concept | application",
                    }
                ],
            },
            "quality_rules": [
                "Every question must have exactly four distinct options A, B, C, and D.",
                "Exactly one answer must be correct, and correct_answer must be A, B, C, or D.",
                "Incorrect options must be clearly false for the question.",
                "No duplicate or near-duplicate questions.",
                "Never use options such as all of the above, none of the above, both A and B, or cannot be determined.",
                "If several options could be true, rewrite the question so only one option is correct.",
                "No vague wording or trick ambiguity.",
                "Every explanation must be factual and concise.",
                "Do not invent facts. For unstable current-event claims, avoid the claim.",
                "Use the exact question count and exact difficulty distribution.",
                "Order questions by the required_difficulty_sequence.",
                "Use only skill_tag values: logic, syntax, concept, application.",
                "Return parseable JSON with only quiz_meta and questions at the top level.",
            ],
            "mode_behavior": {
                "exam": "strict wording with concise explanations",
                "learning": "slightly richer explanations for teaching",
                "practice": "balanced exam-like wording with useful explanations",
            },
        }

        if previous_error:
            user_payload["previous_validation_error"] = previous_error
            user_payload["repair_instruction"] = (
                "Fix the exact validation failure. If an option like all/none/both is present, "
                "replace the entire question with a clean single-answer MCQ."
            )

        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=True),
            },
        ]

    async def _repair_quiz(
        self,
        invalid_payload: dict[str, Any],
        request: QuizGenerationRequest,
        difficulty_plan: dict[Difficulty, int],
        validation_error: str,
    ) -> QuizResponse | None:
        target_sequence = difficulty_sequence(difficulty_plan)
        repair_payload = {
            "task": "Repair this quiz JSON so it passes strict production validation.",
            "validation_error": validation_error,
            "request": {
                "topic": request.topic,
                "difficulty_mode": request.difficulty_mode,
                "total_questions": request.total_questions,
                "mode": request.mode,
            },
            "required_difficulty_sequence": target_sequence,
            "invalid_quiz": invalid_payload,
            "hard_rules": [
                "Return JSON only.",
                "Keep exactly quiz_meta and questions as top-level keys.",
                "Every question must have one and only one correct answer.",
                "Never use all of the above, none of the above, both A and B, or cannot be determined.",
                "If an existing question has multiple true answers, rewrite the question and options.",
                "Preserve the requested topic, question count, and difficulty sequence.",
            ],
        }

        try:
            completion = await self._call_repair_model(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a strict quiz JSON repair engine. Return valid JSON only. "
                            "Repair ambiguity and shortcut options by rewriting the affected MCQ."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(repair_payload, ensure_ascii=True),
                    },
                ],
                max_tokens=self._max_completion_tokens(request),
            )
            content = completion.choices[0].message.content or ""
            payload = self._parse_json(content)
            payload = self._normalize_payload_contract(payload, request, difficulty_plan)
            quiz = QuizResponse.model_validate(payload)
            self._validate_generation_contract(quiz, request, difficulty_plan)
            return quiz
        except (OpenAIError, json.JSONDecodeError, ValidationError, QuizValidationError):
            return None

    async def _call_repair_model(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
    ) -> Any:
        last_error: OpenAIError | None = None
        for model in get_groq_models():
            try:
                return await self._create_chat_completion(
                    model=model,
                    messages=messages,
                    temperature=0.05,
                    top_p=0.85,
                    max_tokens=max_tokens,
                )
            except RateLimitError as exc:
                last_error = exc
                continue
        if last_error:
            raise last_error
        raise QuizGenerationError("No Groq model is configured.")

    def _generate_local_quiz(
        self,
        request: QuizGenerationRequest,
        difficulty_plan: dict[Difficulty, int],
    ) -> QuizResponse:
        target_sequence = difficulty_sequence(difficulty_plan)
        skill_cycle = ("concept", "application", "logic", "syntax")
        answers = ("A", "B", "C", "D")

        questions: list[dict[str, Any]] = []
        for index, difficulty in enumerate(target_sequence, start=1):
            skill_tag = skill_cycle[(index - 1) % len(skill_cycle)]
            correct_answer = answers[(index - 1) % len(answers)]
            correct_option = self._local_correct_option(skill_tag)
            distractors = self._local_distractors(skill_tag)
            option_values = [*distractors]
            option_values.insert(answers.index(correct_answer), correct_option)

            questions.append(
                {
                    "id": index,
                    "question": self._local_question_stem(
                        request.topic,
                        difficulty,
                        skill_tag,
                        index,
                    ),
                    "options": dict(zip(answers, option_values, strict=True)),
                    "correct_answer": correct_answer,
                    "explanation": self._local_explanation(request.topic, skill_tag),
                    "difficulty": difficulty,
                    "skill_tag": skill_tag,
                }
            )

        payload = {
            "quiz_meta": {
                "title": f"{request.topic} Practice Quiz"[:120],
                "topic": request.topic,
                "difficulty_mode": request.difficulty_mode,
                "total_questions": request.total_questions,
            },
            "questions": questions,
        }
        quiz = QuizResponse.model_validate(payload)
        self._validate_generation_contract(quiz, request, difficulty_plan)
        return quiz

    def _local_question_stem(
        self,
        topic: str,
        difficulty: Difficulty,
        skill_tag: str,
        index: int,
    ) -> str:
        templates = {
            "concept": (
                "For {topic}, checkpoint {index} at {difficulty} level, which "
                "choice best supports a clear conceptual understanding?"
            ),
            "application": (
                "In a {difficulty} {topic} practice scenario, checkpoint {index}, "
                "which action is the most reliable way to apply the idea?"
            ),
            "logic": (
                "While reasoning through {topic}, checkpoint {index} at "
                "{difficulty} level, which habit most reduces mistakes?"
            ),
            "syntax": (
                "When following rules or notation in {topic}, checkpoint {index} "
                "at {difficulty} level, what should come first?"
            ),
        }
        return templates[skill_tag].format(
            topic=topic,
            difficulty=difficulty,
            index=index,
        )

    def _local_correct_option(self, skill_tag: str) -> str:
        correct_options = {
            "concept": "Define the key idea and connect it to a concrete example.",
            "application": "Identify the goal, apply the relevant rule, and verify the result.",
            "logic": "Check each assumption against the evidence before choosing.",
            "syntax": "Use the required format consistently and test it on a small case.",
        }
        return correct_options[skill_tag]

    def _local_distractors(self, skill_tag: str) -> list[str]:
        distractors = {
            "concept": [
                "Memorize an isolated phrase without checking its meaning.",
                "Skip examples and move directly to the final answer.",
                "Treat every related term as if it means the same thing.",
            ],
            "application": [
                "Choose a method before reading the complete situation.",
                "Change several variables at once and ignore the outcome.",
                "Copy a previous answer even when the conditions are different.",
            ],
            "logic": [
                "Accept the first option that contains familiar wording.",
                "Ignore information that conflicts with the preferred answer.",
                "Make a conclusion before comparing the available choices.",
            ],
            "syntax": [
                "Guess the format after completing the entire solution.",
                "Mix two conventions because they look mostly similar.",
                "Leave small rule violations for review after submission.",
            ],
        }
        return distractors[skill_tag]

    def _local_explanation(self, topic: str, skill_tag: str) -> str:
        explanations = {
            "concept": (
                f"Strong {topic} learning starts with the idea and a specific example."
            ),
            "application": (
                f"Reliable {topic} application uses the goal, the rule, and a result check."
            ),
            "logic": (
                f"Good {topic} reasoning depends on testing assumptions against evidence."
            ),
            "syntax": (
                f"Accurate {topic} work depends on consistent rules before larger steps."
            ),
        }
        return explanations[skill_tag]

    def _parse_json(self, raw_content: str) -> dict[str, Any]:
        try:
            payload = json.loads(raw_content)
        except json.JSONDecodeError:
            start = raw_content.find("{")
            end = raw_content.rfind("}")
            if start == -1 or end == -1 or start >= end:
                raise
            payload = json.loads(raw_content[start : end + 1])

        if not isinstance(payload, dict):
            raise QuizValidationError("Top-level quiz payload must be an object.")
        return payload

    def _normalize_payload_contract(
        self,
        payload: dict[str, Any],
        request: QuizGenerationRequest,
        difficulty_plan: dict[Difficulty, int],
    ) -> dict[str, Any]:
        questions = payload.get("questions")
        if not isinstance(questions, list):
            raise QuizValidationError("Quiz payload must include a questions array.")

        target_sequence = difficulty_sequence(difficulty_plan)
        normalized_questions: list[dict[str, Any]] = []
        for index, question in enumerate(questions[: request.total_questions], start=1):
            if not isinstance(question, dict):
                raise QuizValidationError("Every question must be an object.")

            options = question.get("options", {})
            if isinstance(options, list):
                options = {
                    key: value
                    for key, value in zip(("A", "B", "C", "D"), options, strict=False)
                }
            if not isinstance(options, dict):
                raise QuizValidationError("Question options must be an object.")

            normalized_options = {
                str(key).upper(): value
                for key, value in options.items()
                if str(key).upper() in {"A", "B", "C", "D"}
            }

            normalized_questions.append(
                {
                    "id": index,
                    "question": question.get("question", ""),
                    "options": normalized_options,
                    "correct_answer": str(question.get("correct_answer", "")).upper()[:1],
                    "explanation": question.get("explanation", ""),
                    "difficulty": target_sequence[index - 1],
                    "skill_tag": self._normalize_skill_tag(question.get("skill_tag")),
                }
            )

        return {
            "quiz_meta": {
                "title": self._normalize_title(payload, request),
                "topic": request.topic,
                "difficulty_mode": request.difficulty_mode,
                "total_questions": request.total_questions,
            },
            "questions": normalized_questions,
        }

    def _normalize_title(
        self,
        payload: dict[str, Any],
        request: QuizGenerationRequest,
    ) -> str:
        quiz_meta = payload.get("quiz_meta")
        title = ""
        if isinstance(quiz_meta, dict):
            title = str(quiz_meta.get("title") or "").strip()

        if title:
            return title[:120]
        return f"{request.topic} Quiz"

    def _normalize_skill_tag(self, value: Any) -> str:
        normalized = str(value or "").lower().strip()
        skill_map = {
            "analysis": "logic",
            "reasoning": "logic",
            "code": "syntax",
            "coding": "syntax",
            "definition": "concept",
            "theory": "concept",
            "applied": "application",
            "scenario": "application",
        }
        if normalized in {"logic", "syntax", "concept", "application"}:
            return normalized
        return skill_map.get(normalized, "concept")

    def _validate_generation_contract(
        self,
        quiz: QuizResponse,
        request: QuizGenerationRequest,
        difficulty_plan: dict[Difficulty, int],
    ) -> None:
        meta = quiz.quiz_meta
        if fingerprint(meta.topic) != fingerprint(request.topic):
            raise QuizValidationError("Quiz topic does not match the request topic.")

        if meta.difficulty_mode != request.difficulty_mode:
            raise QuizValidationError("Quiz difficulty mode does not match the request.")

        if meta.total_questions != request.total_questions:
            raise QuizValidationError("Quiz question count does not match the request.")

        actual_plan = Counter(question.difficulty for question in quiz.questions)
        for difficulty, expected_count in difficulty_plan.items():
            if actual_plan[difficulty] != expected_count:
                raise QuizValidationError(
                    f"Expected {expected_count} {difficulty} questions, "
                    f"got {actual_plan[difficulty]}."
                )

        expected_sequence = difficulty_sequence(difficulty_plan)
        actual_sequence = [question.difficulty for question in quiz.questions]
        if actual_sequence != expected_sequence:
            raise QuizValidationError("Question difficulties are not ordered easy to hard.")

        banned_option_values = {
            "all of the above",
            "none of the above",
            "both a and b",
            "both b and c",
            "cannot be determined",
        }
        for question in quiz.questions:
            normalized_options = {
                option.lower().strip(". ")
                for option in question.options.values()
            }
            if normalized_options & banned_option_values:
                raise QuizValidationError("Options contain vague shortcut answers.")

    def _mastery_level(self, accuracy_percent: float) -> str:
        if accuracy_percent >= 90:
            return "Expert"
        if accuracy_percent >= 75:
            return "Proficient"
        if accuracy_percent >= 55:
            return "Developing"
        return "Needs Focus"

    def _suggest_next_topics(
        self,
        topic: str,
        weak_areas: list[WeakArea],
        accuracy_percent: float,
    ) -> list[str]:
        if not weak_areas:
            return [
                f"Advanced applications of {topic}",
                f"Scenario-based {topic} practice",
                f"Timed mastery drill for {topic}",
            ]

        suggestions = [
            f"{topic} {area.skill_tag} fundamentals ({area.difficulty})"
            for area in weak_areas[:3]
        ]
        if accuracy_percent < 55:
            suggestions.append(f"{topic} beginner revision path")
        else:
            suggestions.append(f"{topic} mixed-difficulty practice set")
        return suggestions[:4]
