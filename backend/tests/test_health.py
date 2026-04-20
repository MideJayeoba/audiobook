import os

import pytest
from django.test import Client


@pytest.mark.django_db
def test_health_endpoint_returns_ok():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "audiobook.settings")
    client = Client()
    response = client.get("/api/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
