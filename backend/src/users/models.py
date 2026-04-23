from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    provider = models.CharField(max_length=50, blank=True)
    provider_id = models.CharField(max_length=255, blank=True)
    display_name = models.CharField(max_length=150, blank=True)
    preferred_voice = models.CharField(max_length=80, blank=True)
    preferred_language = models.CharField(max_length=32, blank=True)
    timezone = models.CharField(max_length=64, blank=True)
    notify_by_email = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Profile<{self.user_id}>"

