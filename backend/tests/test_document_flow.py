"""Tests for the stateless audiobook API.

The app is local-first: documents, sections and audio live in the browser
(IndexedDB). The backend is a set of stateless endpoints — extract text,
section + summarize, list voices, synthesize speech. These tests cover the
offline-safe paths (no network / API keys required); live Edge TTS streaming is
exercised manually.
"""

import pytest
from rest_framework.test import APIClient


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
    return ("".join(parts) + "".join(xref_lines) + trailer).encode("latin-1")


@pytest.fixture
def client():
    return APIClient()


# --- voices ---------------------------------------------------------------

@pytest.mark.django_db
def test_voices_include_at_least_six_accents_with_nigerian_male_and_female(client):
    response = client.get("/api/voices/")
    assert response.status_code == 200

    voices = response.data["voices"]
    values = {voice["value"] for voice in voices}
    assert len(values) >= 6
    # Nigerian male and female must both be offered.
    assert "en-NG-AbeoNeural" in values      # male
    assert "en-NG-EzinneNeural" in values    # female
    # Multiple distinct accents (language-REGION prefixes).
    accents = {"-".join(value.split("-")[:2]) for value in values}
    assert len(accents) >= 4


# --- extraction -----------------------------------------------------------

@pytest.mark.django_db
def test_extract_requires_a_file(client):
    response = client.post("/api/extract/", {}, format="multipart")
    assert response.status_code == 400
    assert "detail" in response.data


@pytest.mark.django_db
def test_extract_returns_text_from_pdf(client):
    from django.core.files.uploadedfile import SimpleUploadedFile

    expected = "Extracted text from a real PDF."
    file_obj = SimpleUploadedFile("sample.pdf", build_pdf_bytes(expected), content_type="application/pdf")

    response = client.post("/api/extract/", {"source_file": file_obj}, format="multipart")
    assert response.status_code == 200
    assert expected in response.data["text"]


# --- AI sectioning + summary ---------------------------------------------

@pytest.mark.django_db
def test_ai_sections_requires_text(client):
    response = client.post("/api/ai/sections/", {"text": ""}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_ai_sections_split_on_explicit_chapter_headings(client):
    text = (
        "Chapter One\nThe detective arrived in Lagos at dawn and studied the case files.\n"
        "Chapter Two\nThe investigation traced a missing shipment through shell companies.\n"
        "Chapter Three\nIn the courtroom the verdict revealed the smuggling ring."
    )
    response = client.post("/api/ai/sections/", {"text": text}, format="json")
    assert response.status_code == 200

    chapters = response.data["chapters"]
    titles = [c["title"] for c in chapters]
    assert titles == ["Chapter One", "Chapter Two", "Chapter Three"]
    # Real boundaries, still contiguous and complete.
    assert " ".join(c["text"] for c in chapters) == " ".join(text.split())


@pytest.mark.django_db
def test_ai_sections_returns_contiguous_sections_with_text_and_summary(client):
    # Distinct words so we can verify the split covers the text exactly once.
    text = " ".join(f"word{i}" for i in range(900))

    response = client.post("/api/ai/sections/", {"text": text}, format="json")
    assert response.status_code == 200

    data = response.data
    chapters = data["chapters"]
    assert len(chapters) >= 1
    assert data["summary"]
    # Honest labelling: heuristic fallback must not masquerade as AI.
    assert not data["summary"].startswith("AI preview summary:")
    assert data["provider"] in {"groq", "heuristic"}

    # Each section carries the fields the reader needs.
    for chapter in chapters:
        assert {"index", "title", "text", "excerpt", "confidence", "aliases"} <= set(chapter)
        assert chapter["text"]

    # Sections are ordered, contiguous, complete and non-overlapping:
    # concatenating them reproduces the (whitespace-normalized) input exactly.
    assert [c["index"] for c in chapters] == list(range(len(chapters)))
    assert " ".join(c["text"] for c in chapters) == text


# --- TTS validation (network-free path) -----------------------------------

@pytest.mark.django_db
def test_tts_requires_text(client):
    response = client.post("/api/tts/", {"voice": "en-NG-AbeoNeural"}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_prepare_tts_returns_a_token(client):
    response = client.post(
        "/api/tts_stream_direct/prepare/",
        data={"text": "Hello there.", "voice": "en-NG-AbeoNeural"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["token"]
