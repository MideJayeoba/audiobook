import re
import os
import json
import time
from collections import Counter
from difflib import SequenceMatcher
from typing import Any

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

from .ai_providers import AIProviderError, cosine_similarity, hf_embed
from .segmentation import STOPWORDS, build_segments, segments_from_anchors, tokenize


def _extractive_summary(text: str, max_sentences: int = 3) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", cleaned)
        if sentence.strip()
    ]
    if not sentences:
        return ""

    token_counts = Counter(
        token for token in re.findall(r"[a-z0-9]+", cleaned.lower()) if token not in STOPWORDS and len(token) > 2
    )
    if not token_counts:
        return " ".join(sentences[:max_sentences])[:480]

    scored: list[tuple[float, int, str]] = []
    for index, sentence in enumerate(sentences):
        sentence_tokens = [
            token for token in re.findall(r"[a-z0-9]+", sentence.lower()) if token not in STOPWORDS and len(token) > 2
        ]
        if not sentence_tokens:
            continue
        score = sum(token_counts.get(token, 0) for token in sentence_tokens) / max(1, len(sentence_tokens))
        scored.append((score, index, sentence))

    if not scored:
        return " ".join(sentences[:max_sentences])[:480]

    best = sorted(scored, key=lambda item: item[0], reverse=True)[:max_sentences]
    best = sorted(best, key=lambda item: item[1])
    return " ".join(item[2] for item in best)[:480]


