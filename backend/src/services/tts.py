from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

try:
    import edge_tts
except Exception:  # pragma: no cover - optional dependency
    edge_tts = None

try:
    from gtts import gTTS
except Exception:  # pragma: no cover - optional dependency
    gTTS = None


BASE_DIR = Path(__file__).resolve().parents[2]
MEDIA_ROOT = Path(os.getenv("AUDIOBOOK_MEDIA_ROOT", str(BASE_DIR / "media")))
PUBLIC_BASE_URL = os.getenv("AUDIOBOOK_PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")


def _normalize_voice(voice: str) -> str:
    cleaned = (voice or "").strip().lower()
    if not cleaned:
        return "en-us"

    match = re.match(r"^([a-z]{2})(?:[-_]?([a-z]{2}))?", cleaned)
    if not match:
        return "en-us"

    language = match.group(1)
    region = match.group(2)
    if region:
        return f"{language}-{region}"
    return language


def _select_engine() -> str:
    for candidate in ("espeak-ng", "espeak"):
        if shutil.which(candidate):
            return candidate
    raise RuntimeError("No local TTS engine is installed. Install espeak-ng to enable synthesis.")


def _safe_output_name(text: str, voice: str, extension: str) -> str:
    digest = hashlib.sha1(f"{voice}\n{text}".encode("utf-8")).hexdigest()[:16]
    return f"speech-{digest}.{extension}"


def _normalize_text_for_speech(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    cleaned = re.sub(r"([a-z])([A-Z])", r"\1. \2", cleaned)
    return cleaned


def _synthesize_with_espeak(text: str, voice: str, target_dir: Path) -> Path:
    output_path = target_dir / _safe_output_name(text, voice, "wav")
    engine = _select_engine()
    normalized_voice = _normalize_voice(voice)
    rate = max(110, min(190, int(os.getenv("ESPEAK_RATE", "140"))))
    pitch = max(20, min(80, int(os.getenv("ESPEAK_PITCH", "45"))))

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as temp_text_file:
        temp_text_file.write(text)
        temp_text_path = Path(temp_text_file.name)

    try:
        subprocess.run(
            [
                engine,
                "-v",
                normalized_voice,
                "-s",
                str(rate),
                "-p",
                str(pitch),
                "-w",
                str(output_path),
                "-f",
                str(temp_text_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=240,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"Speech synthesis failed: {error.stderr.strip() or error.stdout.strip()}") from error
    finally:
        temp_text_path.unlink(missing_ok=True)

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("Speech synthesis did not produce an audio file.")

    return output_path


async def _edge_generate(text: str, voice_name: str, output_path: Path) -> None:
    communicator = edge_tts.Communicate(text=text, voice=voice_name)
    await communicator.save(str(output_path))


def _synthesize_with_edge_tts(text: str, voice: str, target_dir: Path) -> Path:
    if edge_tts is None:
        raise RuntimeError("edge-tts package is not installed.")

    voice_name = os.getenv("EDGE_TTS_VOICE", "en-US-AriaNeural").strip() or "en-US-AriaNeural"
    output_path = target_dir / _safe_output_name(text, voice_name, "mp3")
    asyncio.run(_edge_generate(text, voice_name, output_path))

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("edge-tts did not produce an audio file.")

    return output_path


def _synthesize_with_gtts(text: str, voice: str, target_dir: Path) -> Path:
    if gTTS is None:
        raise RuntimeError("gTTS package is not installed.")

    lang = os.getenv("GTTS_LANG", "en").strip() or "en"
    output_path = target_dir / _safe_output_name(text, voice or lang, "mp3")
    tts = gTTS(text=text, lang=lang)
    tts.save(str(output_path))

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("gTTS did not produce an audio file.")

    return output_path


def synthesize_speech_to_file(text: str, voice: str, output_dir: str | Path | None = None) -> Path:
    cleaned_text = _normalize_text_for_speech(text)
    if not cleaned_text:
        raise ValueError("Text is required for speech synthesis.")

    target_dir = Path(output_dir or MEDIA_ROOT / "audio")
    target_dir.mkdir(parents=True, exist_ok=True)

    preferred_provider = os.getenv("TTS_PROVIDER", "espeak").strip().lower()
    providers = [preferred_provider]
    for fallback in ["edge", "gtts", "espeak"]:
        if fallback not in providers:
            providers.append(fallback)

    errors: list[str] = []
    for provider in providers:
        try:
            if provider == "edge":
                return _synthesize_with_edge_tts(cleaned_text, voice, target_dir)
            if provider == "gtts":
                return _synthesize_with_gtts(cleaned_text, voice, target_dir)
            return _synthesize_with_espeak(cleaned_text, voice, target_dir)
        except Exception as error:
            errors.append(f"{provider}: {error}")

    raise RuntimeError("All TTS providers failed. " + " | ".join(errors))


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
