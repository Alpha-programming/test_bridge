from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.core.paginator import Paginator
from collections import Counter
import json
import re
from datetime import timedelta

from ..models import (
    ReadingTest, UserReadingTest, Question, UserAnswer,
    ReadingAIReport, Subscription
)

from ..services.subscription import (
    can_use_ai,
    can_start_test,
    increment_ai,
    increment_test,
    prepare_subscription
)

from ..services.reading_analytics import build_user_reading_profile
from ..services.ai_reading_overall import analyze_overall


# =========================
# HELPERS
# =========================

def normalize(text):
    return text.strip().lower()


def check_answer(correct, user):
    correct = normalize(correct)
    user = normalize(user)

    if "/" in correct or "," in correct:
        parts = re.split(r"[\/,]", correct)
        parts = [p.strip() for p in parts]
        return user in parts

    optional_removed = re.sub(r"\(.*?\)", "", correct).strip()

    if user == correct or user == optional_removed:
        return True

    clean_correct = re.sub(r"[^\w\s]", "", correct)
    clean_user = re.sub(r"[^\w\s]", "", user)

    if clean_user == clean_correct:
        return True

    if clean_user in clean_correct or clean_correct in clean_user:
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
def reading_home(request):
    query = request.GET.get("q")

    tests = ReadingTest.objects.all()

    if query:
        tests = tests.filter(title__icontains=query)

    tests = tests.order_by("-created_at")

    paginator = Paginator(tests, 6)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    user_tests = UserReadingTest.objects.filter(
        user=request.user,
        completed_at__isnull=False
    ).order_by("-completed_at")[:10]

    for ut in user_tests:
        ut.band = calculate_band(ut.score)

    progress_data = list(
        UserReadingTest.objects.filter(
            user=request.user,
            completed_at__isnull=False
        ).order_by("completed_at").values_list("score", flat=True)
    )

    progress_data = [calculate_band(s) for s in progress_data]

    all_tests = UserReadingTest.objects.filter(
        user=request.user,
        completed_at__isnull=False
    )

    total_tests = all_tests.count()
    avg_score = 0
    avg_accuracy = 0
    mistake_counter = Counter()

    ai_preview = None

    try:
        report = ReadingAIReport.objects.get(user=request.user)
        ai_preview = report.ai_response
    except:
        pass

    if total_tests > 0:
        total_score = sum([t.score for t in all_tests if t.score])
        avg_score = round(total_score / total_tests, 1)

        total_accuracy = sum([t.accuracy for t in all_tests])
        avg_accuracy = round(total_accuracy / total_tests, 1)

        for t in all_tests:
            if t.mistake_stats:
                try:
                    data = json.loads(t.mistake_stats)
                    mistake_counter.update(data)
                except:
                    pass

    sub = prepare_subscription(request.user)

    return render(request, "ielts/reading/reading_home.html", {
        "page_obj": page_obj,
        "user_tests": user_tests,
        "query": query,
        "progress_data": json.dumps(progress_data),
        "total_tests": total_tests,
        "avg_score": avg_score,
        "avg_accuracy": avg_accuracy,
        "weak_types": dict(mistake_counter.most_common(3)),
        "ai_preview": ai_preview,
        "subscription": sub,
    })


@login_required
def start_test(request, test_id):
    allowed, msg = can_start_test(request.user)
    if not allowed:
        return HttpResponse(msg)

    increment_test(request.user)

    test = get_object_or_404(ReadingTest, id=test_id)

    user_test, created = UserReadingTest.objects.get_or_create(
        user=request.user,
        test=test,
    )

    user_test.started_at = timezone.now()
    user_test.completed_at = None
    user_test.score = 0
    user_test.answers_json = {}
    user_test.save()

    user_test.answers.all().delete()

    return redirect("ielts:reading_solve", user_test.id)


@login_required
def solve_test(request, user_test_id):
    user_test = get_object_or_404(UserReadingTest, id=user_test_id)
    test = user_test.test

    passages = test.passages.prefetch_related(
        "paragraphs",
        "groups__questions__options",
        "groups__group_options"
    )

    return render(request, "ielts/reading/solve_test.html", {
        "user_test": user_test,
        "test": test,
        "passages": passages
    })


@login_required
def save_answer(request):
    if request.method == "POST":
        question_id = request.POST.get("question_id")
        answer = request.POST.get("answer")
        user_test_id = request.POST.get("user_test_id")

        question = Question.objects.get(id=question_id)

        is_correct = False
        if question.correct_answer:
            is_correct = check_answer(question.correct_answer, answer)

        UserAnswer.objects.update_or_create(
            user_test_id=user_test_id,
            question=question,
            defaults={
                "user": request.user,
                "test": question.group.passage.test,
                "answer": answer,
                "is_correct": is_correct
            }
        )

        return JsonResponse({"status": "saved"})


@login_required
def submit_test(request, user_test_id):
    user_test = get_object_or_404(UserReadingTest, id=user_test_id)

    answers = user_test.answers.all()
    score = answers.filter(is_correct=True).count()

    total = answers.count()
    correct = score

    mistakes = []

    for ans in answers:
        if not ans.is_correct:
            mistakes.append(ans.question.group.group_type)

    mistake_stats = Counter(mistakes)

    user_test.mistake_stats = json.dumps(mistake_stats)
    user_test.accuracy = round((correct / total) * 100, 1) if total else 0

    data = {}
    for ans in answers:
        data[str(ans.question.number)] = ans.answer

    user_test.score = score
    user_test.answers_json = data
    user_test.completed_at = timezone.now()
    user_test.save()

    return redirect("ielts:reading_result", user_test.id)


@login_required
def result_view(request, user_test_id):
    user_test = get_object_or_404(UserReadingTest, id=user_test_id)

    answers = user_test.answers.select_related("question")
    answer_map = {a.question.number: a for a in answers}

    questions = Question.objects.filter(
        group__passage__test=user_test.test
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

    return render(request, "ielts/reading/result.html", {
        "result": result,
        "left_rows": left_rows,
        "right_rows": right_rows
    })


@login_required
def reading_overall_ai(request):
    allowed, msg = can_use_ai(request.user)
    if not allowed:
        return HttpResponse(msg)

    increment_ai(request.user)

    tests = UserReadingTest.objects.filter(
        user=request.user,
        completed_at__isnull=False
    )

    profile = build_user_reading_profile(tests)

    if not profile:
        return render(request, "ielts/reading/overall_ai.html", {
            "profile": {},
            "ai": {}
        })

    force = request.GET.get("refresh") == "1"

    report, _ = ReadingAIReport.objects.get_or_create(user=request.user)

    need_update = (
        force or
        not report.ai_response or
        report.updated_at < timezone.now() - timedelta(hours=12)
    )

    if need_update:
        try:
            ai = analyze_overall(profile)

            report.total_tests = profile.get("total_tests", 0)
            report.avg_score = profile.get("avg_score", 0)
            report.avg_accuracy = profile.get("avg_accuracy", 0)
            report.weak_types = profile.get("weak_types", {})

            report.ai_response = ai
            report.updated_at = timezone.now()
            report.save()

        except Exception as e:
            print("AI ERROR:", e)

    return render(request, "ielts/reading/overall_ai.html", {
        "profile": report,
        "ai": report.ai_response
    })