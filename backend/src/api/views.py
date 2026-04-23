import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from services.ai_navigation import detect_chapters_ai, seek_in_chapters, semantic_seek_ai
from services.extraction import extract_text_from_pdf
from services.tts import build_public_audio_url, synthesize_speech_to_file

from .models import AudioJob, ChapterNavigationEvent, Document, ExtractionJob
from .serializers import (
    AudioJobSerializer,
    ChapterNavigationEventSerializer,
    DocumentListSerializer,
    DocumentSerializer,
    ExtractionJobSerializer,
)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health_check(_request):
    return Response({"status": "ok", "service": "django-api"})


class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer

    def get_serializer_class(self):
        if self.action == "list":
            return DocumentListSerializer
        return DocumentSerializer

    def _auto_start_tts_enabled(self) -> bool:
        return os.getenv("AUTO_START_TTS", "true").strip().lower() == "true"

    def _resolve_actor(self, request):
        if request.user.is_authenticated:
            return request.user

        user_model = get_user_model()
        guest_username = os.getenv("DEV_GUEST_USERNAME", "guest")
        guest_user, _ = user_model.objects.get_or_create(
            username=guest_username,
            defaults={"email": f"{guest_username}@local.dev"},
        )
        return guest_user

    def _create_extraction_job(self, document: Document) -> ExtractionJob:
        return ExtractionJob.objects.create(
            user=document.user,
            document=document,
            source_name=document.source_name,
            source_mime_type=document.source_mime_type,
            source_size_bytes=document.source_size_bytes,
            storage_mode=document.storage_mode,
            status=ExtractionJob.Status.QUEUED,
        )

    def _create_audio_job(self, document: Document, voice: str) -> AudioJob:
        return AudioJob.objects.create(
            user=document.user,
            document=document,
            voice=voice,
            status=AudioJob.Status.QUEUED,
        )

    def _run_tts_pipeline(self, document: Document, voice: str, base_url: str | None = None) -> None:
        audio_job = self._create_audio_job(document, voice)

        audio_job.status = AudioJob.Status.RUNNING
        audio_job.started_at = timezone.now()
        audio_job.save(update_fields=["status", "started_at", "updated_at"])

        document.status = Document.Status.TTS_PROCESSING
        document.save(update_fields=["status", "updated_at"])

        audio_path = synthesize_speech_to_file(document.extracted_text, voice)
        generated_audio_url = build_public_audio_url(audio_path, base_url=base_url)
        document.audio_local_ref = f"local://{Path(audio_path).name}"
        document.audio_url = generated_audio_url
        document.audio_duration_seconds = max(
            document.audio_duration_seconds,
            round(max(1, len(document.extracted_text.split())) / 2.5, 2),
        )
        document.status = Document.Status.COMPLETED
        document.save(
            update_fields=["audio_url", "audio_local_ref", "audio_duration_seconds", "status", "updated_at"]
        )

        audio_job.audio_url = document.audio_url
        audio_job.audio_local_ref = document.audio_local_ref
        audio_job.audio_duration_seconds = document.audio_duration_seconds
        audio_job.provider = "espeak-ng"
        audio_job.status = AudioJob.Status.SUCCEEDED
        audio_job.completed_at = timezone.now()
        audio_job.save(
            update_fields=[
                "audio_url",
                "audio_local_ref",
                "audio_duration_seconds",
                "provider",
                "status",
                "completed_at",
                "updated_at",
            ]
        )

    def _record_navigation_event(self, document: Document, event_type: str, result: dict, query: str = "", payload: dict | None = None):
        ChapterNavigationEvent.objects.create(
            user=document.user,
            document=document,
            event_type=event_type,
            query=query,
            chapter_index=result.get("chapter_index"),
            chapter_title=result.get("chapter_title", "") or "",
            position_seconds=float(result.get("position_seconds", 0.0)),
            confidence=float(result.get("confidence", 0.0)),
            provider=str(result.get("provider", "")),
            fallback_used=bool(result.get("fallback_used", False)),
            match_excerpt=str(result.get("match_excerpt", "")),
            payload=payload or {},
        )

    def get_queryset(self):
        actor = self._resolve_actor(self.request)
        return Document.objects.filter(user=actor).order_by("-created_at")

    def get_permissions(self):
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        actor = self._resolve_actor(self.request)
        document = serializer.save(user=actor, status=Document.Status.UPLOADED)
        extraction_job = self._create_extraction_job(document)

        if document.source_file:
            document.source_name = document.source_name or document.source_file.name.split("/")[-1]
            document.source_mime_type = document.source_mime_type or getattr(document.source_file, "content_type", "")
            document.source_size_bytes = document.source_size_bytes or int(getattr(document.source_file, "size", 0) or 0)
            if not document.storage_mode:
                document.storage_mode = "uploaded"
            document.save(
                update_fields=[
                    "source_name",
                    "source_mime_type",
                    "source_size_bytes",
                    "storage_mode",
                    "updated_at",
                ]
            )

        try:
            extraction_job.status = ExtractionJob.Status.RUNNING
            extraction_job.started_at = timezone.now()
            extraction_job.save(update_fields=["status", "started_at", "updated_at"])

            document.status = Document.Status.EXTRACTING
            document.save(update_fields=["status", "updated_at"])

            if document.source_file:
                storage_key = document.source_file.path
            else:
                storage_key = document.source_name or document.title

            extracted_text = extract_text_from_pdf(storage_key)
            document.extracted_text = extracted_text
            document.status = Document.Status.EXTRACTED
            document.save(update_fields=["extracted_text", "status", "updated_at"])

            extraction_job.text_preview = extracted_text[:500]
            extraction_job.provider = "pypdf+ocr"
            extraction_job.status = ExtractionJob.Status.SUCCEEDED
            extraction_job.completed_at = timezone.now()
            extraction_job.save(update_fields=["text_preview", "provider", "status", "completed_at", "updated_at"])
        except Exception as error:
            document.status = Document.Status.FAILED
            document.save(update_fields=["status", "updated_at"])
            extraction_job.status = ExtractionJob.Status.FAILED
            extraction_job.error_message = str(error)[:2000] or "Extraction failed."
            extraction_job.completed_at = timezone.now()
            extraction_job.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
            return

        if self._auto_start_tts_enabled() and document.extracted_text.strip():
            try:
                self._run_tts_pipeline(document, voice=os.getenv("DEFAULT_TTS_VOICE", "en-US-Neural2-J"))
            except Exception as error:
                document.status = Document.Status.FAILED
                document.save(update_fields=["status", "updated_at"])
                latest_job = AudioJob.objects.filter(document=document).order_by("-created_at").first()
                if latest_job:
                    latest_job.status = AudioJob.Status.FAILED
                    latest_job.error_message = str(error)[:2000] or "TTS processing failed."
                    latest_job.completed_at = timezone.now()
                    latest_job.save(update_fields=["status", "error_message", "completed_at", "updated_at"])

    @action(detail=True, methods=["post"], url_path="start-tts")
    def start_tts(self, request, pk=None):
        document = self.get_object()

        if not document.extracted_text.strip():
            return Response(
                {"detail": "Document must be extracted before TTS can start."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        voice = request.data.get("voice", "en-US-Neural2-J")
        try:
            self._run_tts_pipeline(
                document,
                voice=voice,
            )
        except Exception as error:
            document.status = Document.Status.FAILED
            document.save(update_fields=["status", "updated_at"])
            latest_job = AudioJob.objects.filter(document=document).order_by("-created_at").first()
            if latest_job:
                latest_job.status = AudioJob.Status.FAILED
                latest_job.error_message = str(error)[:2000] or "TTS processing failed."
                latest_job.completed_at = timezone.now()
                latest_job.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
                return Response({"detail": latest_job.error_message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response({"detail": "TTS processing failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(self.get_serializer(document).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="detect-chapters")
    def detect_chapters(self, request, pk=None):
        document = self.get_object()
        if not document.extracted_text.strip():
            return Response(
                {"detail": "Document must be extracted before chapter detection can run."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = detect_chapters_ai(document.extracted_text)
        document.chapter_map = data["chapters"]
        document.ai_summary = data["summary"]
        document.save(update_fields=["chapter_map", "ai_summary", "updated_at"])
        payload = self.get_serializer(document).data
        payload.update(
            {
                "provider": data.get("provider", "unknown"),
                "fallback_used": data.get("fallback_used", False),
                "latency_ms": data.get("latency_ms", 0.0),
            }
        )
        self._record_navigation_event(
            document,
            ChapterNavigationEvent.EventType.DETECT_CHAPTERS,
            {"position_seconds": document.current_position_seconds, "chapter_index": None, "chapter_title": ""},
            payload={"latency_ms": data.get("latency_ms", 0.0), "chapters": len(data.get("chapters", []))},
        )
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="seek")
    def seek(self, request, pk=None):
        document = self.get_object()
        if not document.chapter_map:
            return Response(
                {"detail": "No chapter map available. Run chapter detection first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        chapter_index = request.data.get("chapter_index")
        seconds = request.data.get("seconds")

        try:
            chapter_index = None if chapter_index is None else int(chapter_index)
            seconds = None if seconds is None else float(seconds)
            result = seek_in_chapters(document.chapter_map, chapter_index, seconds)
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        document.current_position_seconds = result["position_seconds"]
        document.save(update_fields=["current_position_seconds", "updated_at"])
        self._record_navigation_event(document, ChapterNavigationEvent.EventType.SEEK, result, payload={"chapter_index": chapter_index, "seconds": seconds})
        payload = {
            "document_id": document.id,
            "position_seconds": result["position_seconds"],
            "chapter_index": result["chapter_index"],
            "chapter_title": result["chapter_title"],
        }
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="semantic-seek")
    def semantic_seek(self, request, pk=None):
        document = self.get_object()
        query = str(request.data.get("query", "")).strip()

        if not document.extracted_text.strip():
            return Response({"detail": "Document text is required for semantic seek."}, status=status.HTTP_400_BAD_REQUEST)

        if not document.chapter_map:
            detected = detect_chapters_ai(document.extracted_text)
            document.chapter_map = detected["chapters"]
            document.ai_summary = detected["summary"]
            document.save(update_fields=["chapter_map", "ai_summary", "updated_at"])

        try:
            result = semantic_seek_ai(document.extracted_text, document.chapter_map, query)
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        document.current_position_seconds = result["position_seconds"]
        document.save(update_fields=["current_position_seconds", "updated_at"])
        self._record_navigation_event(
            document,
            ChapterNavigationEvent.EventType.SEMANTIC_SEEK,
            result,
            query=query,
            payload={"query": query},
        )
        payload = {
            "document_id": document.id,
            "query": query,
            "position_seconds": result["position_seconds"],
            "chapter_index": result["chapter_index"],
            "chapter_title": result["chapter_title"],
            "confidence": result["confidence"],
            "provider": result["provider"],
            "fallback_used": result.get("fallback_used", False),
            "latency_ms": result.get("latency_ms", 0.0),
            "match_excerpt": result["match_excerpt"],
        }
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="playback-seek")
    def playback_seek(self, request, pk=None):
        document = self.get_object()
        if not document.audio_url and not document.audio_local_ref:
            return Response(
                {"detail": "Audio is not available yet. Run TTS first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        chapter_index = request.data.get("chapter_index")
        seconds = request.data.get("seconds")
        query = str(request.data.get("query", "")).strip()

        try:
            if query:
                if not document.chapter_map:
                    detected = detect_chapters_ai(document.extracted_text)
                    document.chapter_map = detected["chapters"]
                    document.ai_summary = detected["summary"]
                    document.save(update_fields=["chapter_map", "ai_summary", "updated_at"])
                result = semantic_seek_ai(document.extracted_text, document.chapter_map, query)
            else:
                if not document.chapter_map:
                    return Response(
                        {"detail": "No chapter map available. Run chapter detection first or use query."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                chapter_index = None if chapter_index is None else int(chapter_index)
                seconds = None if seconds is None else float(seconds)
                result = seek_in_chapters(document.chapter_map, chapter_index, seconds)
                result.update(
                    {
                        "confidence": 1.0,
                        "provider": "direct-seek",
                        "fallback_used": False,
                        "latency_ms": 0.0,
                        "match_excerpt": "",
                    }
                )
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        document.current_position_seconds = result["position_seconds"]
        document.save(update_fields=["current_position_seconds", "updated_at"])
        self._record_navigation_event(
            document,
            ChapterNavigationEvent.EventType.PLAYBACK_SEEK,
            result,
            query=query,
            payload={"chapter_index": chapter_index, "seconds": seconds, "query": query},
        )

        payload = {
            "document_id": document.id,
            "audio_url": document.audio_url,
            "audio_local_ref": document.audio_local_ref,
            "target_offset_seconds": result["position_seconds"],
            "chapter_index": result["chapter_index"],
            "chapter_title": result["chapter_title"],
            "confidence": result.get("confidence", 1.0),
            "provider": result.get("provider", "direct-seek"),
            "fallback_used": result.get("fallback_used", False),
            "latency_ms": result.get("latency_ms", 0.0),
            "match_excerpt": result.get("match_excerpt", ""),
        }
        return Response(payload, status=status.HTTP_200_OK)


class ExtractionJobViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ExtractionJobSerializer

    def get_permissions(self):
        return [permissions.AllowAny()]

    def get_queryset(self):
        actor = self.request.user
        if settings.DEBUG and not actor.is_authenticated:
            actor = get_user_model().objects.filter(username=os.getenv("DEV_GUEST_USERNAME", "guest")).first()
        if not actor:
            return ExtractionJob.objects.none()

        queryset = ExtractionJob.objects.filter(user=actor).select_related("document")
        document_id = self.request.query_params.get("document")
        status_value = self.request.query_params.get("status")
        if document_id:
            queryset = queryset.filter(document_id=document_id)
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset


class AudioJobViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AudioJobSerializer

    def get_permissions(self):
        return [permissions.AllowAny()]

    def get_queryset(self):
        actor = self.request.user
        if settings.DEBUG and not actor.is_authenticated:
            actor = get_user_model().objects.filter(username=os.getenv("DEV_GUEST_USERNAME", "guest")).first()
        if not actor:
            return AudioJob.objects.none()

        queryset = AudioJob.objects.filter(user=actor).select_related("document")
        document_id = self.request.query_params.get("document")
        status_value = self.request.query_params.get("status")
        if document_id:
            queryset = queryset.filter(document_id=document_id)
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset


class ChapterNavigationEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ChapterNavigationEventSerializer

    def get_permissions(self):
        return [permissions.AllowAny()]

    def get_queryset(self):
        actor = self.request.user
        if settings.DEBUG and not actor.is_authenticated:
            actor = get_user_model().objects.filter(username=os.getenv("DEV_GUEST_USERNAME", "guest")).first()
        if not actor:
            return ChapterNavigationEvent.objects.none()

        queryset = ChapterNavigationEvent.objects.filter(user=actor).select_related("document")
        document_id = self.request.query_params.get("document")
        event_type = self.request.query_params.get("event_type")
        if document_id:
            queryset = queryset.filter(document_id=document_id)
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        return queryset
