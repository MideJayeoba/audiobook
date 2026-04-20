from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "user", "status", "created_at")
    search_fields = ("title", "user__username", "user__email")
    list_filter = ("status", "created_at")
