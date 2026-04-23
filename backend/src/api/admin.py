from django.contrib import admin

from .models import AudioJob, Document, ExtractionJob


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "user", "status", "created_at")
    search_fields = ("title", "user__username", "user__email")
    list_filter = ("status", "created_at")


@admin.register(ExtractionJob)
class ExtractionJobAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "user", "status", "provider", "created_at")
    search_fields = ("document__title", "user__username", "source_name", "provider")
    list_filter = ("status", "provider", "created_at")


@admin.register(AudioJob)
class AudioJobAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "user", "status", "voice", "created_at")
    search_fields = ("document__title", "user__username", "voice", "provider")
    list_filter = ("status", "provider", "created_at")
