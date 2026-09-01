import os
from typing import Any

import httpx


class AIProviderError(RuntimeError):
    pass


def _extract_json_object(content: str) -> dict[str, Any]:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise AIProviderError("Model response did not contain valid JSON.")

    candidate = content[start : end + 1]
    try:
        import json

        return json.loads(candidate)
    except Exception as error:  # pragma: no cover - defensive parser
        raise AIProviderError("Failed to parse model JSON response.") from error


DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"

# Groq decommissions models periodically; transparently upgrade retired ids so a
# stale GROQ_MODEL in .env doesn't silently break AI chaptering.
_RETIRED_GROQ_MODELS = {
    "llama-3.1-70b-versatile": DEFAULT_GROQ_MODEL,
    "llama-3.3-70b-versatile": DEFAULT_GROQ_MODEL,
    "llama3-70b-8192": DEFAULT_GROQ_MODEL,
    "llama-3.1-405b-reasoning": DEFAULT_GROQ_MODEL,
    "mixtral-8x7b-32768": DEFAULT_GROQ_MODEL,
    "gemma-7b-it": DEFAULT_GROQ_MODEL,
}


def groq_chat_json(system_prompt: str, user_prompt: str, model: str | None = None) -> dict[str, Any]:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise AIProviderError("GROQ_API_KEY is not configured.")

    endpoint = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    chosen_model = (model or os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)).strip()
    chosen_model = _RETIRED_GROQ_MODELS.get(chosen_model, chosen_model)

    payload = {
        "model": chosen_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=20.0) as client:
        response = client.post(f"{endpoint}/chat/completions", json=payload, headers=headers)

    if response.status_code >= 400:
        raise AIProviderError(f"Groq request failed ({response.status_code}): {response.text[:300]}")

    content = response.json()["choices"][0]["message"]["content"]
    if isinstance(content, dict):
        return content
    return _extract_json_object(str(content))


def _to_float_vector(raw: Any) -> list[float]:
    if not isinstance(raw, list):
        raise AIProviderError("Embedding response format is invalid.")

    # Some models return token-level embeddings ([[...], [...]]); mean-pool them
    # into a single sentence vector.
    if raw and isinstance(raw[0], list):
        columns = len(raw[0])
        if columns and all(isinstance(row, list) and len(row) == columns for row in raw):
            try:
                return [sum(float(row[col]) for row in raw) / len(raw) for col in range(columns)]
            except Exception as error:  # pragma: no cover - defensive parser
                raise AIProviderError("Embedding response vector could not be parsed.") from error
        raw = raw[0]

    try:
        return [float(item) for item in raw]
    except Exception as error:  # pragma: no cover - defensive parser
        raise AIProviderError("Embedding response vector could not be parsed.") from error


def hf_embed(texts: list[str], model: str | None = None) -> list[list[float]]:
    token = os.getenv("HF_TOKEN", "").strip()
    if not token:
        raise AIProviderError("HF_TOKEN is not configured.")

    if not texts:
        return []

    chosen_model = model or os.getenv("HF_EMBEDDING_MODEL", "BAAI/bge-m3")
    endpoint = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{chosen_model}"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"inputs": [text[:8000] for text in texts], "options": {"wait_for_model": True}}

    with httpx.Client(timeout=60.0) as client:
        response = client.post(endpoint, headers=headers, json=payload)

    if response.status_code >= 400:
        raise AIProviderError(
            f"Hugging Face embedding request failed ({response.status_code}): {response.text[:300]}"
        )

    data = response.json()
    if not isinstance(data, list) or len(data) != len(texts):
        raise AIProviderError("Hugging Face embedding response shape did not match the request.")

    return [_to_float_vector(item) for item in data]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)
