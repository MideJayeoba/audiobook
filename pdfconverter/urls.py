from django.urls import path
from .views import PDFUploadView, PDFRetrieveView

from .views import PDFUploadView, PDFRetrieveView

urlpatterns = [
    path('upload/', PDFUploadView.as_view(), name='pdf-upload'),
    path('retrieve/<str:name>/', PDFRetrieveView.as_view(), name='pdf-retrieve'),
]
