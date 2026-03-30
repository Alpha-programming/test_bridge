import json
from typing import Any

from django.conf import settings
from openai import OpenAI

from topik.models import WritingSubmission, WritingTask


def get_openai_client() -> OpenAI:
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is missing")
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _build_prompt(submission: WritingSubmission) -> str:
    task = submission.task
    exam = submission.attempt.exam

    base = f"""
You are grading a TOPIK writing response.

Exam title: {exam.title}
Level: {exam.get_level_display()}
Task number: {task.task_number}
Task type: {task.get_task_type_display()}
Task max score: {task.score}
Instruction: {task.instruction or '-'}
Prompt: {task.prompt or '-'}
Minimum words: {task.min_words or 0}
Maximum words: {task.max_words or 0}

Student answer:
{submission.answer_text or ''}

Return a fair, strict evaluation for TOPIK-style writing.
Score must never exceed the task max score.
"""

    if task.task_type == WritingTask.TaskType.GRAPH_WRITING:
        base += """
Focus on:
- task completion
- relevance to the graph/data
- clarity
- grammar
- vocabulary
- organization
"""
    elif task.task_type == WritingTask.TaskType.ESSAY:
        base += """
Focus on:
- task response
- coherence and structure
- grammar accuracy
- vocabulary range
- natural Korean expression
- development of ideas
"""
    else:
        base += """
This is a gap-fill task. Evaluate each blank using the reference answer and scoring note.
Accept semantically equivalent answers if they fit the sentence naturally.
"""

    return base.strip()


def score_gap_fill_submission(submission: WritingSubmission) -> WritingSubmission:
    task = submission.task
    blanks = list(task.blanks.all().order_by("blank_order"))
    user_parts = [normalize_text(p) for p in (submission.answer_text or "").split("||")]

    if not blanks:
        submission.is_correct = False
        submission.ai_score = 0
        submission.final_score = 0
        submission.score_awarded = 0
        submission.ai_feedback = {
            "task_type": "gap_fill",
            "feedback_summary": "No blanks were configured for this task."
        }
        submission.save(update_fields=[
            "is_correct",
            "ai_score",
            "final_score",
            "score_awarded",
            "ai_feedback",
            "updated_at",
        ])
        return submission

    blank_max_score = task.score / len(blanks)

    blank_payload = []
    for index, blank in enumerate(blanks):
        blank_payload.append({
            "blank_order": blank.blank_order,
            "student_answer": user_parts[index] if index < len(user_parts) else "",
            "reference_answer": normalize_text(blank.correct_answer or ""),
            "scoring_note": blank.scoring_note or "",
            "max_score": blank_max_score,
        })

    prompt = f"""
You are grading a TOPIK gap-fill writing task.

Task title: {task.title or '-'}
Task prompt:
{task.prompt or '-'}

Task instruction:
{task.instruction or '-'}

The task has {len(blanks)} blanks.
Each blank has a maximum score of {blank_max_score}.

For each blank:
- compare the student's answer against the reference answer
- use the scoring note if provided
- allow semantically equivalent answers
- check meaning, grammar, naturalness, and sentence fit
- give full score if clearly correct and natural
- give partial score if meaning is close but grammar or fit is weak
- give 0 if incorrect, unnatural, or missing

Return JSON only.
"""

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "blank_scores": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "blank_order": {"type": "integer"},
                        "is_acceptable": {"type": "boolean"},
                        "score": {"type": "number"},
                        "reason": {"type": "string"}
                    },
                    "required": ["blank_order", "is_acceptable", "score", "reason"]
                }
            },
            "feedback_summary": {"type": "string"}
        },
        "required": ["blank_scores", "feedback_summary"]
    }

    try:
        client = get_openai_client()
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "You are a strict but fair TOPIK writing examiner. Return only structured evaluation data."
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_text", "text": json.dumps(blank_payload, ensure_ascii=False)}
                    ],
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "topik_gap_fill_score",
                    "strict": True,
                    "schema": schema,
                }
            },
        )

        raw_text = getattr(response, "output_text", "") or ""
        data: dict[str, Any] = json.loads(raw_text)

    except Exception as e:
        submission.is_correct = False
        submission.ai_score = 0
        submission.final_score = 0
        submission.score_awarded = 0
        submission.ai_feedback = {
            "task_type": "gap_fill",
            "error": str(e),
            "feedback_summary": "Automatic gap-fill scoring failed."
        }
        submission.save(update_fields=[
            "is_correct",
            "ai_score",
            "final_score",
            "score_awarded",
            "ai_feedback",
            "updated_at",
        ])
        return submission

    blank_scores = data.get("blank_scores", [])
    total_score = 0
    acceptable_count = 0

    normalized_blank_scores = []
    for item in blank_scores:
        score = float(item.get("score", 0))
        if score < 0:
            score = 0
        if score > blank_max_score:
            score = blank_max_score

        total_score += score
        if item.get("is_acceptable"):
            acceptable_count += 1

        normalized_blank_scores.append({
            "blank_order": item.get("blank_order"),
            "is_acceptable": item.get("is_acceptable", False),
            "score": score,
            "reason": item.get("reason", ""),
        })

    if total_score > task.score:
        total_score = float(task.score)

    submission.is_correct = acceptable_count == len(blanks)
    submission.ai_score = float(total_score)
    submission.final_score = float(total_score)
    submission.score_awarded = round(total_score)
    submission.ai_feedback = {
        "task_type": "gap_fill",
        "blank_scores": normalized_blank_scores,
        "acceptable_count": acceptable_count,
        "total_blanks": len(blanks),
        "feedback_summary": data.get("feedback_summary", ""),
    }
    submission.save(update_fields=[
        "is_correct",
        "ai_score",
        "final_score",
        "score_awarded",
        "ai_feedback",
        "updated_at",
    ])
    return submission


