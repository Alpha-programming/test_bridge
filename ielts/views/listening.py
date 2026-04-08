from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone
from collections import Counter
import json

from ..models import (
    ListeningTest,
    UserListeningTest,
    UserListeningAnswer,
    ListeningQuestion,
    ListeningAIReport
)

from ..services.subscription import (
    can_use_ai,
    can_start_test,
    increment_ai,
    increment_test,
    prepare_subscription
)

from ..services.listening_analytics import build_user_listening_profile
from ..services.ai_listening_overall import analyze_listening


# =========================
# HELPERS
# =========================

def normalize(text):
    return text.strip().lower()


def check_answer(correct, user):
    correct = normalize(correct)
    user = normalize(user)

    if "/" in correct or "," in correct:
        parts = correct.replace(",", "/").split("/")
        parts = [p.strip() for p in parts]
        return user in parts

    if user == correct:
        return True

    return False


def calculate_band(score):
    if score >= 39: return 9
    elif score >= 37: return 8.5
    elif score >= 35: return 8
    elif score >= 32: return 7.5
    elif score >= 30: return 7
    elif score >= 26: return 6.5
    elif score >= 23: return 6
    elif score >= 18: return 5.5
    elif score >= 16: return 5
    else: return 4.5


# =========================
# VIEWS
# =========================

@login_required
def listening_home(request):
    query = request.GET.get("q")

    tests = ListeningTest.objects.all()

    if query:
        tests = tests.filter(title__icontains=query)

    tests = tests.order_by("-created_at")

    paginator = Paginator(tests, 6)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    user_tests = UserListeningTest.objects.filter(
        user=request.user,
        completed_at__isnull=False
    ).order_by("-completed_at")[:10]

    for ut in user_tests:
        ut.band = calculate_band(ut.score)

    progress_data = list(
        UserListeningTest.objects.filter(
            user=request.user,
            completed_at__isnull=False
        ).order_by("completed_at").values_list("score", flat=True)
    )

    progress_data = [calculate_band(s) for s in progress_data]

    all_tests = UserListeningTest.objects.filter(
        user=request.user,
        completed_at__isnull=False
    )

    profile = build_user_listening_profile(all_tests)

    ai_preview = None

    try:
        report = ListeningAIReport.objects.get(user=request.user)
        ai_preview = report.ai_response
    except:
        pass

    sub = prepare_subscription(request.user)

    return render(request, "ielts/listening/listening_home.html", {
        "page_obj": page_obj,
        "user_tests": user_tests,
        "progress_data": json.dumps(progress_data),
        "query": query,
        "profile": profile,
        "ai_preview": ai_preview,
        "total_tests": profile.get("total_tests", 0),
        "avg_score": profile.get("avg_score", 0),
        "avg_accuracy": profile.get("avg_accuracy", 0),
        "weak_types": profile.get("weak_types", {}),
        "subscription": sub,
    })


@login_required
def listening_overall_ai(request):
    allowed, msg = can_use_ai(request.user)
    if not allowed:
        return HttpResponse(msg)

    increment_ai(request.user)

    tests = UserListeningTest.objects.filter(
        user=request.user,
        completed_at__isnull=False
    )

    profile = build_user_listening_profile(tests)

    if not profile:
        return render(request, "ielts/listening/overall_ai.html", {
            "profile": {},
            "ai": {}
        })

    force = request.GET.get("refresh") == "1"

    report, _ = ListeningAIReport.objects.get_or_create(user=request.user)

    need_update = (
        force or
        not report.ai_response
    )

    if need_update:
        try:
            ai = analyze_listening(profile)

            report.total_tests = profile["total_tests"]
            report.avg_score = profile["avg_score"]
            report.avg_accuracy = profile["avg_accuracy"]
            report.weak_types = profile["weak_types"]

            report.ai_response = ai
            report.save()

        except:
            pass

    return render(request, "ielts/listening/overall_ai.html", {
        "profile": report,
        "ai": report.ai_response
    })


@login_required
def start_listening(request, test_id):
    allowed, msg = can_start_test(request.user)
    if not allowed:
        return HttpResponse(msg)

    increment_test(request.user)

    test = get_object_or_404(ListeningTest, id=test_id)

    user_test, _ = UserListeningTest.objects.get_or_create(
        user=request.user,
        test=test
    )

    if user_test.completed_at:
        user_test.score = 0
        user_test.completed_at = None
        user_test.save()
        user_test.answers.all().delete()

    return redirect("ielts:listening_solve", user_test.id)


@login_required
def solve_listening(request, user_test_id):
    user_test = get_object_or_404(UserListeningTest, id=user_test_id)

    sections = user_test.test.sections.prefetch_related(
        "groups__questions__options"
    )

    # 🔥 UNIQUE OPTIONS FIX (MATCH)
    for section in sections:
        for group in section.groups.all():
            if group.group_type == "MATCH":
                seen = set()
                unique_options = []

                for q in group.questions.all():
                    for opt in q.options.all():
                        if opt.label not in seen:
                            seen.add(opt.label)
                            unique_options.append(opt)

                group.unique_options = unique_options

    return render(request, "ielts/listening/solve_listening.html", {
        "user_test": user_test,
        "test": user_test.test,
        "sections": sections,
    })


@login_required
def save_listening_answer(request):
    if request.method == "POST":
        q_id = request.POST.get("question_id")
        answer = request.POST.get("answer")
        user_test_id = request.POST.get("user_test_id")

        question = ListeningQuestion.objects.get(id=q_id)

        is_correct = check_answer(question.correct_answer, answer)

        UserListeningAnswer.objects.update_or_create(
            user_test_id=user_test_id,
            question=question,
            defaults={
                "answer": answer,
                "is_correct": is_correct
            }
        )

        return JsonResponse({"status": "saved"})


@login_required
def submit_listening(request, user_test_id):
    user_test = get_object_or_404(UserListeningTest, id=user_test_id)

    answers = user_test.answers.all()
    score = answers.filter(is_correct=True).count()
    total = answers.count()

    mistakes = []

    for ans in answers:
        if not ans.is_correct:
            mistakes.append(ans.question.group.group_type)

    mistake_stats = Counter(mistakes)

    user_test.score = score
    user_test.completed_at = timezone.now()

    user_test.mistake_stats = json.dumps(mistake_stats)
    user_test.accuracy = round((score / total) * 100, 1) if total else 0

    user_test.save()

    return redirect("ielts:listening_result", user_test.id)


@login_required
def listening_result(request, user_test_id):
    user_test = get_object_or_404(UserListeningTest, id=user_test_id)

    answers = user_test.answers.select_related("question")
    answer_map = {a.question.number: a for a in answers}

    questions = ListeningQuestion.objects.filter(
        group__section__test=user_test.test
    ).order_by("number")

    rows = []

    for q in questions:
        ans_obj = answer_map.get(q.number)

        rows.append({
            "n": q.number,
            "ans": ans_obj.answer if ans_obj else "—",
            "ok": ans_obj.is_correct if ans_obj else False,
            "answered": True if ans_obj else False
        })

    left_rows = [r for r in rows if r["n"] <= 20]
    right_rows = [r for r in rows if r["n"] > 20]

    result = {
        "score": user_test.score,
        "band": calculate_band(user_test.score),
        "test": user_test.test,
        "user": request.user
    }

    return render(request, "ielts/listening/result.html", {
        "result": result,
        "left_rows": left_rows,
        "right_rows": right_rows
    })