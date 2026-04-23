from fastapi import FastAPI
from pydantic import BaseModel

from .ai_navigation import detect_chapters_ai, seek_in_chapters, semantic_seek_ai
from .extraction import extract_text_from_pdf
from .tts import build_public_audio_url, synthesize_speech_to_file

app = FastAPI(title="Audiobook Async Services", version="0.1.0")


class ExtractionRequest(BaseModel):
    document_id: int
    storage_key: str


class TTSRequest(BaseModel):
    document_id: int
    text: str
    voice: str = "en-US-Neural2-J"


class ChapterDetectRequest(BaseModel):
    document_id: int
    text: str


class SeekRequest(BaseModel):
    chapter_map: list[dict]
    chapter_index: int | None = None
    seconds: float | None = None


class SemanticSeekRequest(BaseModel):
    text: str
    chapter_map: list[dict]
    query: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "fastapi-services"}


@app.post("/v1/extract")
def extract(payload: ExtractionRequest):
    text = extract_text_from_pdf(payload.storage_key)
    return {"document_id": payload.document_id, "text_preview": text[:200]}


@app.post("/v1/tts")
def tts(payload: TTSRequest):
    audio_path = synthesize_speech_to_file(payload.text, payload.voice)
    audio_url = build_public_audio_url(audio_path)
    return {"document_id": payload.document_id, "audio_url": audio_url}


@app.post("/v1/chapters/detect")
def detect_chapters(payload: ChapterDetectRequest):
    data = detect_chapters_ai(payload.text)
    return {
        "document_id": payload.document_id,
        "chapters": data["chapters"],
        "summary": data["summary"],
        "provider": data.get("provider", "unknown"),
        "fallback_used": data.get("fallback_used", False),
        "latency_ms": data.get("latency_ms", 0.0),
    }


@app.post("/v1/chapters/seek")
def seek(payload: SeekRequest):
    result = seek_in_chapters(payload.chapter_map, payload.chapter_index, payload.seconds)
    return result


@app.post("/v1/chapters/semantic-seek")
def semantic_seek(payload: SemanticSeekRequest):
    result = semantic_seek_ai(payload.text, payload.chapter_map, payload.query)
    return result
