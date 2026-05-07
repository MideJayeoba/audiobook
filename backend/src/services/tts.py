from __future__ import annotations

import asyncio
from dataclasses import dataclass
import contextlib
import hashlib
import os
import re
import shutil
import subprocess
import wave
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
CLOUD_TTS_CHAR_LIMIT = max(800, int(os.getenv("TTS_CLOUD_CHAR_LIMIT", "3200")))
LONG_TEXT_THRESHOLD = max(800, int(os.getenv("TTS_LONG_TEXT_THRESHOLD", "2200")))
LONG_TEXT_TARGET_CHUNKS = max(1, int(os.getenv("TTS_LONG_TEXT_TARGET_CHUNKS", "4")))
EDGE_TTS_CHAR_LIMIT = max(1200, int(os.getenv("EDGE_TTS_CHAR_LIMIT", "5000")))
GTTS_CHAR_LIMIT = max(1200, int(os.getenv("GTTS_CHAR_LIMIT", "4500")))


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


def _normalize_provider_name(provider: str | None) -> str:
    normalized = (provider or "auto").strip().lower()
    aliases = {
        "espeak-ng": "espeak",
        "google": "gtts",
        "google-tts": "gtts",
        "edge-tts": "edge",
    }
    return aliases.get(normalized, normalized)


def _provider_order(preferred_provider: str | None, text_length: int | None = None) -> list[str]:
    preferred = _normalize_provider_name(preferred_provider)
    if preferred in {"", "auto"}:
        if text_length is not None and text_length > LONG_TEXT_THRESHOLD:
            preferred_long = _normalize_provider_name(os.getenv("TTS_LONG_TEXT_PROVIDER", "edge"))
            order = [preferred_long, "edge", "gtts", "espeak"]
            deduped: list[str] = []
            for candidate in order:
                if candidate not in deduped:
                    deduped.append(candidate)
            return deduped
        return ["edge", "gtts", "espeak"]

    order = [preferred]
    for fallback in ["edge", "gtts", "espeak"]:
        if fallback not in order:
            order.append(fallback)
    return order


def _resolve_provider_voice(provider: str, requested_voice: str) -> str:
    cleaned_voice = (requested_voice or "").strip()
    if provider == "edge":
        return cleaned_voice or os.getenv("EDGE_TTS_VOICE", "en-US-AriaNeural").strip() or "en-US-AriaNeural"
    if provider == "gtts":
        if cleaned_voice:
            match = re.match(r"^([a-z]{2})(?:[-_][a-z]{2})?", cleaned_voice.lower())
            if match:
                return match.group(1)
        return os.getenv("GTTS_LANG", "en").strip() or "en"

    fallback_voice = cleaned_voice or os.getenv("DEFAULT_TTS_VOICE", "en-US-AriaNeural")
    return _normalize_voice(fallback_voice)


def _provider_label(provider: str) -> str:
    return {
        "edge": "edge-tts",
        "gtts": "gtts",
        "espeak": "espeak-ng",
    }.get(provider, provider)


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


def _split_text_for_espeak(text: str, max_words: int | None = None) -> list[str]:
    cleaned = _normalize_text_for_speech(text)
    if not cleaned:
        return []

    word_limit = max(8, int(max_words or os.getenv("ESPEAK_MAX_CHUNK_WORDS", "18")))
    sentence_parts = re.split(r"(?<=[.!?])\s+", cleaned)
    segments: list[str] = []

    for sentence in sentence_parts:
        words = sentence.split()
        if not words:
            continue

        if len(words) <= word_limit:
            segments.append(sentence.strip())
            continue

        for index in range(0, len(words), word_limit):
            chunk = " ".join(words[index : index + word_limit]).strip()
            if chunk and not chunk.endswith(('.', '!', '?')):
                chunk = f"{chunk}."
            segments.append(chunk)

    return [segment for segment in segments if segment]


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


def _concat_wav_files(segment_paths: list[Path], output_path: Path, pause_seconds: float = 0.18) -> None:
    if not segment_paths:
        raise RuntimeError("No WAV segments were generated.")

    with contextlib.ExitStack() as stack:
        inputs = [stack.enter_context(wave.open(str(path), "rb")) for path in segment_paths]
        first = inputs[0]
        params = first.getparams()

        with wave.open(str(output_path), "wb") as output_file:
            output_file.setparams(params)
            pause_frames = int(params.framerate * max(0.0, pause_seconds))
            silence = b"\x00" * pause_frames * params.sampwidth * params.nchannels

            for index, input_file in enumerate(inputs):
                output_file.writeframes(input_file.readframes(input_file.getnframes()))
                if index < len(inputs) - 1 and silence:
                    output_file.writeframes(silence)


