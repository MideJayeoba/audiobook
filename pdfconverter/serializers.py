"""
Serializers for the audiobook/pdfconverter application.

This module defines serializers for converting PDF model instances to/from
JSON for API responses and requests.
"""
from rest_framework import serializers

from .models import PDF


class PDFSerializer(serializers.ModelSerializer):
    """
    Serializer for the PDF model.

    Exposes all fields needed to represent a processed PDF document,
    including its extracted text and the URL of the generated audio file.
    The ``extracted_text``, ``audio_file``, and ``created_at`` fields are
    read-only because they are populated server-side during processing.
    """

    class Meta:
        model = PDF
        fields = ['id', 'name', 'extracted_file', 'extracted_text', 'audio_file', 'created_at']
        read_only_fields = ['id', 'extracted_text', 'audio_file', 'created_at']
