"""
Views for the audiobook/pdfconverter application.

This module contains API views for uploading PDFs and converting them to
audiobooks, as well as retrieving previously converted documents and
rendering the front-end template.
"""
import os

from django.conf import settings
from django.shortcuts import render
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PDF
from .readpdf import convertpdf, generate_audio
from .serializers import PDFSerializer


class PDFUploadView(APIView):
    """
    API view for uploading a PDF and converting it to an audiobook.

    Accepts a multipart POST request containing a single PDF file, extracts
    the text from every page using PyMuPDF, generates an MP3 audio file with
    gTTS, persists both files together with the extracted text in the database,
    and returns the audio URL in the response.

    Endpoint: POST /pdfconverter/upload/
    """

    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        """
        Handle a PDF upload, perform text extraction and audio generation.

        Args:
            request: DRF Request object.  The uploaded PDF must be attached
                     under the ``file`` field of the multipart form.

        Returns:
            Response (201): JSON with ``message``, ``id``, ``name``, and
                            ``audio_url`` on success.
            Response (400): JSON with ``error`` when no file or a non-PDF
                            file is submitted.
            Response (422): JSON with ``error`` when text extraction fails or
                            the PDF contains no extractable text.
            Response (500): JSON with ``error`` when audio generation fails.
        """
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {'error': 'No file provided. Attach the PDF under the "file" field.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not uploaded_file.name.lower().endswith('.pdf'):
            return Response(
                {'error': 'Only PDF files are accepted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ------------------------------------------------------------------ #
        # 1. Persist the uploaded PDF to MEDIA_ROOT/pdfs/                    #
        # ------------------------------------------------------------------ #
        pdf_name = uploaded_file.name
        pdfs_dir = os.path.join(settings.MEDIA_ROOT, 'pdfs')
        os.makedirs(pdfs_dir, exist_ok=True)
        pdf_path = os.path.join(pdfs_dir, pdf_name)

        with open(pdf_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        # ------------------------------------------------------------------ #
        # 2. Extract text from the PDF using PyMuPDF                         #
        # ------------------------------------------------------------------ #
        try:
            extracted_text = convertpdf(pdf_path)
        except (FileNotFoundError, RuntimeError) as exc:
            return Response({'error': str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        if not extracted_text.strip():
            return Response(
                {'error': 'No extractable text found in the PDF (it may be image-only).'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # ------------------------------------------------------------------ #
        # 3. Generate the MP3 audiobook with gTTS                            #
        # ------------------------------------------------------------------ #
        audio_name = os.path.splitext(pdf_name)[0] + '.mp3'
        audio_dir = os.path.join(settings.MEDIA_ROOT, 'audio')
        audio_path = os.path.join(audio_dir, audio_name)

        try:
            generate_audio(extracted_text, audio_path)
        except (ValueError, RuntimeError) as exc:
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # ------------------------------------------------------------------ #
        # 4. Save the record to the database                                  #
        # ------------------------------------------------------------------ #
        pdf_instance = PDF(name=pdf_name, extracted_text=extracted_text)
        pdf_instance.extracted_file.name = f'pdfs/{pdf_name}'
        pdf_instance.audio_file.name = f'audio/{audio_name}'
        pdf_instance.save()

        audio_url = request.build_absolute_uri(f'{settings.MEDIA_URL}audio/{audio_name}')

        return Response(
            {
                'message': 'PDF converted to audiobook successfully.',
                'id': pdf_instance.id,
                'name': pdf_instance.name,
                'audio_url': audio_url,
            },
            status=status.HTTP_201_CREATED,
        )


class PDFRetrieveView(APIView):
    """
    API view for retrieving a previously converted audiobook by PDF name.

    Endpoint: GET /pdfconverter/retrieve/<name>/
    """

    def get(self, request, name):
        """
        Retrieve a PDF record and its associated audiobook by name.

        Args:
            request: DRF Request object.
            name (str): The original file name of the uploaded PDF, e.g.
                        ``"mybook.pdf"``.

        Returns:
            Response (200): Serialised PDF data including ``audio_file`` URL.
            Response (404): JSON with ``error`` if no matching record is found.
        """
        try:
            pdf = PDF.objects.get(name=name)
        except PDF.DoesNotExist:
            return Response(
                {'error': f'No PDF record found with name "{name}".'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = PDFSerializer(pdf, context={'request': request})
        return Response(serializer.data)


def homeview(request):
    """
    Render the home page for the PDF-to-audiobook converter.

    Args:
        request: Django HttpRequest object.

    Returns:
        HttpResponse: The rendered ``index.html`` template.
    """
    return render(request, 'index.html')
