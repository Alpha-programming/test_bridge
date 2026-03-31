from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import (ReadingTest,UserReadingTest,Question,UserAnswer,
                     ListeningTest,UserListeningTest,UserListeningAnswer,ListeningQuestion,
                     WritingTest,UserWritingTest,WritingResult,HomePageContent,
                     SpeakingTest,SpeakingAttempt,SpeakingQuestion,UserSpeakingTest,
                     ReadingAIReport,ListeningAIReport,Subscription)
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
import json
from .services.ai_selector import get_model_for_user
from .services.ai_writing import evaluate_with_retry
from django.core.paginator import Paginator
import re
from .services.pipeline import process_speaking
from .services.evaluation import evaluate_full_speaking
from .services.speech import transcribe_audio
from .services.reading_analytics import build_user_reading_profile
from .services.ai_reading_overall import analyze_overall
from datetime import timedelta
from .services.listening_analytics import build_user_listening_profile
from .services.ai_listening_overall import analyze_listening
from django.db.models import Avg
from .forms import ProfileForm
from .services.subscription import (
    can_use_ai,
    can_start_test,
    increment_ai,
    increment_test,
    prepare_subscription,
    activate_plan
)
from django.http import HttpResponse

LISTENING_REVIEW_SECONDS = 120

def round_band(score):
    return round(score * 2) / 2

@login_required
def home(request):
    content = HomePageContent.objects.filter(is_active=True).first()

    return render(request, "ielts/main.html", {
        "content": content
    })

def normalize(text):
    return text.strip().lower()

def check_answer(correct, user):
    correct = normalize(correct)
    user = normalize(user)

    # 🔹 1. MULTIPLE ANSWERS (A/C or A,B)
    if "/" in correct or "," in correct:
        parts = re.split(r"[\/,]", correct)
        parts = [p.strip() for p in parts]
        return user in parts

    # 🔹 2. OPTIONAL WORDS (remove brackets)
    # "first aid (training)" → "first aid"
    optional_removed = re.sub(r"\(.*?\)", "", correct).strip()

    if user == correct:
        return True

    if user == optional_removed:
        return True

    # 🔹 3. FLEXIBLE MATCH (ignore small variations)
    # remove punctuation
    clean_correct = re.sub(r"[^\w\s]", "", correct)
    clean_user = re.sub(r"[^\w\s]", "", user)

    if clean_user == clean_correct:
        return True

    # 🔹 4. CONTAINS MATCH (advanced)
    if clean_user in clean_correct or clean_correct in clean_user:
        return True

    return False

def calculate_task_band(scores):
    values = [
        scores.get("task", 0),
        scores.get("coherence", 0),
        scores.get("lexical", 0),
        scores.get("grammar", 0),
    ]

    avg = sum(values) / 4

    # 🔥 FRIENDLIER ROUNDING (not too strict)
    return round(avg * 2) / 2

def calculate_final_band(t1, t2):
    if not t1 or not t2:
        return None

    final = (t1 + (t2 * 2)) / 3

    # friendly rounding
    return round(final * 2) / 2

from collections import Counter

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

    # bands
    for ut in user_tests:
        ut.band = calculate_band(ut.score)

    # 📊 PROGRESS
    progress_data = list(
        UserReadingTest.objects.filter(
            user=request.user,
            completed_at__isnull=False
        ).order_by("completed_at").values_list("score", flat=True)
    )

    progress_data = [calculate_band(s) for s in progress_data]

    # 🔥 ANALYTICS (NO AI)
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
        ai_preview = None

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

        # 🔥 analytics
        "total_tests": total_tests,
        "avg_score": avg_score,
        "avg_accuracy": avg_accuracy,
        "weak_types": dict(mistake_counter.most_common(3)),
        "ai_preview": ai_preview,
        "subscription": sub,
    })

@login_required
def start_test(request, test_id):

    # 🔒 LIMIT CHECK
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

    from collections import Counter
    import json

    total = answers.count()
    correct = score

    mistakes = []

    for ans in answers:
        if not ans.is_correct:
            mistakes.append(ans.question.group.group_type)

    mistake_stats = Counter(mistakes)

    # save data
    user_test.mistake_stats = json.dumps(mistake_stats)
    user_test.accuracy = round((correct / total) * 100, 1) if total else 0

    # JSON snapshot
    data = {}
    for ans in answers:
        data[str(ans.question.number)] = ans.answer

    user_test.score = score
    user_test.answers_json = data
    user_test.completed_at = timezone.now()
    user_test.save()

    return redirect("ielts:reading_result", user_test.id)

def calculate_band(score):
    # simple IELTS conversion (you can improve later)
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

    # split into 2 columns
    left_rows = [r for r in rows if r["n"] <= 20]
    right_rows = [r for r in rows if r["n"] > 20]

    # build result object
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
    # 🔒 AI LIMIT
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

    # 🔥 CHECK FORCE REFRESH (from button)
    force = request.GET.get("refresh") == "1"

    # 🔥 GET OR CREATE REPORT
    report, _ = ReadingAIReport.objects.get_or_create(user=request.user)

    # 🔥 SMART CACHE LOGIC
    need_update = (
        force or  # 🔥 user clicked button
        not report.ai_response or
        report.updated_at < timezone.now() - timedelta(hours=12)
    )

    if need_update:
        try:
            ai = analyze_overall(profile)

            # ✅ UPDATE REPORT
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

