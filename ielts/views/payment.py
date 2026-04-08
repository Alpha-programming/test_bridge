from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.conf import settings
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
import stripe

from ..models import Subscription
from ..services.subscription import prepare_subscription, activate_plan


# 🔑 Stripe config
stripe.api_key = settings.STRIPE_SECRET_KEY


# =========================
# VIEWS
# =========================

@login_required
def pricing_view(request):
    sub = prepare_subscription(request.user)

    return render(request, "ielts/payment/pricing.html", {
        "subscription": sub
    })


@login_required
def upgrade_plan(request, plan):
    if plan not in ["STANDARD", "PRO"]:
        return redirect("ielts:pricing")

    activate_plan(request.user, plan)

    return redirect("ielts:profile")


@login_required
def downgrade_plan(request):
    sub = Subscription.objects.filter(user=request.user).first()

    if sub and sub.stripe_subscription_id:
        try:
            stripe.Subscription.delete(sub.stripe_subscription_id)
        except Exception as e:
            print("Stripe cancel error:", e)

    if sub:
        sub.plan = "FREE"
        sub.is_active = False
        sub.end_date = None
        sub.stripe_subscription_id = None
        sub.save()

    return redirect("ielts:profile")


@login_required
def create_checkout_session(request, plan):

    price_map = {
        "STANDARD": settings.STRIPE_PRICES["STANDARD"],
        "PRO": settings.STRIPE_PRICES["PRO"],
    }

    if plan not in price_map:
        return redirect("ielts:pricing")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        payment_method_collection="always",
        mode="subscription",

        line_items=[{
            "price": price_map[plan],
            "quantity": 1,
        }],

        customer_email=request.user.email or "test@example.com",

        success_url="http://127.0.0.1:8000/ielts/payment-success/?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="http://127.0.0.1:8000/ielts/pricing/",

        metadata={
            "user_id": request.user.id,
            "plan": plan
        }
    )

    return redirect(session.url)


@login_required
def payment_success(request):
    session_id = request.GET.get("session_id")

    if not session_id:
        return redirect("ielts:pricing")

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        print("Stripe error:", e)
        return redirect("ielts:pricing")

    # ❌ NOT PAID
    if session.payment_status != "paid":
        return redirect("ielts:pricing")

    user_id = session["metadata"]["user_id"]
    plan = session["metadata"]["plan"]

    user = User.objects.get(id=user_id)

    sub = Subscription.objects.filter(user=user).first()

    # 🔥 avoid duplicate activation
    if not sub or sub.plan != plan:
        activate_plan(user, plan)

    return render(request, "ielts/payment/success.html")


@csrf_exempt
def stripe_webhook(request):

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception:
        return HttpResponse(status=400)

    # ✅ PAYMENT SUCCESS
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        user_id = session["metadata"]["user_id"]
        plan = session["metadata"]["plan"]
        stripe_sub_id = session.get("subscription")

        user = User.objects.get(id=user_id)

        # ❗ (kept same as your original - commented logic)
        # sub = activate_plan(user, plan)
        # sub.stripe_subscription_id = stripe_sub_id
        # sub.save()

    # 🔥 AUTO DOWNGRADE
    if event["type"] == "customer.subscription.deleted":
        stripe_sub_id = event["data"]["object"]["id"]

        sub = Subscription.objects.filter(
            stripe_subscription_id=stripe_sub_id
        ).first()

        if sub:
            sub.plan = "FREE"
            sub.is_active = False
            sub.end_date = None
            sub.stripe_subscription_id = None
            sub.save()

    return HttpResponse(status=200)