def _sample_text_for_detection(text: str, max_chars: int = 18000) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned

    slice_size = max_chars // 3
    middle_start = max(0, (len(cleaned) // 2) - (slice_size // 2))
    middle_end = middle_start + slice_size

    return "\n\n".join([cleaned[:slice_size], cleaned[middle_start:middle_end], cleaned[-slice_size:]])


def _sections_from_segments(segments: list[dict[str, Any]], confidences: list[float] | None = None) -> list[dict[str, Any]]:
    """Turn canonical segments into the section objects the client consumes.

    Each section carries its real, contiguous text (read aloud and displayed),
    a title, an excerpt, keyword aliases and a confidence. A segment may carry
    its own ``confidence`` (e.g. from AI anchoring); otherwise the aligned
    ``confidences`` list is used, falling back to a neutral default. No
    timestamps: in the local-first player each section is its own audio clip
    whose duration the browser measures natively.
    """
    confidences = confidences or []
    sections: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        title = segment["title"]
        aliases = list(segment.get("aliases", []))
        if title.lower() not in [alias.lower() for alias in aliases]:
            aliases.insert(0, title)

        confidence = segment.get("confidence")
        if confidence is None:
            confidence = confidences[index] if index < len(confidences) else 0.5
        sections.append(
            {
                "index": index,
                "title": title[:120],
                "text": segment["text"],
                "excerpt": segment["excerpt"],
                "word_count": len(segment["text"].split()),
                "confidence": round(max(0.0, min(1.0, confidence)), 3),
                "aliases": aliases[:6],
            }
        )
    return sections


def detect_chapters_ai(text: str) -> dict[str, Any]:
    """Section a document into chapters/major sections and summarize it.

    The model (Groq, when configured) supplies chapter titles, aliases and the
    summary; the actual section boundaries and text always come from
    :func:`services.segmentation.build_segments`, so the sections are contiguous
    and cover the whole book exactly once. Falls back to a keyword heuristic when
    no model is available. Provider labels are honest.
    """
    started = time.perf_counter()
    cleaned = text.strip()
    if not cleaned:
        return {
            "chapters": [],
            "summary": "No text available for chapter detection.",
            "provider": "none",
            "fallback_used": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    system_prompt = (
        "You are an expert chapter detection and summarization engine for audiobooks. "
        "Return strict JSON only with keys: summary (string), chapters (array). "
        "Each chapter object has: title (short, descriptive), start_text (a snippet of 5-10 words "
        "copied VERBATIM from the document marking exactly where that chapter/section begins), "
        "confidence (0-1), and aliases (array of alternate names). "
        "start_text MUST be copied exactly from the text so it can be located; do not paraphrase it. "
        "The 'summary' must be a highly detailed, comprehensive, multi-paragraph breakdown of the book's content, "
        "covering key themes, main characters, and a thorough plot overview. "
        "Create 3-12 chapters covering the whole document in order, and avoid generic labels like 'Chapter 1' "
        "when a descriptive title is possible."
    )
    user_prompt = (
        "Analyze this extracted book text and infer a high-quality chapter map and a detailed summary.\n"
        "For each chapter, copy start_text verbatim from where the chapter begins so it can be found in the text.\n\n"
        f"TEXT SAMPLE:\n{_sample_text_for_detection(cleaned)}"
    )

    try:
        if not genai:
            raise AIProviderError("google-genai is not installed.")
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise AIProviderError("GEMINI_API_KEY is not set.")

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[system_prompt, user_prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        
        data = json.loads(response.text)
        
        entries = [
            {
                "title": str(item.get("title", "")).strip(),
                "start_text": str(item.get("start_text", "")).strip(),
                "confidence": float(item.get("confidence", 0.8)) if str(item.get("confidence", "")).strip() else 0.8,
                "aliases": item.get("aliases", []) if isinstance(item.get("aliases"), list) else [],
            }
            for item in data.get("chapters", [])
            if isinstance(item, dict) and str(item.get("title", "")).strip()
        ]
        if not entries:
            raise AIProviderError("Model did not return chapter titles.")

        # Preferred: cut the text at the model's verbatim start anchors (real
        # boundaries). If too few anchors resolve, keep the model's titles over an
        # even split so we still benefit from AI labelling.
        segments = segments_from_anchors(cleaned, entries)
        ai_anchored = bool(segments)
        if not segments:
            segments = build_segments(cleaned, entries)

        confidences = [entry["confidence"] for entry in entries][: len(segments)]
        chapters = _sections_from_segments(segments, confidences)

        summary = str(data.get("summary", "")).strip()
        if not summary or len(summary) < 40:
            summary = _extractive_summary(cleaned) or "AI chapter detection completed."

        return {
            "chapters": chapters,
            "summary": summary,
            "provider": "gemini",
            "ai_anchored": ai_anchored,
            "fallback_used": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except Exception:
        segments = build_segments(cleaned)
        chapters = _sections_from_segments(segments, confidences=[0.5] * len(segments))
        summary = _extractive_summary(cleaned) or "Sections ready."
        return {
            "chapters": chapters,
            "summary": summary,
            "provider": "heuristic",
            "ai_anchored": False,
            "fallback_used": True,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }


def _score_local_section(query: str, section: dict[str, Any]) -> float:
    query_tokens = tokenize(query)
    title = str(section.get("title", ""))
    body = str(section.get("text", ""))
    combined_tokens = tokenize(f"{title} {body}")
    title_tokens = tokenize(title)

    if not query_tokens or not combined_tokens:
        return 0.0

    overlap_score = len(query_tokens.intersection(combined_tokens)) / len(query_tokens)
    title_score = len(query_tokens.intersection(title_tokens)) / len(query_tokens)
    phrase_score = SequenceMatcher(None, query.lower(), f"{title} {body[:1200]}".lower()).ratio()
    return min(1.0, (overlap_score * 0.5) + (title_score * 0.3) + (phrase_score * 0.2))


def semantic_seek_ai(text: str, chapters: list[dict[str, Any]], query: str) -> dict[str, Any]:
    """Find the section best matching ``query`` (used by the FastAPI service).

    Sections are rebuilt with the same ``build_segments`` split so the matched
    index aligns with ``chapters``. Returns the chapter's ``start_seconds`` when
    present (0.0 otherwise, e.g. in the local-first flow where each section is
    its own clip).
    """
    started = time.perf_counter()
    if not query.strip():
        raise ValueError("Query is required.")
    if not chapters:
        raise ValueError("No chapter map available for semantic seek.")

    segments = build_segments(text, chapters)
    if not segments:
        raise ValueError("Could not build searchable sections.")

    def chapter_field(index: int, field: str, default: Any) -> Any:
        return chapters[index].get(field, default) if 0 <= index < len(chapters) else default

    def start_for(index: int) -> float:
        return float(chapter_field(index, "start_seconds", 0.0))

    def title_for(index: int) -> str:
        fallback = segments[index]["title"] if index < len(segments) else "Unknown section"
        return str(chapter_field(index, "title", fallback))

    lexical_scores = {index: _score_local_section(query, segment) for index, segment in enumerate(segments)}

    try:
        embedding_inputs = [
            f"{segment['title']} {' '.join(segment.get('aliases', []))} {segment['text']}" for segment in segments
        ]
        vectors = hf_embed([query] + embedding_inputs)
        query_vector = vectors[0]
        segment_vectors = vectors[1:]

        scored: list[tuple[float, int, dict[str, Any]]] = []
        for index, (vector, segment) in enumerate(zip(segment_vectors, segments)):
            semantic_score = max(0.0, min(1.0, (cosine_similarity(query_vector, vector) + 1.0) / 2.0))
            hybrid_score = (semantic_score * 0.72) + (lexical_scores.get(index, 0.0) * 0.28)
            scored.append((hybrid_score, index, segment))

        best_score, best_index, best_segment = max(scored, key=lambda item: item[0])
        return {
            "position_seconds": start_for(best_index),
            "chapter_index": best_index,
            "chapter_title": title_for(best_index),
            "match_excerpt": best_segment["text"][:280],
            "confidence": round(max(0.25, min(0.98, best_score)), 3),
            "provider": "huggingface+hints",
            "fallback_used": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except Exception:
        best_index, best_score = max(lexical_scores.items(), key=lambda item: item[1])
        best_segment = segments[best_index]
        return {
            "position_seconds": start_for(best_index),
            "chapter_index": best_index,
            "chapter_title": title_for(best_index),
            "match_excerpt": best_segment["text"][:280],
            "confidence": round(max(0.3, min(0.86, best_score + 0.22)), 3),
            "provider": "keyword-fallback",
            "fallback_used": True,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }


def seek_in_chapters(chapters: list[dict[str, Any]], chapter_index: int | None, seconds: float | None) -> dict[str, Any]:
    if chapter_index is not None:
        chapter = next((item for item in chapters if int(item.get("index", -1)) == chapter_index), None)
        if not chapter:
            raise ValueError("Requested chapter index does not exist.")

        return {
            "position_seconds": float(chapter.get("start_seconds", 0.0)),
            "chapter_index": chapter_index,
            "chapter_title": chapter.get("title", "Unknown chapter"),
        }

    if seconds is not None:
        normalized = max(0.0, float(seconds))
        current = next(
            (
                item
                for item in chapters
                if float(item.get("start_seconds", 0.0)) <= normalized < float(item.get("end_seconds", 0.0))
            ),
            None,
        )

        return {
            "position_seconds": normalized,
            "chapter_index": None if current is None else int(current.get("index", -1)),
            "chapter_title": None if current is None else current.get("title", "Unknown chapter"),
        }

    raise ValueError("Provide either chapter_index or seconds.")
