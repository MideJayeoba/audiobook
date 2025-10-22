"""
URL configuration for the pdfconverter application.

This module defines URL patterns for PDF upload and retrieval endpoints.
"""
from django.urls import path

from .views import PDFUploadView, PDFRetrieveView


# URL patterns for pdfconverter app
urlpatterns = [
    # path('upload/', PDFUploadView.as_view(), name='pdf-upload'),
    # path('retrieve/<str:name>/', PDFRetrieveView.as_view(), name='pdf-retrieve'),
]

