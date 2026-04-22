import json
from django.conf import settings
from django.db.models import Avg, Max
from openai import OpenAI

from topik.models import ExamAttempt, UserProgressInsight


def get_openai_client():
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def update_progress_advice_for_user(user):
    submitted_attempts = ExamAttempt.objects.filter(
        user=user,
        status=ExamAttempt.Status.SUBMITTED
    ).select_related("exam").order_by("-submitted_at")

    completed_attempts = submitted_attempts.count()

    insight, _ = UserProgressInsight.objects.get_or_create(user=user)

    # ✅ prevent re-calling AI
    if insight.based_on_attempt_count == completed_attempts:
        return insight

    # ✅ not enough data → skip AI
    if completed_attempts < 2:
        insight.summary = "Complete more tests to unlock personalized insights."
        insight.focus_area = ""
        insight.advice_items = []
        insight.based_on_attempt_count = completed_attempts
        insight.save()
        return insight

    # ======================
    # DATA
    # ======================
    avg_score = round(submitted_attempts.aggregate(v=Avg("total_score"))["v"] or 0)
    best_score = round(submitted_attempts.aggregate(v=Max("total_score"))["v"] or 0)

    reading_avg = round(submitted_attempts.aggregate(v=Avg("reading_score"))["v"] or 0)
    listening_avg = round(submitted_attempts.aggregate(v=Avg("listening_score"))["v"] or 0)
    writing_avg = round(submitted_attempts.aggregate(v=Avg("writing_score"))["v"] or 0)

    recent_scores = list(submitted_attempts.values_list("total_score", flat=True)[:5])

    payload = {
        "avg_score": avg_score,
        "best_score": best_score,
        "reading": reading_avg,
        "listening": listening_avg,
        "writing": writing_avg,
        "recent_scores": recent_scores,
    }

    # ======================
    # AI CALL
    # ======================
    client = get_openai_client()

    try:
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are a TOPIK coach. Give short practical advice. "
                                "Do NOT judge scores harshly. Just guide improvement."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps(payload)}],
                },
            ],
        )

        text = response.output_text

        # ⚡ simple parsing (cheap)
        insight.summary = text[:300]
        insight.focus_area = min(
            {"Reading": reading_avg, "Listening": listening_avg, "Writing": writing_avg},
            key=lambda x: {"Reading": reading_avg, "Listening": listening_avg, "Writing": writing_avg}[x]
        )
        insight.advice_items = text.split(". ")[:3]

    except Exception:
        insight.summary = "Unable to generate advice right now."
        insight.focus_area = ""
        insight.advice_items = []

    insight.based_on_attempt_count = completed_attempts
    insight.save()

    return insight