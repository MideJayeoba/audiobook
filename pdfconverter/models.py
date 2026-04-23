"""
Models for the audiobook/pdfconverter application.

This module defines the database models for managing PDFs and their
derived audiobook audio files.
"""
from django.db import models


class PDF(models.Model):
    """
    Model representing a PDF document and its generated audiobook.

    Attributes:
        name: Original file name of the uploaded PDF.
        extracted_file: The stored PDF file.
        extracted_text: Full text extracted from the PDF pages.
        audio_file: Generated MP3 audiobook file.
        created_at: Timestamp of when the record was created.
    """

    name = models.CharField(max_length=255)
    extracted_file = models.FileField(upload_to='pdfs/')
    extracted_text = models.TextField(blank=True, default='')
    audio_file = models.FileField(upload_to='audio/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        """Return the PDF file name as the string representation."""
        return self.name

