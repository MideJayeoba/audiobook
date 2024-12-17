import os
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import PDF
from .readpdf import convertpdf, readpdf
from django.shortcuts import render

class PDFUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        serializer = PDF(data=request.data)
        if serializer.is_valid():
            txt_file = serializer.validated_data['extracted_text']
            filename = txt_file.name

            # Convert PDF to text
            extracted_text = convertpdf(filename[:-4])  # Remove .pdf extension for the function
            
            if extracted_text:
                # Save the extracted text to a .txt file
                txt_filename = filename[:-4] + '.txt'
                with open(os.path.join('media', txt_filename), 'w', encoding='utf-8') as txt_file:
                    txt_file.write(extracted_text)
                return Response({'message': 'File processed successfully', 'txt_file': txt_filename}, status=status.HTTP_201_CREATED), readpdf(txt_filename)
            else:
                return Response({'error': 'Error extracting text from PDF'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class PDFRetrieveView(APIView):
    def get(self, request, name):
        try:
            pdf = PDF.objects.get(name=name)
            return Response({
                'name': pdf.name,
                'text': pdf.extracted_file
                # 'file_url': pdf.file.url  # Removed since the file is no longer stored
            })
        except PDF.DoesNotExist:
            return Response({'message': 'PDF not found!'}, status=status.HTTP_404_NOT_FOUND)

def homeview(request):
    """Render the index HTML page."""
    return render(request, 'index.html')
