from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DocumentViewSet, health_check

router = DefaultRouter()
router.register("documents", DocumentViewSet, basename="document")

urlpatterns = [
    path("health/", health_check, name="api-health"),
    path("", include(router.urls)),
]
