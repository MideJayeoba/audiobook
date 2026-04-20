from fastapi import FastAPI
from pydantic import BaseModel

from .extraction import extract_text_stub
from .tts import synthesize_stub

app = FastAPI(title="Audiobook Async Services", version="0.1.0")


class ExtractionRequest(BaseModel):
    document_id: int
    storage_key: str


class TTSRequest(BaseModel):
    document_id: int
    text: str
    voice: str = "en-US-Neural2-J"


@app.get("/health")
def health():
    return {"status": "ok", "service": "fastapi-services"}


@app.post("/v1/extract")
def extract(payload: ExtractionRequest):
    text = extract_text_stub(payload.storage_key)
    return {"document_id": payload.document_id, "text_preview": text[:200]}


@app.post("/v1/tts")
def tts(payload: TTSRequest):
    audio_url = synthesize_stub(payload.text, payload.voice)
    return {"document_id": payload.document_id, "audio_url": audio_url}
