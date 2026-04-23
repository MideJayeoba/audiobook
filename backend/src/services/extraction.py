from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import BinaryIO

from pypdf import PdfReader


BASE_DIR = Path(__file__).resolve().parents[2]
MEDIA_ROOT = Path(os.getenv("AUDIOBOOK_MEDIA_ROOT", str(BASE_DIR / "media")))


def _resolve_pdf_path(storage_key: str | Path) -> Path:
    candidate = Path(storage_key)
    if candidate.is_file():
        return candidate

    if candidate.is_absolute():
        return candidate

    media_candidate = MEDIA_ROOT / candidate
    if media_candidate.is_file():
        return media_candidate

    return BASE_DIR / candidate


def _normalize_text(text: str) -> str:
    cleaned = text.replace("\x00", "")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _ocr_page(pdf_path: Path, page_number: int, working_dir: Path, language: str) -> str:
    image_prefix = working_dir / f"page-{page_number}"
    image_path = working_dir / f"page-{page_number}.png"

    subprocess.run(
        [
            "pdftoppm",
            "-f",
            str(page_number),
            "-l",
            str(page_number),
            "-singlefile",
            "-png",
            str(pdf_path),
            str(image_prefix),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if not image_path.exists():
        raise RuntimeError(f"OCR image conversion failed for page {page_number}.")

    result = subprocess.run(
        ["tesseract", str(image_path), "stdout", "-l", language],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return _normalize_text(result.stdout)


def _ocr_fallback(pdf_path: Path, page_count: int, language: str) -> str:
    if shutil.which("pdftoppm") is None:
        raise RuntimeError("OCR unavailable: install poppler-utils (pdftoppm not found).")
    if shutil.which("tesseract") is None:
        raise RuntimeError("OCR unavailable: install tesseract-ocr (tesseract not found).")

    pages: list[str] = []
    with tempfile.TemporaryDirectory(prefix="ocr-") as tmp_dir:
        work_dir = Path(tmp_dir)
        for page_number in range(1, page_count + 1):
            page_text = _ocr_page(pdf_path, page_number, work_dir, language)
            if page_text:
                pages.append(page_text)

    ocr_text = "\n\n".join(pages).strip()
    if not ocr_text:
        raise ValueError("OCR completed but no text was recognized.")
    return ocr_text


def extract_text_from_pdf(source: str | Path | BinaryIO) -> str:
    if isinstance(source, (str, Path)):
        pdf_path = _resolve_pdf_path(source)
        if not pdf_path.is_file():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        with pdf_path.open("rb") as pdf_file:
            return extract_text_from_pdf(pdf_file)

    ocr_language = os.getenv("OCR_LANGUAGE", "eng").strip() or "eng"
    ocr_enabled = os.getenv("OCR_ENABLED", "true").strip().lower() == "true"

    reader = PdfReader(source, strict=False)
    pages: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        normalized = _normalize_text(page_text)
        if normalized:
            pages.append(normalized)

    extracted_text = "\n\n".join(pages).strip()
    if extracted_text:
        return extracted_text

    if not ocr_enabled:
        raise ValueError("No extractable text found in the PDF and OCR is disabled.")

    if not hasattr(source, "name"):
        raise ValueError("OCR requires a file-backed PDF source.")

    pdf_path = Path(str(source.name))
    if not pdf_path.exists():
        raise FileNotFoundError("OCR requires a readable PDF file on disk.")

    page_count = len(reader.pages)
    if page_count < 1:
        raise ValueError("PDF does not contain pages for OCR.")

    return _ocr_fallback(pdf_path, page_count, ocr_language)


extract_text_stub = extract_text_from_pdf
