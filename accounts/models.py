from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Create your models here.

class Subscription(models.Model):
    PLAN_CHOICES = [
        ("FREE", "Free"),
        ("STANDARD", "Standard"),
        ("PRO", "Pro"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="FREE")

    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    ai_used = models.IntegerField(default=0)
    tests_used = models.IntegerField(default=0)
    last_reset = models.DateTimeField(auto_now_add=True)
    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True)

    def is_expired(self):
        if self.plan == "FREE":
            return False
        return self.end_date and timezone.now() > self.end_date

    def reset_monthly_usage(self):
        from datetime import timedelta

        if timezone.now() - self.last_reset >= timedelta(days=30):
            self.ai_used = 0
            self.tests_used = 0
            self.last_reset = timezone.now()
            self.save()

    def get_limits(self):
        return {
            "FREE": {"ai": 0, "tests": 50},
            "STANDARD": {"ai": 15, "tests": 50},
            "PRO": {"ai": 100, "tests": 9999},
        }.get(self.plan, {"ai": 0, "tests": 0})

    def activate_plan(self, plan):
        self.plan = plan
        self.start_date = timezone.now()

        if plan == "STANDARD":
            self.end_date = self.start_date + timedelta(days=30)

        elif plan == "PRO":
            self.end_date = self.start_date + timedelta(days=90)

        else:  # FREE
            self.end_date = None

        self.ai_used = 0
        self.tests_used = 0
        self.last_reset = timezone.now()
        self.is_active = True
        self.save()

    def can_use_ai(self):
        self.reset_monthly_usage()
        limits = self.get_limits()
        return self.ai_used < limits["ai"]

    def can_take_test(self):
        self.reset_monthly_usage()
        limits = self.get_limits()
        return self.tests_used < limits["tests"]

    def __str__(self):
        return f"{self.user.username} - {self.plan}"