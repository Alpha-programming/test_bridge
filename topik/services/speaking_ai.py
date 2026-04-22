import json
from django.conf import settings
from django.db.models import Avg
from openai import OpenAI


def get_openai_client():
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is missing")
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def clamp_score(value, min_value=0.0, max_value=9.0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0
    return max(min_value, min(max_value, value))


def transcribe_speaking_audio(file_path: str) -> str:
    client = get_openai_client()

    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=audio_file,
        )

    return (transcript.text or "").strip()


def evaluate_speaking_answer(answer):
    client = get_openai_client()

    transcript = (answer.transcript or "").strip()
    normalized_transcript = " ".join(transcript.split())
    word_count = len(normalized_transcript.split())

    if not normalized_transcript:
        answer.ai_score = 0
        answer.fluency_score = 0
        answer.grammar_score = 0
        answer.vocabulary_score = 0
        answer.pronunciation_score = 0
        answer.task_completion_score = 0
        answer.ai_feedback = {
            "language_valid": True,
            "task_completion_score": 0,
            "strengths": [],
            "improvements": ["No usable transcript was provided."],
            "feedback_summary": "No usable transcript was provided.",
        }
        answer.save(update_fields=[
            "ai_score",
            "fluency_score",
            "grammar_score",
            "vocabulary_score",
            "pronunciation_score",
            "task_completion_score",
            "ai_feedback",
        ])
        return answer

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "language_valid": {"type": "boolean"},
            "fluency_score": {"type": "number"},
            "grammar_score": {"type": "number"},
            "vocabulary_score": {"type": "number"},
            "pronunciation_score": {"type": "number"},
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
            "language_valid",
            "fluency_score",
            "grammar_score",
            "vocabulary_score",
            "pronunciation_score",
            "task_completion_score",
            "strengths",
            "improvements",
            "feedback_summary"
        ]
    }

    prompt = f"""
You are a very strict Korean speaking evaluator.

Evaluate the user's Korean speaking response harshly and realistically.
Do NOT be generous.
Do NOT inflate scores.

Scoring guide:
- 0 to 2 = extremely poor
- 3 = very weak
- 4 = weak
- 5 = basic / average
- 6 = acceptable but not strong
- 7 = good and clearly above average
- 8 = very strong and advanced
- 9 = excellent, highly natural, near-native level

Rules:
- If the response is short, incomplete, repetitive, unnatural, or off-topic, lower the score.
- If grammar errors are frequent, lower the score.
- If vocabulary is simple or repetitive, lower the score.
- If the response lacks structure or logical flow, lower the score.
- If the transcript sounds unnatural for Korean, lower the score.
- If the answer is mostly not in Korean, set language_valid to false.
- Only give 8 or 9 if the response is truly excellent.

Question:
{answer.question.prompt}

Part:
{answer.question.get_part_display()}

Type:
{answer.question.get_question_type_display()}

Difficulty:
{answer.question.get_difficulty_display()}

Transcript:
{normalized_transcript}

Return strict JSON only.
"""

    response = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are a strict Korean speaking examiner. "
                            "Score conservatively. "
                            "Evaluate Korean speaking only. "
                            "If the response is mostly not Korean, mark language_valid as false."
                        )
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt
                    }
                ],
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "speaking_evaluation",
                "strict": True,
                "schema": schema,
            }
        }
    )

    raw_text = getattr(response, "output_text", "") or ""
    if not raw_text.strip():
        raise ValueError("Model returned empty output_text.")

    data = json.loads(raw_text)

    language_valid = bool(data.get("language_valid", True))

    fluency = clamp_score(data.get("fluency_score", 0))
    grammar = clamp_score(data.get("grammar_score", 0))
    vocabulary = clamp_score(data.get("vocabulary_score", 0))
    pronunciation = clamp_score(data.get("pronunciation_score", 0))
    task_completion = clamp_score(data.get("task_completion_score", 0))

    if not language_valid:
        fluency = min(fluency, 1.5)
        grammar = min(grammar, 1.5)
        vocabulary = min(vocabulary, 1.5)
        pronunciation = min(pronunciation, 2.0)
        task_completion = min(task_completion, 1.5)

    if word_count < 5:
        fluency = min(fluency, 1.5)
        grammar = min(grammar, 1.5)
        vocabulary = min(vocabulary, 1.5)
        pronunciation = min(pronunciation, 2.0)
        task_completion = min(task_completion, 1.5)
    elif word_count < 12:
        fluency = min(fluency, 3.0)
        grammar = min(grammar, 3.0)
        vocabulary = min(vocabulary, 3.0)
        pronunciation = min(pronunciation, 4.0)
        task_completion = min(task_completion, 3.0)
    elif word_count < 25:
        fluency = min(fluency, 4.5)
        grammar = min(grammar, 4.5)
        vocabulary = min(vocabulary, 4.5)
        task_completion = min(task_completion, 4.5)
    elif word_count < 40:
        fluency = min(fluency, 5.5)
        grammar = min(grammar, 5.5)
        vocabulary = min(vocabulary, 5.5)
        task_completion = min(task_completion, 5.5)

    overall = round((fluency + grammar + vocabulary + pronunciation + task_completion) / 5, 1)

    answer.ai_score = overall
    answer.fluency_score = round(fluency, 1)
    answer.grammar_score = round(grammar, 1)
    answer.vocabulary_score = round(vocabulary, 1)
    answer.pronunciation_score = round(pronunciation, 1)
    answer.task_completion_score = round(task_completion, 1)
    answer.ai_feedback = {
        "language_valid": language_valid,
        "task_completion_score": round(task_completion, 1),
        "strengths": data.get("strengths", []),
        "improvements": data.get("improvements", []),
        "feedback_summary": data.get("feedback_summary", ""),
    }

    answer.save(update_fields=[
        "ai_score",
        "fluency_score",
        "grammar_score",
        "vocabulary_score",
        "pronunciation_score",
        "task_completion_score",
        "ai_feedback",
    ])

    return answer