def score_writing_submission(submission: WritingSubmission) -> WritingSubmission:
    task = submission.task

    # GAP FILL -> AI reference-guided scoring
    if task.task_type == WritingTask.TaskType.GAP_FILL:
        return score_gap_fill_submission(submission)

    answer_text = (submission.answer_text or "").strip()
    if not answer_text:
        submission.is_correct = False
        submission.ai_score = 0
        submission.final_score = 0
        submission.score_awarded = 0
        submission.ai_feedback = {
            "score": 0,
            "grammar_score": 0,
            "vocabulary_score": 0,
            "coherence_score": 0,
            "task_completion_score": 0,
            "strengths": [],
            "improvements": ["No answer submitted."],
            "feedback_summary": "No answer was provided."
        }
        submission.save(update_fields=[
            "is_correct",
            "ai_score",
            "final_score",
            "score_awarded",
            "ai_feedback",
            "updated_at",
        ])
        return submission

    prompt = _build_prompt(submission)

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "score": {"type": "number"},
            "grammar_score": {"type": "number"},
            "vocabulary_score": {"type": "number"},
            "coherence_score": {"type": "number"},
            "task_completion_score": {"type": "number"},
            "strengths": {
                "type": "array",
                "items": {"type": "string"}
            },
            "improvements": {
                "type": "array",
                "items": {"type": "string"}
            },
            "feedback_summary": {"type": "string"}
        },
        "required": [
            "score",
            "grammar_score",
            "vocabulary_score",
            "coherence_score",
            "task_completion_score",
            "strengths",
            "improvements",
            "feedback_summary"
        ]
    }

    try:
        client = get_openai_client()
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are a strict TOPIK writing examiner. "
                                "Return only structured evaluation data."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "topik_writing_score",
                    "strict": True,
                    "schema": schema,
                }
            },
        )

        raw_text = getattr(response, "output_text", "") or ""
        data: dict[str, Any] = json.loads(raw_text)

    except Exception as e:
        submission.is_correct = False
        submission.ai_score = 0
        submission.final_score = 0
        submission.score_awarded = 0
        submission.ai_feedback = {
            "error": str(e),
            "feedback_summary": "Automatic scoring failed."
        }
        submission.save(update_fields=[
            "is_correct",
            "ai_score",
            "final_score",
            "score_awarded",
            "ai_feedback",
            "updated_at",
        ])
        return submission

    score = float(data.get("score", 0))
    if score < 0:
        score = 0
    if score > task.score:
        score = float(task.score)

    submission.is_correct = False
    submission.ai_score = score
    submission.final_score = score
    submission.score_awarded = round(score)
    submission.ai_feedback = data
    submission.save(update_fields=[
        "is_correct",
        "ai_score",
        "final_score",
        "score_awarded",
        "ai_feedback",
        "updated_at",
    ])
    return submission