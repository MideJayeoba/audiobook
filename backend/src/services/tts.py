from __future__ import annotations

import asyncio
from dataclasses import dataclass
import contextlib
import hashlib
import os
import re
import tempfile
from pathlib import Path

try:
    import edge_tts
except Exception:  # pragma: no cover - optional dependency
    edge_tts = None


BASE_DIR = Path(__file__).resolve().parents[2]
MEDIA_ROOT = Path(os.getenv("AUDIOBOOK_MEDIA_ROOT", str(BASE_DIR / "media")))
PUBLIC_BASE_URL = os.getenv("AUDIOBOOK_PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
LONG_TEXT_THRESHOLD = max(800, int(os.getenv("TTS_LONG_TEXT_THRESHOLD", "2200")))
LONG_TEXT_TARGET_CHUNKS = max(1, int(os.getenv("TTS_LONG_TEXT_TARGET_CHUNKS", "4")))
EDGE_TTS_CHAR_LIMIT = max(1200, int(os.getenv("EDGE_TTS_CHAR_LIMIT", "5000")))


@dataclass(frozen=True)
class TTSResult:
    audio_path: Path
    provider: str
    voice: str


DEFAULT_EDGE_VOICE_OPTIONS = [
    {"value": "en-US-AriaNeural", "label": "US English - Aria"},
    {"value": "en-US-GuyNeural", "label": "US English - Guy"},
    {"value": "en-US-JennyNeural", "label": "US English - Jenny"},
    {"value": "en-GB-SoniaNeural", "label": "UK English - Sonia"},
    {"value": "en-GB-RyanNeural", "label": "UK English - Ryan"},
    {"value": "en-NG-EzinneNeural", "label": "Nigerian English - Ezinne"},
    {"value": "en-NG-AbeoNeural", "label": "Nigerian English - Abeo"},
    {"value": "en-AU-NatashaNeural", "label": "Australian English - Natasha"},
]


def _resolve_provider_voice(requested_voice: str) -> str:
    cleaned_voice = (requested_voice or "").strip()
    return cleaned_voice or os.getenv("EDGE_TTS_VOICE", "en-US-AriaNeural").strip() or "en-US-AriaNeural"


def get_edge_voice_options() -> list[dict[str, str]]:
    configured = os.getenv("EDGE_TTS_VOICES", "").strip()
    if not configured:
        return DEFAULT_EDGE_VOICE_OPTIONS

    options: list[dict[str, str]] = []
    for item in configured.split(","):
        token = item.strip()
        if not token:
            continue
        if ":" in token:
            value, label = token.split(":", 1)
            options.append({"value": value.strip(), "label": label.strip() or value.strip()})
        else:
            options.append({"value": token, "label": token})

    return options or DEFAULT_EDGE_VOICE_OPTIONS


def _safe_output_name(text: str, voice: str, extension: str) -> str:
    digest = hashlib.sha1(f"{voice}\n{text}".encode("utf-8")).hexdigest()[:16]
    return f"speech-{digest}.{extension}"


def _reuse_cached_audio(output_path: Path) -> Path | None:
    if output_path.is_file() and output_path.stat().st_size > 0:
        return output_path
    return None


def _normalize_text_for_speech(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    cleaned = re.sub(r"[\u2018\u2019\u201C\u201D]", '"', cleaned)
    cleaned = re.sub(r"[•·]", ". ", cleaned)
    cleaned = re.sub(r"([a-z])([A-Z])", r"\1. \2", cleaned)
    return cleaned


def _split_text_for_cloud_tts(text: str, max_chars: int, target_chunks: int | None = None) -> list[str]:
    cleaned = _normalize_text_for_speech(text)
    if not cleaned:
        return []

    requested_chunks = max(1, int(target_chunks or LONG_TEXT_TARGET_CHUNKS))
    preferred_chunk_size = max(900, min(max_chars, (len(cleaned) + requested_chunks - 1) // requested_chunks))

    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # If a sentence alone exceeds max size, split by words.
        if len(sentence) > max_chars:
            words = sentence.split()
            piece = ""
            for word in words:
                candidate = f"{piece} {word}".strip()
                if len(candidate) <= max_chars:
                    piece = candidate
                    continue
                if piece:
                    chunks.append(piece)
                piece = word
            if piece:
                chunks.append(piece)
            continue

        candidate = f"{current} {sentence}".strip()
        if not current or len(candidate) <= preferred_chunk_size:
            current = candidate
        else:
            chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)

    return [chunk for chunk in chunks if chunk]


def _concat_binary_audio_files(segment_paths: list[Path], output_path: Path) -> None:
    if not segment_paths:
        raise RuntimeError("No audio segments were generated.")

    with output_path.open("wb") as output_file:
        for segment_path in segment_paths:
            with segment_path.open("rb") as segment_file:
                output_file.write(segment_file.read())

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("Audio segment concatenation failed.")


async def _edge_generate(text: str, voice_name: str, output_path: Path) -> None:
    communicator = edge_tts.Communicate(text=text, voice=voice_name)
    timeout_seconds = max(5.0, float(os.getenv("EDGE_TTS_TIMEOUT_SECONDS", "45")))
    await asyncio.wait_for(communicator.save(str(output_path)), timeout=timeout_seconds)


def _synthesize_with_edge_tts(text: str, voice: str, target_dir: Path) -> Path:
    if edge_tts is None:
        raise RuntimeError("edge-tts package is not installed.")

    voice_name = _resolve_provider_voice(voice)
    output_path = target_dir / _safe_output_name(text, voice_name, "mp3")
    cached_audio = _reuse_cached_audio(output_path)
    if cached_audio:
        return cached_audio

    if len(text) <= EDGE_TTS_CHAR_LIMIT:
        asyncio.run(_edge_generate(text, voice_name, output_path))
    else:
        chunks = _split_text_for_cloud_tts(text, EDGE_TTS_CHAR_LIMIT, target_chunks=LONG_TEXT_TARGET_CHUNKS)
        segment_paths: list[Path] = []
        temp_dir = Path(tempfile.mkdtemp(prefix="audiobook-edge-tts-"))
        try:
            for index, chunk in enumerate(chunks):
                segment_path = temp_dir / f"segment-{index:04d}.mp3"
                asyncio.run(_edge_generate(chunk, voice_name, segment_path))
                if not segment_path.is_file() or segment_path.stat().st_size == 0:
                    raise RuntimeError("edge-tts did not produce an audio segment.")
                segment_paths.append(segment_path)

            _concat_binary_audio_files(segment_paths, output_path)
        finally:
            for segment_path in segment_paths:
                segment_path.unlink(missing_ok=True)
            with contextlib.suppress(Exception):
                temp_dir.rmdir()

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("edge-tts did not produce an audio file.")

    return output_path


def synthesize_speech(
    text: str,
    voice: str,
    output_dir: str | Path | None = None,
    preferred_provider: str | None = None,
) -> TTSResult:
    cleaned_text = _normalize_text_for_speech(text)
    if not cleaned_text:
        raise ValueError("Text is required for speech synthesis.")

    target_dir = Path(output_dir or MEDIA_ROOT / "audio")
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        audio_path = _synthesize_with_edge_tts(cleaned_text, voice, target_dir)
        return TTSResult(audio_path=audio_path, provider="edge-tts", voice=_resolve_provider_voice(voice))
    except Exception as error:
        raise RuntimeError(f"TTS failed: {error}")


def synthesize_speech_to_file(text: str, voice: str, output_dir: str | Path | None = None) -> Path:
    return synthesize_speech(text, voice, output_dir=output_dir).audio_path


def build_public_audio_url(audio_path: str | Path, base_url: str | None = None) -> str:
    path = Path(audio_path)
    relative_path = path.relative_to(MEDIA_ROOT).as_posix()
    if base_url is None:
        return f"/media/{relative_path}"

    prefix = (base_url or PUBLIC_BASE_URL).rstrip("/")
    return f"{prefix}/media/{relative_path}"


def synthesize_stub(text: str, voice: str) -> str:
    audio_path = synthesize_speech_to_file(text, voice)
    return build_public_audio_url(audio_path)


from typing import AsyncGenerator

async def stream_edge_tts(text: str, voice: str) -> AsyncGenerator[bytes, None]:
    if edge_tts is None:
        raise RuntimeError("edge-tts package is not installed.")

    voice_name = _resolve_provider_voice(voice)
    
    cleaned = _normalize_text_for_speech(text)
    if not cleaned:
        return
        
    if len(cleaned) <= EDGE_TTS_CHAR_LIMIT:
        chunks = [cleaned]
    else:
        chunks = _split_text_for_cloud_tts(cleaned, EDGE_TTS_CHAR_LIMIT, target_chunks=LONG_TEXT_TARGET_CHUNKS)
        
    for chunk in chunks:
        communicator = edge_tts.Communicate(text=chunk, voice=voice_name)
        async for edge_chunk in communicator.stream():
            if edge_chunk["type"] == "audio":
                yield edge_chunk["data"]
