from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import ReadingTest,UserReadingTest
from django.db.models import Q


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