"""
Admin configuration for the audiobook/pdfconverter application.

This module registers models with the Django admin interface
for managing PDFs and audiobooks.
"""
from django.contrib import admin

from .models import PDF


class PDFAdmin(admin.ModelAdmin):
    """
    Admin interface configuration for PDF model.
    
    Defines how PDF instances are displayed and managed in the Django admin.
    """
    pass


# Register models with the admin site
# admin.site.register(PDF, PDFAdmin)
