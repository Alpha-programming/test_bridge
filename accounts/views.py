from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Subscription
from .subscription import prepare_subscription

class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)


def login_view(request):
    form = LoginForm()

    next_url = request.GET.get("next")

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"]
            )
            if user:
                login(request, user)

                # 🔥 KEY LOGIC
                if next_url:
                    return redirect(next_url)
                return redirect("home")  # fallback

    return render(request, "accounts/login.html", {"form": form})

def register_view(request):
    form = UserCreationForm()

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("ielts:home")

    return render(request, "accounts/register.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("home")


@login_required
def profile_view(request):
    subscription = prepare_subscription(request.user)

    limits = subscription.get_limits()
    test_limit = limits["tests"]
    ai_limit = limits["ai"]

    # ✅ monthly remaining
    remaining_tests = max(0, test_limit - subscription.tests_used)
    remaining_ai = max(0, ai_limit - subscription.ai_used)

    tests_progress_percent = 0
    ai_progress_percent = 0

    if test_limit > 0:
        tests_progress_percent = min(100, round((subscription.tests_used / test_limit) * 100))

    if ai_limit > 0:
        ai_progress_percent = min(100, round((subscription.ai_used / ai_limit) * 100))

    context = {
        "subscription": subscription,
        "test_limit": test_limit,
        "ai_limit": ai_limit,
        "remaining_tests": remaining_tests,
        "remaining_ai": remaining_ai,
        "tests_progress_percent": tests_progress_percent,
        "ai_progress_percent": ai_progress_percent,
    }

    return render(request, "accounts/profile.html", context)

@login_required
@require_POST
def update_plan_view(request):
    plan = request.POST.get("plan")

    if plan not in ["FREE", "STANDARD", "PRO"]:
        return redirect("accounts:profile")

    subscription, _ = Subscription.objects.get_or_create(
        user=request.user,
        defaults={"plan": "FREE"}
    )

    if plan == "FREE":
        subscription.plan = "FREE"
        subscription.is_active = True
        subscription.start_date = timezone.now()
        subscription.end_date = None
    else:
        subscription.plan = plan
        subscription.is_active = True
        subscription.start_date = timezone.now()
        subscription.end_date = timezone.now() + timedelta(days=30)

    subscription.ai_used_today = 0
    subscription.tests_used_today = 0
    subscription.last_reset = timezone.now().date()
    subscription.save()

    return redirect("accounts:profile")