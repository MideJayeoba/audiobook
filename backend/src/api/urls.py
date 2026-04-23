from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AudioJobViewSet,
    ChapterNavigationEventViewSet,
    DocumentViewSet,
    ExtractionJobViewSet,
    health_check,
)

router = DefaultRouter()
router.register("documents", DocumentViewSet, basename="document")
router.register("extraction-jobs", ExtractionJobViewSet, basename="extraction-job")
router.register("audio-jobs", AudioJobViewSet, basename="audio-job")
router.register("navigation-events", ChapterNavigationEventViewSet, basename="navigation-event")

urlpatterns = [
    path("health/", health_check, name="api-health"),
    path("", include(router.urls)),
]
