# Django Audiobook Scaffold - Implementation Guide

This document provides guidance on how to implement the skeleton files in this Django audiobook application scaffold.

## Overview

This project is a **skeleton/scaffold** of a Django application for converting PDF documents to audiobooks. All files contain only structural elements (imports, class definitions, function signatures, docstrings) with no actual implementation code.

## What's Included

### 1. Models (`pdfconverter/models.py`)

**Current State:** Skeleton class with commented example field definitions

**To Implement:**
- Uncomment and customize the field definitions:
  ```python
  name = models.CharField(max_length=255)
  extracted_file = models.FileField(upload_to='pdfs/')
  created_at = models.DateTimeField(auto_now_add=True)
  ```
- Implement the `__str__()` method to return the PDF name
- Add any additional fields needed (e.g., file size, page count, audio file)

### 2. Views (`pdfconverter/views.py`)

**Current State:** Skeleton API views with comprehensive docstrings

**To Implement:**

#### PDFUploadView.upload()
- Validate and save uploaded PDF file
- Call `convertpdf()` to extract text
- Save extracted text to database
- Return appropriate Response with status and data

#### PDFRetrieveView.retrieve()
- Query database for PDF by name
- Handle DoesNotExist exception
- Return PDF data as JSON response

#### homeview()
- Render the index.html template
- Pass any necessary context data

### 3. Serializers (`pdfconverter/serializers.py`)

**Current State:** Skeleton serializer with commented Meta configuration

**To Implement:**
- Uncomment and customize the Meta class:
  ```python
  class Meta:
      model = PDF
      fields = ['id', 'name', 'extracted_file', 'created_at']
      read_only_fields = ['id', 'created_at']
  ```
- Add custom validation methods if needed
- Add custom field serializers if needed

### 4. Admin (`pdfconverter/admin.py`)

**Current State:** Skeleton admin class with commented configuration

**To Implement:**
- Uncomment the admin configuration:
  ```python
  list_display = ['name', 'created_at']
  list_filter = ['created_at']
  search_fields = ['name']
  ordering = ['-created_at']
  ```
- Uncomment the registration line
- Add custom actions if needed

### 5. PDF Utilities (`pdfconverter/readpdf.py`)

**Current State:** Skeleton functions with detailed docstrings

**To Implement:**

#### convertpdf(filename)
- Install PyMuPDF: `pip install PyMuPDF`
- Open PDF file using pymupdf
- Extract text from each page
- Save to .txt file
- Return extracted text
- Handle FileNotFoundError and UnicodeEncodeError

#### readpdf(filename)
- Install pyttsx3: `pip install pyttsx3`
- Initialize text-to-speech engine
- Read text file
- Convert text to speech
- Handle FileNotFoundError

### 6. URLs (`pdfconverter/urls.py` and `audiobook/urls.py`)

**Current State:** Commented URL patterns

**To Implement:**
- Uncomment URL patterns in both files
- Add any additional routes needed
- Configure static/media file serving for development

### 7. Tests (`pdfconverter/tests.py`)

**Current State:** 15 skeleton test cases with descriptive names

**To Implement:**
- Add test data in setUp() methods
- Implement test assertions for each test case
- Create test fixtures for PDF files
- Mock external dependencies (file I/O, TTS)

## Implementation Steps

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
# Then install additional packages when implementing utilities:
# pip install PyMuPDF pyttsx3
```

### Step 2: Update Models
1. Uncomment field definitions in `models.py`
2. Implement `__str__()` method
3. Run migrations:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

### Step 3: Update Serializers
1. Uncomment Meta class configuration
2. Test serialization/deserialization

### Step 4: Implement Views
1. Implement `upload()` method in PDFUploadView
2. Implement `retrieve()` method in PDFRetrieveView
3. Implement `homeview()` function

### Step 5: Implement PDF Utilities
1. Install PyMuPDF and pyttsx3
2. Implement `convertpdf()` function
3. Implement `readpdf()` function
4. Test with sample PDF files

### Step 6: Configure Admin
1. Uncomment admin configuration
2. Uncomment registration
3. Create superuser and test admin interface

### Step 7: Enable URLs
1. Uncomment URL patterns
2. Test all endpoints

### Step 8: Implement Tests
1. Create test fixtures
2. Implement all test methods
3. Run tests and fix any issues

### Step 9: Add Static Files
1. Configure static files serving
2. Add CSS/JavaScript for frontend
3. Create/update templates

## Testing During Development

Run checks frequently:
```bash
# System check
python manage.py check

# Run tests
python manage.py test pdfconverter

# Check for migrations
python manage.py makemigrations --dry-run
```

## Security Considerations

When implementing:
- Validate uploaded file types and sizes
- Sanitize file names
- Set appropriate file permissions
- Use environment variables for sensitive settings
- Enable CSRF protection
- Configure ALLOWED_HOSTS properly
- Use HTTPS in production
- Generate a new SECRET_KEY for production

## Additional Features to Consider

- User authentication and authorization
- Rate limiting for API endpoints
- Async task processing for PDF conversion
- File upload progress tracking
- Audio file caching
- Support for different audio formats
- Language selection for TTS
- Voice selection for TTS
- PDF preview functionality
- Download converted files

## Resources

- Django Documentation: https://docs.djangoproject.com/
- Django REST Framework: https://www.django-rest-framework.org/
- PyMuPDF Documentation: https://pymupdf.readthedocs.io/
- pyttsx3 Documentation: https://pyttsx3.readthedocs.io/

## Support

For questions or issues, please refer to the project README.md or open an issue on the repository.
