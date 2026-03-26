from django.utils import timezone

# 🔥 PLAN LIMITS (requests per month)
PLAN_LIMITS = {
    "FREE": 2,
    "BASIC": 20,
    "PRO": 100,
    "PREMIUM": 999999,
}


def can_use_ai(user):
    sub = user.subscription

    # 🔴 check expiration
    if sub.is_expired():
        sub.plan = "FREE"
        sub.is_active = False
        sub.save()
        return False, "Your subscription has expired."

    # 🔄 reset monthly usage
    sub.reset_usage_if_needed()

    # 🚫 limit reached
    if sub.requests_used >= PLAN_LIMITS[sub.plan]:
        return False, "You reached your limit. Upgrade your plan."

    return True, None


def increment_usage(user, tokens=0):
    sub = user.subscription
    sub.requests_used += 1
    sub.tokens_used += tokens
    sub.save()