"""
Serializers for the audiobook/pdfconverter application.

This module defines serializers for converting model instances to/from JSON
for API responses and requests.
"""
from rest_framework import serializers

from .models import PDF


class PDFSerializer(serializers.ModelSerializer):
    """
    Serializer for the PDF model.
    
    Converts PDF model instances to JSON format for API responses
    and validates incoming data for creating/updating PDFs.
    """

    class Meta:
        """Meta options for PDFSerializer."""
        # Example configuration (uncomment and customize as needed):
        # model = PDF
        # fields = ['id', 'name', 'extracted_file', 'created_at']
        # read_only_fields = ['id', 'created_at']
        pass