def evaluate_full_speaking_attempt(attempt):
    answers = attempt.answers.all()

    if not answers.exists():
        attempt.overall_score = 0
        attempt.ai_feedback = {
            "overall_score": 0,
            "feedback_summary": "No answers provided."
        }
        attempt.save(update_fields=["overall_score", "ai_feedback"])
        return attempt

    avg_ai = answers.aggregate(v=Avg("ai_score"))["v"] or 0
    avg_fluency = answers.aggregate(v=Avg("fluency_score"))["v"] or 0
    avg_grammar = answers.aggregate(v=Avg("grammar_score"))["v"] or 0
    avg_vocab = answers.aggregate(v=Avg("vocabulary_score"))["v"] or 0
    avg_pronunciation = answers.aggregate(v=Avg("pronunciation_score"))["v"] or 0
    avg_task_completion = answers.aggregate(v=Avg("task_completion_score"))["v"] or 0

    section_scores = {
        "Fluency": round(avg_fluency, 1),
        "Grammar": round(avg_grammar, 1),
        "Vocabulary": round(avg_vocab, 1),
        "Pronunciation": round(avg_pronunciation, 1),
        "Task Completion": round(avg_task_completion, 1),
    }

    weakest_skill = min(section_scores, key=section_scores.get)
    strongest_skill = max(section_scores, key=section_scores.get)

    attempt.overall_score = round(avg_ai, 1)
    attempt.ai_feedback = {
        "overall_score": round(avg_ai, 1),
        "average_fluency": round(avg_fluency, 1),
        "average_grammar": round(avg_grammar, 1),
        "average_vocabulary": round(avg_vocab, 1),
        "average_pronunciation": round(avg_pronunciation, 1),
        "average_task_completion": round(avg_task_completion, 1),
        "weakest_skill": weakest_skill,
        "strongest_skill": strongest_skill,
        "feedback_summary": "AI evaluation completed for this speaking test."
    }

    attempt.save(update_fields=["overall_score", "ai_feedback"])
    return attempt