from django.conf import settings
from django.db import models


class Document(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        EXTRACTING = "extracting", "Extracting"
        EXTRACTED = "extracted", "Extracted"
        TTS_PROCESSING = "tts_processing", "TTS Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=255)
    source_file = models.FileField(upload_to="documents/", blank=True, null=True)
    source_name = models.CharField(max_length=255, blank=True)
    source_mime_type = models.CharField(max_length=120, blank=True)
    source_size_bytes = models.BigIntegerField(default=0)
    storage_mode = models.CharField(max_length=24, default="local_device")
    extracted_text = models.TextField(blank=True)
    chapter_map = models.JSONField(default=list, blank=True)
    ai_summary = models.TextField(blank=True)
    current_position_seconds = models.FloatField(default=0.0)
    audio_url = models.URLField(blank=True)
    audio_local_ref = models.CharField(max_length=255, blank=True)
    audio_duration_seconds = models.FloatField(default=0.0)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.UPLOADED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.title} ({self.status})"


class ExtractionJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="extraction_jobs")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="extraction_jobs")
    source_name = models.CharField(max_length=255, blank=True)
    source_mime_type = models.CharField(max_length=120, blank=True)
    source_size_bytes = models.BigIntegerField(default=0)
    storage_mode = models.CharField(max_length=24, default="local_device")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.QUEUED)
    provider = models.CharField(max_length=64, blank=True)
    text_preview = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["document", "status"]),
        ]

    def __str__(self) -> str:
        return f"ExtractionJob<{self.document_id}:{self.status}>"


class AudioJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="audio_jobs")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="audio_jobs")
    voice = models.CharField(max_length=80, blank=True)
    provider = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.QUEUED)
    audio_url = models.URLField(blank=True)
    audio_local_ref = models.CharField(max_length=255, blank=True)
    audio_duration_seconds = models.FloatField(default=0.0)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["document", "status"]),
        ]

    def __str__(self) -> str:
        return f"AudioJob<{self.document_id}:{self.status}>"


class ChapterNavigationEvent(models.Model):
    class EventType(models.TextChoices):
        SEEK = "seek", "Seek"
        SEMANTIC_SEEK = "semantic_seek", "Semantic Seek"
        PLAYBACK_SEEK = "playback_seek", "Playback Seek"
        DETECT_CHAPTERS = "detect_chapters", "Detect Chapters"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chapter_navigation_events")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="navigation_events")
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    query = models.CharField(max_length=255, blank=True)
    chapter_index = models.IntegerField(null=True, blank=True)
    chapter_title = models.CharField(max_length=255, blank=True)
    position_seconds = models.FloatField(default=0.0)
    confidence = models.FloatField(default=0.0)
    provider = models.CharField(max_length=64, blank=True)
    fallback_used = models.BooleanField(default=False)
    match_excerpt = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["document", "created_at"]),
            models.Index(fields=["event_type", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"NavigationEvent<{self.document_id}:{self.event_type}>"
