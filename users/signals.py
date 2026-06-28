from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.core.cache import cache

User = get_user_model()


@receiver(post_save, sender=User)
def clear_user_cache(sender, instance, **kwargs):
    """Clear user cache after admin updates to ensure fresh data on next request."""
    cache.delete(f"user_{instance.pk}")
    cache.delete(f"auth_user_{instance.pk}")
