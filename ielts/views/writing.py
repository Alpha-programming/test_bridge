from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Avg
import json
import ast

from ..models import (
    WritingTest,
    UserWritingTest,
    WritingResult
)

from ..services.ai_selector import get_model_for_user
from ..services.ai_writing import evaluate_with_retry
from ..services.subscription import (
    can_use_ai,
    increment_ai,
    prepare_subscription
)


# =========================
# HELPERS
# =========================

def calculate_task_band(scores):
    values = [
        scores.get("task", 0),
        scores.get("coherence", 0),
        scores.get("lexical", 0),
        scores.get("grammar", 0),
    ]

    avg = sum(values) / 4
    return round(avg * 2) / 2


def calculate_final_band(t1, t2):
    if not t1 or not t2:
        return None

    final = (t1 + (t2 * 2)) / 3
    return round(final * 2) / 2


# =========================
# VIEWS
# =========================

@login_required
def writing_home(request):
    query = request.GET.get("q")

    tests = WritingTest.objects.all()

    if query:
        tests = tests.filter(title__icontains=query)

    tests = tests.order_by("-created_at")

    paginator = Paginator(tests, 6)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    results = WritingResult.objects.filter(
        user=request.user
    ).exclude(final_band__isnull=True).order_by("-submitted_at")[:10]

    progress_data = list(
        WritingResult.objects.filter(
            user=request.user
        )
        .exclude(final_band__isnull=True)
        .order_by("submitted_at")
        .values_list("final_band", flat=True)
    )

    progress_data = [float(x) for x in progress_data]

    sub = prepare_subscription(request.user)

    return render(request, "ielts/writing/writing_home.html", {
        "page_obj": page_obj,
        "results": results,
        "query": query,
        "progress_data": json.dumps(progress_data),
        "subscription": sub,
    })


@login_required
def start_writing(request, test_id):
    test = get_object_or_404(WritingTest, id=test_id)

    user_test, _ = UserWritingTest.objects.get_or_create(
        user=request.user,
        test=test
    )

    user_test.started_at = timezone.now()
    user_test.task1_answer = ""
    user_test.task2_answer = ""
    user_test.completed_at = None

    user_test.save()

    return redirect("ielts:writing_solve", user_test.id)


@login_required
def writing_solve(request, user_test_id):
    user_test = get_object_or_404(UserWritingTest, id=user_test_id)

    return render(request, "ielts/writing/solve_writing.html", {
        "user_test": user_test,
        "test": user_test.test,
        "task1": user_test.test.task1,
        "task2": user_test.test.task2,
    })


@login_required
def save_writing_answer(request):
    if request.method == "POST":
        user_test = UserWritingTest.objects.get(id=request.POST.get("user_test_id"))

        task = request.POST.get("task")
        answer = request.POST.get("answer")

        if task == "task1":
            user_test.task1_answer = answer
        else:
            user_test.task2_answer = answer

        user_test.save()

        return JsonResponse({"status": "saved"})


@login_required
def submit_writing(request, user_test_id):
    user_test = get_object_or_404(UserWritingTest, id=user_test_id)

    # 🔒 CHECK SUBSCRIPTION
    allowed, message = can_use_ai(request.user)
    if not allowed:
        return JsonResponse({"error": message}, status=403)

    increment_ai(request.user)

    config = get_model_for_user(request.user)

    if not config:
        return JsonResponse({"error": "Upgrade your plan to use AI"}, status=403)

    result, _ = WritingResult.objects.get_or_create(
        user=request.user,
        test=user_test.test,
        user_test=user_test
    )

    data, usage = evaluate_with_retry(
        user_test.task1_answer,
        user_test.task2_answer,
        config
    )

    # ❌ AI FAILED
    if not data:
        result.feedback = "AI evaluation failed. Please try again."
        result.status = "submitted"
        result.save()

        return redirect("ielts:writing_result", result.id)

    task1 = data.get("task1", {})
    task2 = data.get("task2", {})

    # save raw scores
    result.task1_task = task1.get("task")
    result.task1_coherence = task1.get("coherence")
    result.task1_lexical = task1.get("lexical")
    result.task1_grammar = task1.get("grammar")

    result.task2_task = task2.get("task")
    result.task2_coherence = task2.get("coherence")
    result.task2_lexical = task2.get("lexical")
    result.task2_grammar = task2.get("grammar")

    # bands
    result.task1_band = calculate_task_band(task1)
    result.task2_band = calculate_task_band(task2)

    result.final_band = calculate_final_band(
        result.task1_band,
        result.task2_band
    )

    result.feedback = json.dumps(data.get("feedback", {}))
    result.advanced = json.dumps(data.get("advanced", {}))
    result.status = "checked"

    result.save()

    user_test.completed_at = timezone.now()
    user_test.save()

    return redirect("ielts:writing_result", result.id)


@login_required
def writing_result(request, result_id):
    result = get_object_or_404(WritingResult, id=result_id)

    feedback = result.feedback

    # 🔥 FIX: handle python dict string
    if isinstance(feedback, str):
        try:
            feedback = json.loads(feedback)
        except:
            try:
                feedback = ast.literal_eval(feedback)
            except:
                feedback = {}

    advanced = {}

    if result.advanced:
        try:
            advanced = json.loads(result.advanced)
        except:
            advanced = {}

    feedback_task1 = feedback.get("task1", "")
    feedback_task2 = feedback.get("task2", "")
    improvements = feedback.get("improvements", [])

    def to_percent(value):
        if not value:
            return 0
        return round((value / 9) * 100)

    return render(request, "ielts/writing/result.html", {
        "result": result,
        "user_test": result.user_test,
        "feedback_task1": feedback_task1,
        "feedback_task2": feedback_task2,
        "improvements": improvements,
        "advanced": advanced,

        "t1_task_p": to_percent(result.task1_task),
        "t1_coherence_p": to_percent(result.task1_coherence),
        "t1_lexical_p": to_percent(result.task1_lexical),
        "t1_grammar_p": to_percent(result.task1_grammar),

        "t2_task_p": to_percent(result.task2_task),
        "t2_coherence_p": to_percent(result.task2_coherence),
        "t2_lexical_p": to_percent(result.task2_lexical),
        "t2_grammar_p": to_percent(result.task2_grammar),
    })