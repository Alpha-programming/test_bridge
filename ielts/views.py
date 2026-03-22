from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import ReadingTest,UserReadingTest,Question,UserAnswer
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone




@login_required
def home(request):
    return render(request, "ielts/ielts.html")

@login_required
def reading_home(request):
    query = request.GET.get("q")

    tests = ReadingTest.objects.all()

    if query:
        tests = tests.filter(
            Q(title__icontains=query)
        )

    tests = tests.order_by("-created_at")

    user_tests = UserReadingTest.objects.filter(
        user=request.user,
        completed_at__isnull=False
    ).order_by("-completed_at")[:5]

    return render(request, "ielts/reading/reading_home.html", {
        "tests": tests,
        "user_tests": user_tests,
        "query": query
    })

@login_required
def start_test(request, test_id):
    test = get_object_or_404(ReadingTest, id=test_id)

    user_test = UserReadingTest.objects.create(
        user=request.user,
        test=test
    )

    return redirect("ielts:solve_test", user_test.id)

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

def save_answer(request):
    if request.method == "POST":
        question_id = request.POST.get("question_id")
        answer = request.POST.get("answer")
        user_test_id = request.POST.get("user_test_id")

        question = Question.objects.get(id=question_id)

        is_correct = False
        if question.correct_answer:
            is_correct = question.correct_answer.strip().lower() == answer.strip().lower()

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

    return redirect("ielts:result", user_test.id)

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