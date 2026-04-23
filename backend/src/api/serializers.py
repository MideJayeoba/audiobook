import os

from rest_framework import serializers

from .models import AudioJob, ChapterNavigationEvent, Document, ExtractionJob


MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50")) * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf"}
ALLOWED_CONTENT_TYPES = {"application/pdf"}


class DocumentSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        source_file = attrs.get("source_file")
        source_name = (attrs.get("source_name") or "").strip()

        if not source_file and not source_name:
            raise serializers.ValidationError("Provide either source_file or source_name.")

        return attrs

    def validate_source_file(self, value):
        filename = (value.name or "").lower()
        if not any(filename.endswith(ext) for ext in ALLOWED_EXTENSIONS):
            raise serializers.ValidationError("Only PDF files are allowed.")

        content_type = getattr(value, "content_type", None)
        if content_type and content_type not in ALLOWED_CONTENT_TYPES:
            raise serializers.ValidationError("Invalid file type. Expected application/pdf.")

        if value.size > MAX_UPLOAD_SIZE_BYTES:
            max_mb = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
            raise serializers.ValidationError(f"File is too large. Max size is {max_mb}MB.")

        return value

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "source_file",
            "source_name",
            "source_mime_type",
            "source_size_bytes",
            "storage_mode",
            "extracted_text",
            "chapter_map",
            "ai_summary",
            "current_position_seconds",
            "audio_url",
            "audio_local_ref",
            "audio_duration_seconds",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status",
            "extracted_text",
            "chapter_map",
            "ai_summary",
            "audio_url",
            "audio_local_ref",
            "audio_duration_seconds",
            "created_at",
            "updated_at",
        ]


class DocumentListSerializer(serializers.ModelSerializer):
    has_extracted_text = serializers.SerializerMethodField()
    has_chapter_map = serializers.SerializerMethodField()

    def get_has_extracted_text(self, obj):
        return obj.status in {"extracted", "tts_processing", "completed", "failed"}

    def get_has_chapter_map(self, obj):
        chapter_map = getattr(obj, "chapter_map", None)
        return isinstance(chapter_map, list) and len(chapter_map) > 0

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "source_name",
            "storage_mode",
            "current_position_seconds",
            "audio_url",
            "audio_local_ref",
            "audio_duration_seconds",
            "status",
            "has_extracted_text",
            "has_chapter_map",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ExtractionJobSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source="document.title", read_only=True)

    class Meta:
        model = ExtractionJob
        fields = [
            "id",
            "document",
            "document_title",
            "source_name",
            "source_mime_type",
            "source_size_bytes",
            "storage_mode",
            "status",
            "provider",
            "text_preview",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AudioJobSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source="document.title", read_only=True)

    class Meta:
        model = AudioJob
        fields = [
            "id",
            "document",
            "document_title",
            "voice",
            "provider",
            "status",
            "audio_url",
            "audio_local_ref",
            "audio_duration_seconds",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChapterNavigationEventSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source="document.title", read_only=True)

    class Meta:
        model = ChapterNavigationEvent
        fields = [
            "id",
            "document",
            "document_title",
            "event_type",
            "query",
            "chapter_index",
            "chapter_title",
            "position_seconds",
            "confidence",
            "provider",
            "fallback_used",
            "match_excerpt",
            "payload",
            "created_at",
        ]
        read_only_fields = fields
