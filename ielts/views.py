from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import (ReadingTest,UserReadingTest,Question,UserAnswer,
                     ListeningTest,UserListeningTest,UserListeningAnswer,ListeningQuestion,
                     WritingTest,UserWritingTest,WritingResult,HomePageContent,
                     SpeakingTest,SpeakingAttempt,SpeakingQuestion,UserSpeakingTest)
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
import json
from .services.subscription import can_use_ai, increment_usage
from .services.ai_selector import get_model_for_user
from .services.ai_writing import evaluate_with_retry
from django.core.paginator import Paginator
import re

LISTENING_REVIEW_SECONDS = 120

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

@login_required
def reading_home(request):
    query = request.GET.get("q")

    tests = ReadingTest.objects.all()

    if query:
        tests = tests.filter(title__icontains=query)

    tests = tests.order_by("-created_at")

    # ✅ PAGINATION (6 per page)
    paginator = Paginator(tests, 6)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # ✅ LAST 10 RESULTS
    user_tests = UserReadingTest.objects.filter(
        user=request.user,
        completed_at__isnull=False
    ).order_by("-completed_at")[:10]

    # add band
    for ut in user_tests:
        ut.band = calculate_band(ut.score)

    progress_data = list(
        UserReadingTest.objects.filter(
            user=request.user,
            completed_at__isnull=False
        ).order_by("completed_at").values_list("score", flat=True)
    )

    progress_data = [calculate_band(s) for s in progress_data]

    return render(request, "ielts/reading/reading_home.html", {
        "page_obj": page_obj,
        "user_tests": user_tests,
        "query": query,
        "progress_data": json.dumps(progress_data)
    })

@login_required
def start_test(request, test_id):
    test = get_object_or_404(ReadingTest, id=test_id)

    user_test, created = UserReadingTest.objects.get_or_create(
        user=request.user,
        test=test,
    )

    # 🔥 RESET if already completed
    if user_test.completed_at:
        user_test.score = 0
        user_test.answers_json = {}
        user_test.started_at = timezone.now()
        user_test.completed_at = None
        user_test.save()

        # ❗ delete old answers
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

    return render(request, "ielts/listening/listening_home.html", {
        "page_obj": page_obj,
        "user_tests": user_tests,
        "progress_data": json.dumps(progress_data),
        "query": query
    })

@login_required
def start_listening(request, test_id):
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

    user_test.score = score
    user_test.completed_at = timezone.now()
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

    return render(request, "ielts/writing/writing_home.html", {
        "page_obj": page_obj,
        "results": results,
        "query": query,
        "progress_data": json.dumps(progress_data)
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
@login_required
def submit_writing(request, user_test_id):
    user_test = get_object_or_404(UserWritingTest, id=user_test_id)

    # 🔐 CHECK SUBSCRIPTION
    allowed, message = can_use_ai(request.user)

    if not allowed:
        return JsonResponse({"error": message}, status=403)

    # 🎯 SELECT MODEL BASED ON PLAN
    model = get_model_for_user(request.user)

    if not model:
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
        model
    )

    # ❌ AI failed
    if not data:
        result.feedback = "AI evaluation failed. Please try again."
        result.status = "submitted"
        result.save()

        return redirect("ielts:writing_result", result.id)

    # ✅ SAVE TASK 1
    result.task1_task = data["task1"]["task"]
    result.task1_coherence = data["task1"]["coherence"]
    result.task1_lexical = data["task1"]["lexical"]
    result.task1_grammar = data["task1"]["grammar"]
    result.task1_band = data["task1"]["band"]

    # ✅ SAVE TASK 2
    result.task2_task = data["task2"]["task"]
    result.task2_coherence = data["task2"]["coherence"]
    result.task2_lexical = data["task2"]["lexical"]
    result.task2_grammar = data["task2"]["grammar"]
    result.task2_band = data["task2"]["band"]

    # ✅ FINAL
    result.final_band = data["final_band"]
    result.feedback = data["feedback"]
    result.status = "checked"

    result.save()

    # 🔥 TRACK USAGE (TOKENS)
    if usage:
        try:
            increment_usage(
                request.user,
                tokens=usage.total_tokens
            )
        except:
            increment_usage(request.user)

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

    # safe extract
    feedback_task1 = feedback.get("task1", "")
    feedback_task2 = feedback.get("task2", "")
    improvements = feedback.get("improvements", [])

    return render(request, "ielts/writing/result.html", {
        "result": result,
        "user_test": result.user_test,
        "feedback_task1": feedback_task1,
        "feedback_task2": feedback_task2,
        "improvements": improvements
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

    return render(request, "ielts/speaking/speaking_home.html", {
        "page_obj": page_obj,
        "results": user_tests,
        "query": query,
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

        attempt = SpeakingAttempt.objects.create(
            user=request.user,
            question=question,
            audio=audio
        )

        result = process_speaking(attempt)

        return JsonResponse(result)

@login_required
def submit_speaking(request, user_test_id):
    user_test = get_object_or_404(UserSpeakingTest, id=user_test_id)

    user_test.completed_at = timezone.now()
    user_test.save()

    return redirect("ielts:speaking_result", user_test.id)

@login_required
def speaking_result(request, user_test_id):
    user_test = get_object_or_404(UserSpeakingTest, id=user_test_id)

    attempts = SpeakingAttempt.objects.filter(
        user=request.user,
        question__test=user_test.test
    ).order_by("-created_at")

    return render(request, "ielts/speaking/result.html", {
        "attempts": attempts,
        "test": user_test.test
    })