from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import Subscription
from .models import UserProgressInsight


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_related_objects(sender, instance, created, **kwargs):
    if created:
        Subscription.objects.get_or_create(
            user=instance,
            defaults={"plan": "FREE"}
        )
        UserProgressInsight.objects.get_or_create(user=instance)