from datetime import timedelta
from django.utils import timezone
from .models import Subscription


# =========================
# 🔹 GET OR CREATE
# =========================
def get_subscription(user):
    sub, _ = Subscription.objects.get_or_create(user=user)
    return sub


# =========================
# 🔹 PREPARE (RESET + EXPIRE)
# =========================
def prepare_subscription(user):
    sub = get_subscription(user)

    # 🔥 Monthly reset
    sub.reset_monthly_usage()

    # 🔥 Auto downgrade if expired
    if sub.is_expired():
        sub.plan = "FREE"
        sub.is_active = True
        sub.end_date = None
        sub.stripe_subscription_id = None
        sub.save()

    return sub


# =========================
# 🔹 CHECK AI LIMIT
# =========================
def can_use_ai(user):
    sub = prepare_subscription(user)

    limits = sub.get_limits()

    if sub.ai_used >= limits["ai"]:
        return False, "AI monthly limit reached"

    return True, ""


# =========================
# 🔹 CHECK TEST LIMIT
# =========================
def can_start_test(user):
    sub = prepare_subscription(user)

    limits = sub.get_limits()

    if sub.tests_used >= limits["tests"]:
        return False, "Test limit reached"

    return True, ""


# =========================
# 🔹 INCREMENT USAGE
# =========================
def increment_ai(user):
    sub = get_subscription(user)
    sub.ai_used += 1
    sub.save()


def increment_test(user):
    sub = get_subscription(user)
    sub.tests_used += 1
    sub.save()


# =========================
# 🔹 ACTIVATE PLAN
# =========================
def activate_plan(user, plan):
    sub, _ = Subscription.objects.get_or_create(user=user)

    sub.plan = plan
    sub.start_date = timezone.now()

    if plan == "STANDARD":
        sub.end_date = timezone.now() + timedelta(days=30)

    elif plan == "PRO":
        sub.end_date = timezone.now() + timedelta(days=90)

    else:  # FREE
        sub.end_date = None

    sub.is_active = True

    # 🔥 reset usage
    sub.ai_used = 0
    sub.tests_used = 0
    sub.last_reset = timezone.now()

    sub.save()

    return sub