@login_required
def listening_home(request):
    query = request.GET.get("q")

    tests = ListeningTest.objects.all()

    if query:
        tests = tests.filter(title__icontains=query)

    tests = tests.order_by("-created_at")

    # pagination
    paginator = Paginator(tests, 6)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # last 10 results
    user_tests = UserListeningTest.objects.filter(
        user=request.user,
        completed_at__isnull=False
    ).order_by("-completed_at")[:10]

    # band
    for ut in user_tests:
        ut.band = calculate_band(ut.score)

    # progress chart
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
    # 🔒 AI LIMIT
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

    # 🔒 LIMIT CHECK
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

    # ✅ FIX: unique options per group
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

    # 🔥 SAVE ANALYTICS
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


@login_required
def writing_home(request):
    query = request.GET.get("q")

    tests = WritingTest.objects.all()

    if query:
        tests = tests.filter(title__icontains=query)

    tests = tests.order_by("-created_at")

    # ✅ PAGINATION
    paginator = Paginator(tests, 6)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # ✅ LAST RESULTS
    results = WritingResult.objects.filter(
        user=request.user
    ).exclude(final_band__isnull=True).order_by("-submitted_at")[:10]

    # progress
    progress_data = list(
        WritingResult.objects.filter(
            user=request.user
        )
        .exclude(final_band__isnull=True)
        .order_by("submitted_at")
        .values_list("final_band", flat=True)
    )

    # 🔥 FIX HERE
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

    # 🔥 ALWAYS reset start time
    user_test.started_at = timezone.now()

    # reset answers if needed
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

    # 🔐 CHECK SUBSCRIPTION
    allowed, message = can_use_ai(request.user)

    if not allowed:
        return JsonResponse({"error": message}, status=403)

    # AFTER SUCCESS
    increment_ai(request.user)

    # 🎯 SELECT MODEL BASED ON PLAN
    config = get_model_for_user(request.user)

    if not config:
        return JsonResponse({"error": "Upgrade your plan to use AI"}, status=403)

    result, _ = WritingResult.objects.get_or_create(
        user=request.user,
        test=user_test.test,
        user_test=user_test
    )

    # 🧠 CALL AI (with retry + safe JSON)
    data, usage = evaluate_with_retry(
        user_test.task1_answer,
        user_test.task2_answer,
        config
    )

    # ❌ AI failed
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

    # 🔥 calculate bands yourself
    result.task1_band = calculate_task_band(task1)
    result.task2_band = calculate_task_band(task2)

    result.final_band = calculate_final_band(
        result.task1_band,
        result.task2_band
    )
    result.feedback = json.dumps(data.get("feedback", {}))

    # ADVANCED
    result.advanced = json.dumps(data.get("advanced", {}))
    result.status = "checked"

    result.save()


    # ⏱ mark completed
    user_test.completed_at = timezone.now()
    user_test.save()

    return redirect("ielts:writing_result", result.id)

import json
import ast

@login_required
def writing_result(request, result_id):
    result = get_object_or_404(WritingResult, id=result_id)

    feedback = result.feedback


    # 🔥 FIX: handle python dict string
    if isinstance(feedback, str):
        try:
            feedback = json.loads(feedback)  # try JSON
        except:
            try:
                feedback = ast.literal_eval(feedback)  # 🔥 THIS FIXES IT
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

    # 2. ONE GPT CALL
    result = evaluate_full_speaking(full_text)

    # 3. SAVE SAME RESULT TO ALL
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

        # 🔥 friendly IELTS rounding
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
        return round(sum(lst)/len(lst), 1) if lst else 0

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

@login_required
def profile_view(request):

    user = request.user

    # 📊 READING
    reading_tests = UserReadingTest.objects.filter(
        user=user,
        completed_at__isnull=False
    )
    reading_scores = [t.score for t in reading_tests if t.score is not None]

    reading_avg_score = round(sum(reading_scores) / len(reading_scores), 1) if reading_scores else 0

    reading_bands = [calculate_band(s) for s in reading_scores]
    reading_avg_band = round_band(sum(reading_bands) / len(reading_bands)) if reading_bands else 0

    # 🎧 LISTENING
    listening_tests = UserListeningTest.objects.filter(
        user=user,
        completed_at__isnull=False
    )
    listening_scores = [t.score for t in listening_tests if t.score is not None]

    listening_avg_score = round(sum(listening_scores) / len(listening_scores), 1) if listening_scores else 0

    listening_bands = [calculate_band(s) for s in listening_scores]
    listening_avg_band = round_band(sum(listening_bands) / len(listening_bands)) if listening_bands else 0

    # ✍️ WRITING
    writing = WritingResult.objects.filter(
        user=user,
        final_band__isnull=False
    )
    writing_avg = writing.aggregate(avg=Avg("final_band"))["avg"] or 0

    # 🎤 SPEAKING
    speaking = SpeakingAttempt.objects.filter(user=user)
    speaking_avg = speaking.aggregate(avg=Avg("overall_band"))["avg"] or 0

    # 💳 SUBSCRIPTION
    sub = Subscription.objects.filter(user=user).first()

    return render(request, "ielts/profile/profile.html", {
        "reading_avg_score": reading_avg_score,
        "reading_avg_band": reading_avg_band,

        "listening_avg_score": listening_avg_score,
        "listening_avg_band": listening_avg_band,
        "writing_avg": round(writing_avg, 1),
        "speaking_avg": round(speaking_avg, 1),
        "subscription": sub
    })

@login_required
def edit_profile(request):

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)

        if form.is_valid():
            form.save()
            return redirect("ielts:profile")

    else:
        form = ProfileForm(instance=request.user)

    return render(request, "ielts/profile/edit_profile.html", {
        "form": form
    })

@login_required
def pricing_view(request):
    sub = prepare_subscription(request.user)

    return render(request, "ielts/payment/pricing.html", {
        "subscription": sub
    })

@login_required
def upgrade_plan(request, plan):

    if plan not in ["STANDARD", "PRO"]:
        return redirect("ielts:pricing")

    activate_plan(request.user, plan)

    return redirect("ielts:profile")