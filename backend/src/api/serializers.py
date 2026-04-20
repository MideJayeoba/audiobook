from rest_framework import serializers

from .models import Document


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "source_file",
            "extracted_text",
            "audio_url",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["status", "extracted_text", "audio_url", "created_at", "updated_at"]
