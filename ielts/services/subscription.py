from datetime import timedelta
from django.utils import timezone
from ..models import Subscription


# 🔹 GET OR CREATE
def get_subscription(user):
    sub, _ = Subscription.objects.get_or_create(user=user)
    return sub


# 🔹 CHECK + RESET
def prepare_subscription(user):
    sub = get_subscription(user)

    # reset daily usage
    sub.reset_daily_usage()

    # check expiration
    if sub.is_expired():
        sub.plan = "FREE"
        sub.is_active = False
        sub.save()

    return sub


# 🔹 CHECK AI
def can_use_ai(user):
    sub = prepare_subscription(user)

    limits = sub.get_limits()

    if sub.ai_used_today >= limits["ai"]:
        return False, "AI daily limit reached"

    return True, ""


# 🔹 CHECK TEST
def can_start_test(user):
    sub = prepare_subscription(user)

    limits = sub.get_limits()

    if sub.tests_used_today >= limits["tests"]:
        return False, "Daily test limit reached"

    return True, ""


# 🔹 INCREMENT
def increment_ai(user):
    sub = get_subscription(user)
    sub.ai_used_today += 1
    sub.save()


def increment_test(user):
    sub = get_subscription(user)
    sub.tests_used_today += 1
    sub.save()


# 🔹 ACTIVATE PLAN (FAKE PAYMENT FOR NOW)
def activate_plan(user, plan):
    sub = get_subscription(user)

    sub.plan = plan
    sub.start_date = timezone.now()
    sub.end_date = timezone.now() + timedelta(days=30)
    sub.is_active = True

    sub.save()