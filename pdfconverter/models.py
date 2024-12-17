# api/models.py
from django.db import models

class PDF(models.Model):
    name = models.CharField(max_length=255)
    extracted_file = models.FileField(upload_to='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

