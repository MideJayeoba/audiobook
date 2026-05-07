import pytest
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient


Document = apps.get_model("api", "Document")
ExtractionJob = apps.get_model("api", "ExtractionJob")
AudioJob = apps.get_model("api", "AudioJob")
ChapterNavigationEvent = apps.get_model("api", "ChapterNavigationEvent")
UserProfile = apps.get_model("users", "UserProfile")


def build_pdf_bytes(text: str) -> bytes:
    escaped_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = f"BT /F1 24 Tf 72 120 Td ({escaped_text}) Tj ET\n"

    objects = [
        "1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        "2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>endobj\n",
        "4 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
        f"5 0 obj<< /Length {len(content.encode('latin-1'))} >>stream\n{content}endstream\nendobj\n",
    ]

    parts = ["%PDF-1.4\n"]
    offsets = [0]
    current_offset = len(parts[0].encode("latin-1"))

    for obj in objects:
        offsets.append(current_offset)
        parts.append(obj)
        current_offset += len(obj.encode("latin-1"))

    xref_offset = current_offset
    xref_lines = ["xref\n", "0 6\n", "0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref_lines.append(f"{offset:010d} 00000 n \n")

    trailer = f"trailer<< /Root 1 0 R /Size 6 >>\nstartxref\n{xref_offset}\n%%EOF\n"
    pdf_bytes = "".join(parts) + "".join(xref_lines) + trailer
    return pdf_bytes.encode("latin-1")


@pytest.mark.django_db
def test_document_upload_triggers_extraction_stub(monkeypatch):
    monkeypatch.setenv("AUTO_DETECT_CHAPTERS", "true")
    user = get_user_model().objects.create_user(username="learner", password="secret123")
    client = APIClient()
    client.force_authenticate(user=user)

    expected_text = "Extracted text from a real PDF."

    file_obj = SimpleUploadedFile(
        "sample.pdf",
        build_pdf_bytes(expected_text),
        content_type="application/pdf",
    )

    response = client.post(
        "/api/documents/",
        {"title": "My First PDF", "source_file": file_obj},
        format="multipart",
    )

    assert response.status_code == 201, response.data
    assert response.data["title"] == "My First PDF"
    assert response.data["status"] in {"extracted", "completed"}
    assert expected_text in response.data["extracted_text"]
    assert response.data["source_file"].startswith("http://testserver/media/documents/")

    extraction_job = ExtractionJob.objects.filter(document__title="My First PDF").latest("created_at")
    assert extraction_job.status == ExtractionJob.Status.SUCCEEDED
    assert extraction_job.provider == "pypdf+ocr"
    assert expected_text in extraction_job.text_preview
    assert isinstance(response.data["chapter_map"], list)
    assert len(response.data["chapter_map"]) >= 1
    assert response.data["ai_summary"]


@pytest.mark.django_db
def test_document_upload_works_without_credentials_in_debug():
    client = APIClient()

    expected_text = "Guest access should still extract text."

    file_obj = SimpleUploadedFile(
        "guest-upload.pdf",
        build_pdf_bytes(expected_text),
        content_type="application/pdf",
    )

    response = client.post(
        "/api/documents/",
        {"title": "Guest PDF", "source_file": file_obj},
        format="multipart",
    )

    assert response.status_code == 201, getattr(response, "data", None)
    assert response.data["title"] == "Guest PDF"
    assert response.data["status"] in {"extracted", "completed"}
    assert expected_text in response.data["extracted_text"]

    document = Document.objects.get(title="Guest PDF")
    assert document.user.username == "guest"


@pytest.mark.django_db
def test_document_upload_rejects_non_pdf_files():
    user = get_user_model().objects.create_user(username="learner2", password="secret123")
    client = APIClient()
    client.force_authenticate(user=user)

    txt_file = SimpleUploadedFile("notes.txt", b"hello", content_type="text/plain")
    response = client.post(
        "/api/documents/",
        {"title": "Bad File", "source_file": txt_file},
        format="multipart",
    )

    assert response.status_code == 400
    assert "source_file" in response.data


@pytest.mark.django_db
def test_start_tts_marks_document_completed():
    user = get_user_model().objects.create_user(username="learner3", password="secret123")
    client = APIClient()
    client.force_authenticate(user=user)

    document = Document.objects.create(
        user=user,
        title="Extracted Doc",
        source_file="documents/sample.pdf",
        extracted_text="This text is ready for speech.",
        status=Document.Status.EXTRACTED,
    )

    response = client.post(f"/api/documents/{document.id}/start-tts/", {"voice": "en-US-Neural2-J"}, format="json")

    assert response.status_code == 200
    assert response.data["status"] == "completed"
    assert response.data["audio_local_ref"].startswith("local://speech-")
    assert response.data["audio_url"].startswith("/media/audio/")

    audio_job = AudioJob.objects.filter(document=document).latest("created_at")
    assert audio_job.status == AudioJob.Status.SUCCEEDED
    assert audio_job.voice == "en-US-Neural2-J"


@pytest.mark.django_db
def test_start_tts_requires_extracted_text():
    user = get_user_model().objects.create_user(username="learner4", password="secret123")
    client = APIClient()
    client.force_authenticate(user=user)

    document = Document.objects.create(
        user=user,
        title="Not Extracted Yet",
        source_file="documents/sample.pdf",
        extracted_text="",
        status=Document.Status.UPLOADED,
    )

    response = client.post(f"/api/documents/{document.id}/start-tts/", {}, format="json")

    assert response.status_code == 400
    assert "detail" in response.data


@pytest.mark.django_db
def test_detect_chapters_populates_document_chapter_map():
    user = get_user_model().objects.create_user(username="learner5", password="secret123")
    client = APIClient()
    client.force_authenticate(user=user)

    document = Document.objects.create(
        user=user,
        title="Book with sections",
        source_file="documents/book.pdf",
        extracted_text="Chapter 1 Beginning\nSome text\nChapter 2 Middle\nMore text",
        status=Document.Status.EXTRACTED,
    )

    response = client.post(f"/api/documents/{document.id}/detect-chapters/", {}, format="json")

    assert response.status_code == 200
    assert len(response.data["chapter_map"]) >= 1
    assert response.data["ai_summary"]
    assert "provider" in response.data
    assert "fallback_used" in response.data
    assert "latency_ms" in response.data
    assert "confidence" in response.data["chapter_map"][0]
    assert "aliases" in response.data["chapter_map"][0]


@pytest.mark.django_db
def test_seek_by_chapter_sets_current_position():
    user = get_user_model().objects.create_user(username="learner6", password="secret123")
    client = APIClient()
    client.force_authenticate(user=user)

    document = Document.objects.create(
        user=user,
        title="Seekable book",
        source_file="documents/book.pdf",
        extracted_text="Chapter 1 Start\nText\nChapter 2 Later",
        status=Document.Status.EXTRACTED,
        chapter_map=[
            {"index": 0, "title": "Chapter 1", "start_seconds": 0.0, "end_seconds": 300.0},
            {"index": 1, "title": "Chapter 2", "start_seconds": 300.0, "end_seconds": 600.0},
        ],
    )

    response = client.post(f"/api/documents/{document.id}/seek/", {"chapter_index": 1}, format="json")

    assert response.status_code == 200
    assert response.data["position_seconds"] == 300.0
    assert response.data["chapter_index"] == 1

    document.refresh_from_db()
    assert document.current_position_seconds == 300.0

    nav_event = ChapterNavigationEvent.objects.filter(document=document, event_type=ChapterNavigationEvent.EventType.SEEK).latest("created_at")
    assert nav_event.chapter_index == 1
    assert nav_event.position_seconds == 300.0


@pytest.mark.django_db
def test_semantic_seek_returns_position_and_updates_document():
    user = get_user_model().objects.create_user(username="learner7", password="secret123")
    client = APIClient()
    client.force_authenticate(user=user)

    document = Document.objects.create(
        user=user,
        title="Semantic navigation",
        source_file="documents/book.pdf",
        extracted_text=(
            "Chapter 1 Arrival in Lagos with tense atmosphere and political unrest. "
            "Chapter 2 Investigation into mysterious disappearances in the capital city. "
            "Chapter 3 Courtroom resolution and final reflections."
        ),
        status=Document.Status.EXTRACTED,
        chapter_map=[
            {"index": 0, "title": "Arrival", "start_seconds": 0.0, "end_seconds": 300.0},
            {"index": 1, "title": "Investigation", "start_seconds": 300.0, "end_seconds": 600.0},
            {"index": 2, "title": "Resolution", "start_seconds": 600.0, "end_seconds": 900.0},
        ],
    )

    response = client.post(
        f"/api/documents/{document.id}/semantic-seek/",
        {"query": "take me to the investigation part"},
        format="json",
    )

    assert response.status_code == 200
    assert "position_seconds" in response.data
    assert response.data["provider"] in {"huggingface+hints", "keyword-fallback"}
    assert "fallback_used" in response.data
    assert "latency_ms" in response.data

    document.refresh_from_db()
    assert document.current_position_seconds >= 0.0

    nav_event = ChapterNavigationEvent.objects.filter(
        document=document, event_type=ChapterNavigationEvent.EventType.SEMANTIC_SEEK
    ).latest("created_at")
    assert nav_event.query == "take me to the investigation part"
    assert nav_event.position_seconds >= 0.0


@pytest.mark.django_db
def test_playback_seek_returns_audio_url_and_target_offset():
    user = get_user_model().objects.create_user(username="learner8", password="secret123")
    client = APIClient()
    client.force_authenticate(user=user)

    document = Document.objects.create(
        user=user,
        title="Playback book",
        source_file="documents/book.pdf",
        extracted_text="Chapter 1 Arrival. Chapter 2 Investigation. Chapter 3 Resolution.",
        audio_local_ref="local://document-123.mp3",
        status=Document.Status.COMPLETED,
        chapter_map=[
            {"index": 0, "title": "Arrival", "start_seconds": 0.0, "end_seconds": 300.0},
            {"index": 1, "title": "Investigation", "start_seconds": 300.0, "end_seconds": 600.0},
            {"index": 2, "title": "Resolution", "start_seconds": 600.0, "end_seconds": 900.0},
        ],
    )

    response = client.post(
        f"/api/documents/{document.id}/playback-seek/",
        {"query": "go to the investigation section"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["audio_local_ref"] == "local://document-123.mp3"
    assert "target_offset_seconds" in response.data
    assert response.data["provider"] in {"huggingface+hints", "keyword-fallback"}
    assert "fallback_used" in response.data
    assert "latency_ms" in response.data

    document.refresh_from_db()
    assert document.current_position_seconds >= 0.0


@pytest.mark.django_db
def test_document_upload_with_local_device_storage():
    user = get_user_model().objects.create_user(username="learner9", password="secret123")
    client = APIClient()
    client.force_authenticate(user=user)

    expected_text = "Local device PDFs should still be extracted."
    file_obj = SimpleUploadedFile(
        "local-device.pdf",
        build_pdf_bytes(expected_text),
        content_type="application/pdf",
    )

    response = client.post(
        "/api/documents/",
        {
            "title": "Client-only PDF",
            "storage_mode": "local_device",
            "source_file": file_obj,
        },
        format="multipart",
    )

    assert response.status_code == 201
    assert expected_text in response.data["extracted_text"]
    assert response.data["storage_mode"] == "local_device"
    assert response.data["status"] in {"extracted", "completed"}


@pytest.mark.django_db
def test_user_profile_is_created_for_new_user():
    user = get_user_model().objects.create_user(username="learner10", password="secret123")

    profile = UserProfile.objects.get(user=user)

    assert profile.display_name == "learner10"
    assert profile.notify_by_email is True


@pytest.mark.django_db
def test_job_history_endpoints_return_user_scoped_records():
    user = get_user_model().objects.create_user(username="learner11", password="secret123")
    client = APIClient()
    client.force_authenticate(user=user)

    document = Document.objects.create(
        user=user,
        title="History PDF",
        source_file="documents/history.pdf",
        extracted_text="History text",
        status=Document.Status.EXTRACTED,
    )
    extraction_job = ExtractionJob.objects.create(
        user=user,
        document=document,
        source_name="history.pdf",
        status=ExtractionJob.Status.SUCCEEDED,
        provider="stub",
        text_preview="History text",
    )
    audio_job = AudioJob.objects.create(
        user=user,
        document=document,
        voice="en-US-Neural2-J",
        status=AudioJob.Status.SUCCEEDED,
        provider="stub",
        audio_local_ref="local://history.mp3",
    )
    ChapterNavigationEvent.objects.create(
        user=user,
        document=document,
        event_type=ChapterNavigationEvent.EventType.SEMANTIC_SEEK,
        query="open chapter 2",
        chapter_index=1,
        chapter_title="Chapter 2",
        position_seconds=120.0,
        confidence=0.8,
        provider="keyword-fallback",
    )

    extraction_response = client.get("/api/extraction-jobs/?document=%s" % document.id)
    audio_response = client.get("/api/audio-jobs/?document=%s" % document.id)
    navigation_response = client.get("/api/navigation-events/?document=%s" % document.id)

    assert extraction_response.status_code == 200
    assert audio_response.status_code == 200
    assert navigation_response.status_code == 200

    assert extraction_response.data[0]["id"] == extraction_job.id
    assert audio_response.data[0]["id"] == audio_job.id
    assert navigation_response.data[0]["document"] == document.id


@pytest.mark.django_db
def test_delete_document_can_keep_job_history_and_remove_files():
    user = get_user_model().objects.create_user(username="learner12", password="secret123")
    client = APIClient()
    client.force_authenticate(user=user)

    source_file = SimpleUploadedFile(
        "delete-me.pdf",
        build_pdf_bytes("Delete me"),
        content_type="application/pdf",
    )
    document = Document.objects.create(
        user=user,
        title="Delete Me",
        source_file=source_file,
        extracted_text="Delete me text",
        audio_url="/media/audio/delete-me.wav",
        audio_local_ref="local://delete-me.wav",
        status=Document.Status.COMPLETED,
    )
    extraction_job = ExtractionJob.objects.create(
        user=user,
        document=document,
        source_name="delete-me.pdf",
        status=ExtractionJob.Status.SUCCEEDED,
    )
    audio_job = AudioJob.objects.create(
        user=user,
        document=document,
        voice="en-US-Neural2-J",
        status=AudioJob.Status.SUCCEEDED,
    )
    navigation_event = ChapterNavigationEvent.objects.create(
        user=user,
        document=document,
        event_type=ChapterNavigationEvent.EventType.SEMANTIC_SEEK,
    )

    source_file_name = document.source_file.name
    audio_path = settings.MEDIA_ROOT / "audio" / "delete-me.wav"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"audio")

    response = client.delete(f"/api/documents/{document.id}/?keep_history=true")

    assert response.status_code == 204
    assert not Document.objects.filter(id=document.id, is_deleted=False).exists()
    assert Document.objects.filter(id=document.id, is_deleted=True).exists()
    assert ExtractionJob.objects.filter(id=extraction_job.id).exists()
    assert AudioJob.objects.filter(id=audio_job.id).exists()
    assert ChapterNavigationEvent.objects.filter(id=navigation_event.id).exists()
    assert not audio_path.exists()
    assert source_file_name and not document.source_file.storage.exists(source_file_name)

    document.refresh_from_db()
    assert document.source_file.name == ""
    assert document.audio_url == ""
    assert document.audio_local_ref == ""


@pytest.mark.django_db
def test_delete_document_can_remove_job_history():
    user = get_user_model().objects.create_user(username="learner13", password="secret123")
    client = APIClient()
    client.force_authenticate(user=user)

    document = Document.objects.create(
        user=user,
        title="Delete Everything",
        source_file="documents/delete-everything.pdf",
        extracted_text="Delete everything text",
        status=Document.Status.EXTRACTED,
    )
    extraction_job = ExtractionJob.objects.create(
        user=user,
        document=document,
        source_name="delete-everything.pdf",
        status=ExtractionJob.Status.SUCCEEDED,
    )

    response = client.delete(f"/api/documents/{document.id}/?keep_history=false")

    assert response.status_code == 204
    assert not Document.objects.filter(id=document.id).exists()
    assert not ExtractionJob.objects.filter(id=extraction_job.id).exists()
