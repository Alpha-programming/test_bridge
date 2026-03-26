def get_model_for_user(user):
    plan = user.subscription.plan

    if plan == "FREE":
        return None  # no AI or limited AI
    elif plan == "BASIC":
        return "gpt-5-nano"
    elif plan == "PRO":
        return "gpt-5-mini"
    elif plan == "PREMIUM":
        return "gpt-5"