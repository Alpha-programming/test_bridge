from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Avg

from ..models import (
    UserReadingTest,
    UserListeningTest,
    WritingResult,
    SpeakingAttempt,
    Subscription
)

from ..forms import ProfileForm


# =========================
# HELPERS
# =========================

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


def round_band(score):
    return round(score * 2) / 2


# =========================
# VIEWS
# =========================

@login_required
def profile_view(request):

    user = request.user

    # 📘 READING
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
def results_view(request):
    user = request.user

    # 📘 Reading
    reading_results = UserReadingTest.objects.filter(
        user=user,
        completed_at__isnull=False
    ).order_by("-completed_at")

    # 🎧 Listening
    listening_results = UserListeningTest.objects.filter(
        user=user,
        completed_at__isnull=False
    ).order_by("-completed_at")

    # ✍️ Writing
    writing_results = WritingResult.objects.filter(
        user=user,
        final_band__isnull=False
    ).order_by("-submitted_at")

    # 🎤 Speaking
    speaking_results = SpeakingAttempt.objects.filter(
        user=user
    ).order_by("-created_at")

    return render(request, "ielts/profile/results.html", {
        "reading_results": reading_results,
        "listening_results": listening_results,
        "writing_results": writing_results,
        "speaking_results": speaking_results,
    })