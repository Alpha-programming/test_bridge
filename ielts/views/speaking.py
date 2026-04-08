from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.core.paginator import Paginator
import json

from ..models import (
    SpeakingTest,
    SpeakingAttempt,
    SpeakingQuestion,
    UserSpeakingTest
)

from ..services.subscription import (
    can_use_ai,
    increment_ai,
    prepare_subscription
)

from ..services.speech import transcribe_audio
from ..services.evaluation import evaluate_full_speaking


# =========================
# HELPERS
# =========================

def round_band(score):
    return round(score * 2) / 2


# =========================
# VIEWS
# =========================

@login_required
def speaking_home(request):
    query = request.GET.get("q")

    tests = SpeakingTest.objects.all()

    if query:
        tests = tests.filter(title__icontains=query)

    tests = tests.order_by("-id")

    paginator = Paginator(tests, 6)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    user_tests = UserSpeakingTest.objects.filter(
        user=request.user,
        completed_at__isnull=False
    ).order_by("-completed_at")[:10]

    sub = prepare_subscription(request.user)

    return render(request, "ielts/speaking/speaking_home.html", {
        "page_obj": page_obj,
        "results": user_tests,
        "query": query,
        "subscription": sub,
    })


@login_required
def start_speaking(request, test_id):
    test = get_object_or_404(SpeakingTest, id=test_id)

    user_test, _ = UserSpeakingTest.objects.get_or_create(
        user=request.user,
        test=test
    )

    user_test.started_at = timezone.now()
    user_test.completed_at = None
    user_test.save()

    return redirect("ielts:speaking_solve", user_test.id)


@login_required
def solve_speaking(request, user_test_id):
    user_test = get_object_or_404(UserSpeakingTest, id=user_test_id)

    questions = user_test.test.questions.all()

    part1 = questions.filter(part=1)
    part2 = questions.filter(part=2).first()
    part3 = questions.filter(part=3)

    return render(request, "ielts/speaking/solve_speaking.html", {
        "user_test": user_test,
        "part1": part1,
        "part2": part2,
        "part3": part3,
    })


@login_required
def upload_speaking_answer(request):
    if request.method == "POST":
        audio = request.FILES.get("audio")
        question_id = request.POST.get("question_id")

        question = SpeakingQuestion.objects.get(id=question_id)

        attempt, _ = SpeakingAttempt.objects.update_or_create(
            user=request.user,
            question=question,
            test=question.test,
            defaults={
                "audio": audio
            }
        )

        return JsonResponse({"status": "saved"})


@login_required
def submit_speaking(request, user_test_id):
    # 🔒 AI LIMIT
    allowed, msg = can_use_ai(request.user)
    if not allowed:
        return HttpResponse(msg)

    increment_ai(request.user)

    user_test = get_object_or_404(UserSpeakingTest, id=user_test_id)

    attempts = SpeakingAttempt.objects.filter(
        user=request.user,
        test=user_test.test
    )

    full_text = ""

    # 1. TRANSCRIBE ALL
    for a in attempts:
        if not a.transcript:
            transcript = transcribe_audio(a.audio.path)
            a.transcript = transcript
            a.save()

        full_text += f"\nQ: {a.question.question_text}\nA: {a.transcript}\n"

    # 2. ONE AI CALL
    result = evaluate_full_speaking(full_text)

    # 3. SAVE RESULTS
    for a in attempts:
        a.fluency_score = result["fluency"]
        a.grammar_score = result["grammar"]
        a.vocabulary_score = result["lexical"]
        a.pronunciation_score = result["pronunciation"]

        scores = [
            result.get("fluency", 0),
            result.get("grammar", 0),
            result.get("lexical", 0),
            result.get("pronunciation", 0),
        ]

        avg = sum(scores) / 4
        band = round(avg * 2) / 2

        a.overall_band = band
        a.feedback = json.dumps(result.get("feedback", {}))
        a.save()

    user_test.completed_at = timezone.now()
    user_test.save()

    return redirect("ielts:speaking_result", user_test.id)


@login_required
def speaking_result(request, user_test_id):
    user_test = get_object_or_404(UserSpeakingTest, id=user_test_id)

    attempts = SpeakingAttempt.objects.filter(
        user=request.user,
        question__test=user_test.test
    ).select_related("question").order_by("created_at")

    # parse feedback
    for a in attempts:
        try:
            a.feedback_parsed = json.loads(a.feedback)
        except:
            a.feedback_parsed = {}

    def avg(lst):
        return round(sum(lst) / len(lst), 1) if lst else 0

    fluency = [a.fluency_score for a in attempts if a.fluency_score]
    grammar = [a.grammar_score for a in attempts if a.grammar_score]
    lexical = [a.vocabulary_score for a in attempts if a.vocabulary_score]
    pron = [a.pronunciation_score for a in attempts if a.pronunciation_score]

    avg_scores = {
        "fluency": avg(fluency),
        "grammar": avg(grammar),
        "lexical": avg(lexical),
        "pron": avg(pron),
    }

    avg_band = round(
        (avg_scores["fluency"] +
         avg_scores["grammar"] +
         avg_scores["lexical"] +
         avg_scores["pron"]) / 4 * 2
    ) / 2

    def to_percent(v):
        return round((v / 9) * 100) if v else 0

    return render(request, "ielts/speaking/result.html", {
        "attempts": attempts,
        "test": user_test.test,
        "avg_band": avg_band,
        "avg_scores": avg_scores,

        "fluency_p": to_percent(avg_scores["fluency"]),
        "grammar_p": to_percent(avg_scores["grammar"]),
        "lexical_p": to_percent(avg_scores["lexical"]),
        "pron_p": to_percent(avg_scores["pron"]),
    })