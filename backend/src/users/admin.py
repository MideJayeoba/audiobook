from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "display_name", "provider", "preferred_voice", "created_at")
    search_fields = ("user__username", "user__email", "provider", "display_name", "preferred_voice")
    list_filter = ("provider", "preferred_language", "notify_by_email", "created_at")
