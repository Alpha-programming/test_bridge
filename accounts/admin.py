from django.contrib import admin
from .models import Subscription

# Register your models here.

# =========================================================
# 💳 SUBSCRIPTION ADMIN
# =========================================================

class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "is_active",
        "ai_used_today",
        "tests_used_today",
        "start_date",
        "end_date",
    )

admin.site.register(Subscription, SubscriptionAdmin)