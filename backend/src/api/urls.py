from django.urls import path

from .views import (
    health_check,
    extract_document,
    ai_sections,
    tts_stream,
    prepare_tts,
    tts_stream_direct,
    voices_list,
)

urlpatterns = [
    path("health/", health_check, name="api-health"),
    path("extract/", extract_document, name="api-extract"),
    path("ai/sections/", ai_sections, name="api-sections"),
    path("tts/", tts_stream, name="api-tts"),
    path("tts_stream_direct/prepare/", prepare_tts, name="prepare_tts"),
    path("tts_stream_direct/", tts_stream_direct, name="tts_stream_direct"),
    path("voices/", voices_list, name="api-voices"),
]