def _synthesize_with_espeak(text: str, voice: str, target_dir: Path) -> Path:
    output_path = target_dir / _safe_output_name(text, voice, "wav")
    cached_audio = _reuse_cached_audio(output_path)
    if cached_audio:
        return cached_audio

    engine = _select_engine()
    normalized_voice = _resolve_provider_voice("espeak", voice)
    rate = max(100, min(175, int(os.getenv("ESPEAK_RATE", "128"))))
    pitch = max(20, min(75, int(os.getenv("ESPEAK_PITCH", "40"))))

    segments = _split_text_for_espeak(text)
    if not segments:
        raise ValueError("Text is required for speech synthesis.")

    if len(segments) == 1:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as temp_text_file:
            temp_text_file.write(segments[0])
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
    else:
        segment_paths: list[Path] = []
        temp_dir = Path(tempfile.mkdtemp(prefix="audiobook-tts-"))
        try:
            for index, segment in enumerate(segments):
                segment_path = temp_dir / f"segment-{index:04d}.wav"
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as temp_text_file:
                    temp_text_file.write(segment)
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
                            str(segment_path),
                            "-f",
                            str(temp_text_path),
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                except subprocess.CalledProcessError as error:
                    raise RuntimeError(f"Speech synthesis failed: {error.stderr.strip() or error.stdout.strip()}") from error
                finally:
                    temp_text_path.unlink(missing_ok=True)

                if not segment_path.is_file() or segment_path.stat().st_size == 0:
                    raise RuntimeError("Speech synthesis did not produce an audio segment.")
                segment_paths.append(segment_path)

            _concat_wav_files(segment_paths, output_path)
        finally:
            for segment_path in segment_paths:
                segment_path.unlink(missing_ok=True)
            with contextlib.suppress(Exception):
                temp_dir.rmdir()

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("Speech synthesis did not produce an audio file.")

    return output_path


async def _edge_generate(text: str, voice_name: str, output_path: Path) -> None:
    communicator = edge_tts.Communicate(text=text, voice=voice_name)
    timeout_seconds = max(5.0, float(os.getenv("EDGE_TTS_TIMEOUT_SECONDS", "45")))
    await asyncio.wait_for(communicator.save(str(output_path)), timeout=timeout_seconds)


def _synthesize_with_edge_tts(text: str, voice: str, target_dir: Path) -> Path:
    if edge_tts is None:
        raise RuntimeError("edge-tts package is not installed.")

    voice_name = _resolve_provider_voice("edge", voice)
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


def _synthesize_with_gtts(text: str, voice: str, target_dir: Path) -> Path:
    if gTTS is None:
        raise RuntimeError("gTTS package is not installed.")

    lang = _resolve_provider_voice("gtts", voice)
    output_path = target_dir / _safe_output_name(text, lang, "mp3")
    cached_audio = _reuse_cached_audio(output_path)
    if cached_audio:
        return cached_audio

    if len(text) <= GTTS_CHAR_LIMIT:
        tts = gTTS(text=text, lang=lang)
        tts.save(str(output_path))
    else:
        chunks = _split_text_for_cloud_tts(text, GTTS_CHAR_LIMIT, target_chunks=LONG_TEXT_TARGET_CHUNKS)
        segment_paths: list[Path] = []
        temp_dir = Path(tempfile.mkdtemp(prefix="audiobook-gtts-"))
        try:
            for index, chunk in enumerate(chunks):
                segment_path = temp_dir / f"segment-{index:04d}.mp3"
                tts = gTTS(text=chunk, lang=lang)
                tts.save(str(segment_path))
                if not segment_path.is_file() or segment_path.stat().st_size == 0:
                    raise RuntimeError("gTTS did not produce an audio segment.")
                segment_paths.append(segment_path)

            _concat_binary_audio_files(segment_paths, output_path)
        finally:
            for segment_path in segment_paths:
                segment_path.unlink(missing_ok=True)
            with contextlib.suppress(Exception):
                temp_dir.rmdir()

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("gTTS did not produce an audio file.")

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

    configured_provider = preferred_provider if preferred_provider is not None else os.getenv("TTS_PROVIDER", "auto")
    normalized_provider = _normalize_provider_name(configured_provider)
    providers = _provider_order(normalized_provider, len(cleaned_text))

    if len(cleaned_text) > LONG_TEXT_THRESHOLD and normalized_provider in {"", "auto"}:
        preferred_long = _normalize_provider_name(os.getenv("TTS_LONG_TEXT_PROVIDER", "edge"))
        if preferred_long in providers:
            providers = [preferred_long, *[provider for provider in providers if provider != preferred_long]]

    errors: list[str] = []
    for provider in providers:
        try:
            if provider == "edge":
                audio_path = _synthesize_with_edge_tts(cleaned_text, voice, target_dir)
                return TTSResult(audio_path=audio_path, provider=_provider_label(provider), voice=_resolve_provider_voice(provider, voice))
            if provider == "gtts":
                audio_path = _synthesize_with_gtts(cleaned_text, voice, target_dir)
                return TTSResult(audio_path=audio_path, provider=_provider_label(provider), voice=_resolve_provider_voice(provider, voice))

            audio_path = _synthesize_with_espeak(cleaned_text, voice, target_dir)
            return TTSResult(audio_path=audio_path, provider=_provider_label(provider), voice=_resolve_provider_voice(provider, voice))
        except Exception as error:
            errors.append(f"{provider}: {error}")

    raise RuntimeError("All TTS providers failed. " + " | ".join(errors))


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
