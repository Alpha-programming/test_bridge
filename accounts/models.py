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

    ai_used_today = models.IntegerField(default=0)
    tests_used_today = models.IntegerField(default=0)

    last_reset = models.DateField(auto_now_add=True)
    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True)

    def is_expired(self):
        if self.plan == "FREE":
            return False
        return self.end_date and timezone.now() > self.end_date

    def reset_daily_usage(self):
        today = timezone.now().date()

        if self.last_reset != today:
            self.ai_used_today = 0
            self.tests_used_today = 0
            self.last_reset = today
            self.save()

    def get_limits(self):
        return {
            "FREE": {"ai": 1, "tests": 2},
            "STANDARD": {"ai": 5, "tests": 10},
            "PRO": {"ai": 100, "tests": 100},
        }.get(self.plan, {"ai": 0, "tests": 0})

    def __str__(self):
        return f"{self.user.username} - {self.plan}"