from django.db import transaction
from accounts.models import Subscription


def get_or_create_subscription(user):
    subscription, _ = Subscription.objects.get_or_create(
        user=user,
        defaults={"plan": "FREE"}
    )
    subscription.reset_daily_usage()
    return subscription


def get_remaining_tests(user):
    sub = get_or_create_subscription(user)
    limits = sub.get_limits()
    return max(0, limits["tests"] - sub.tests_used_today)


def get_remaining_ai(user):
    sub = get_or_create_subscription(user)
    limits = sub.get_limits()
    return max(0, limits["ai"] - sub.ai_used_today)


@transaction.atomic
def charge_test_usage(user, amount=1):
    sub = Subscription.objects.select_for_update().get(user=user)
    sub.reset_daily_usage()
    limits = sub.get_limits()

    if sub.tests_used_today + amount > limits["tests"]:
        return False, sub

    sub.tests_used_today += amount
    sub.save(update_fields=["tests_used_today"])
    return True, sub


@transaction.atomic
def refund_test_usage(user, amount=1):
    sub = Subscription.objects.select_for_update().get(user=user)
    sub.reset_daily_usage()
    sub.tests_used_today = max(0, sub.tests_used_today - amount)
    sub.save(update_fields=["tests_used_today"])
    return sub


@transaction.atomic
def charge_ai_usage(user, amount=1):
    sub = Subscription.objects.select_for_update().get(user=user)
    sub.reset_daily_usage()
    limits = sub.get_limits()

    if sub.ai_used_today + amount > limits["ai"]:
        return False, sub

    sub.ai_used_today += amount
    sub.save(update_fields=["ai_used_today"])
    return True, sub


@transaction.atomic
def refund_ai_usage(user, amount=1):
    sub = Subscription.objects.select_for_update().get(user=user)
    sub.reset_daily_usage()
    sub.ai_used_today = max(0, sub.ai_used_today - amount)
    sub.save(update_fields=["ai_used_today"])
    return sub