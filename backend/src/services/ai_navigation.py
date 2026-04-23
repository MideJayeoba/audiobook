import re
import time
from typing import Any

from .ai_providers import AIProviderError, cosine_similarity, groq_chat_json, hf_embed


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


def _heuristic_detect_chapters(text: str) -> dict[str, Any]:
    started = time.perf_counter()
    cleaned = text.strip()
    if not cleaned:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "chapters": [],
            "summary": "No text available for chapter detection.",
            "provider": "heuristic",
            "fallback_used": True,
            "latency_ms": elapsed_ms,
        }

    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    chapter_candidates = []

    for line in lines:
        if re.match(r"^(chapter|part|section)\s+\d+", line, flags=re.IGNORECASE):
            chapter_candidates.append(line)

    if not chapter_candidates:
        inline_matches = re.finditer(
            r"(chapter|part|section)\s+\d+[^\n]{0,90}",
            cleaned,
            flags=re.IGNORECASE,
        )
        for match in inline_matches:
            candidate = match.group(0).strip(" .:-")
            if candidate:
                chapter_candidates.append(candidate)

    if chapter_candidates:
        # Keep order while removing duplicates.
        chapter_candidates = list(dict.fromkeys(chapter_candidates))

    if not chapter_candidates:
        words = cleaned.split()
        target_count = max(1, min(8, len(words) // 250))
        chunk_size = max(1, len(words) // target_count)
        chapter_candidates = [
            f"Chapter {index + 1}: {' '.join(words[index * chunk_size : index * chunk_size + 6])}"
            for index in range(target_count)
        ]

    chapters = []
    for index, title in enumerate(chapter_candidates):
        chapters.append(
            {
                "index": index,
                "title": title[:120],
                "start_seconds": float(index * 300),
                "end_seconds": float((index + 1) * 300),
                "confidence": 0.45,
                "aliases": [title[:120].lower()],
            }
        )

    summary = " ".join(cleaned.split()[:40])
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "chapters": chapters,
        "summary": f"AI preview summary: {summary}",
        "provider": "heuristic",
        "fallback_used": True,
        "latency_ms": elapsed_ms,
    }


def _estimate_chapter_times(text: str, chapter_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    words = text.split()
    if not words:
        return []

    # Approximation: 150 spoken words per minute -> 2.5 words per second.
    seconds_per_word = 1.0 / 2.5
    total_duration = max(60.0, len(words) * seconds_per_word)
    chapter_count = max(1, len(chapter_entries))
    chapter_duration = total_duration / chapter_count

    chapters = []
    for index, entry in enumerate(chapter_entries):
        title = str(entry.get("title", f"Chapter {index + 1}")).strip() or f"Chapter {index + 1}"
        confidence = float(entry.get("confidence", 0.8))
        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = []
        aliases = [str(alias).strip() for alias in aliases if str(alias).strip()]
        if title.lower() not in [alias.lower() for alias in aliases]:
            aliases.insert(0, title)

        chapters.append(
            {
                "index": index,
                "title": title[:120],
                "start_seconds": round(index * chapter_duration, 2),
                "end_seconds": round((index + 1) * chapter_duration, 2),
                "confidence": round(max(0.0, min(1.0, confidence)), 3),
                "aliases": aliases[:6],
            }
        )

    return chapters


def detect_chapters_ai(text: str) -> dict[str, Any]:
    started = time.perf_counter()
    cleaned = text.strip()
    if not cleaned:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "chapters": [],
            "summary": "No text available for chapter detection.",
            "provider": "none",
            "fallback_used": False,
            "latency_ms": elapsed_ms,
        }

    system_prompt = (
        "You are a chapter detection engine. Return strict JSON only with keys: "
        "summary (string), chapters (array of objects with title, confidence 0-1, aliases array)."
    )
    user_prompt = (
        "Detect likely chapter boundaries for this extracted book text. "
        "Use concise chapter titles.\n\n"
        f"TEXT:\n{cleaned[:12000]}"
    )

    try:
        data = groq_chat_json(system_prompt, user_prompt)
        chapter_entries = [
            {
                "title": str(item.get("title", "")).strip(),
                "confidence": item.get("confidence", 0.8),
                "aliases": item.get("aliases", []),
            }
            for item in data.get("chapters", [])
            if isinstance(item, dict) and str(item.get("title", "")).strip()
        ]
        if not chapter_entries:
            raise AIProviderError("Model did not return chapter titles.")

        chapters = _estimate_chapter_times(cleaned, chapter_entries)
        summary = str(data.get("summary", "")).strip() or "AI chapter detection completed."
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "chapters": chapters,
            "summary": summary,
            "provider": "groq",
            "fallback_used": False,
            "latency_ms": elapsed_ms,
        }
    except Exception:
        fallback = _heuristic_detect_chapters(cleaned)
        total_ms = round((time.perf_counter() - started) * 1000, 2)
        fallback["latency_ms"] = total_ms
        fallback["fallback_used"] = True
        return fallback


def _chapter_chunks(text: str, chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = text.strip()
    if not chapters:
        return []

    words = cleaned.split()
    if not words:
        return []

    chunk_size = max(30, len(words) // len(chapters))
    chunks = []
    for chapter in chapters:
        index = int(chapter.get("index", 0))
        start = index * chunk_size
        excerpt = " ".join(words[start : start + chunk_size])
        chunks.append(
            {
                "chapter_index": index,
                "chapter_title": chapter.get("title", "Unknown chapter"),
                "start_seconds": float(chapter.get("start_seconds", 0.0)),
                "text": excerpt,
            }
        )

    return chunks


def semantic_seek_ai(text: str, chapters: list[dict[str, Any]], query: str) -> dict[str, Any]:
    started = time.perf_counter()
    if not query.strip():
        raise ValueError("Query is required.")
    if not chapters:
        raise ValueError("No chapter map available for semantic seek.")

    chunks = _chapter_chunks(text, chapters)
    if not chunks:
        raise ValueError("Could not build searchable chapter chunks.")

    try:
        vectors = hf_embed([query] + [item["text"] for item in chunks])
        query_vector = vectors[0]
        chunk_vectors = vectors[1:]
        scored = [
            (cosine_similarity(query_vector, vector), chunk)
            for vector, chunk in zip(chunk_vectors, chunks)
        ]
        best_score, best_chunk = max(scored, key=lambda item: item[0])
        return {
            "position_seconds": float(best_chunk["start_seconds"]),
            "chapter_index": int(best_chunk["chapter_index"]),
            "chapter_title": str(best_chunk["chapter_title"]),
            "match_excerpt": best_chunk["text"][:280],
            "confidence": round(max(0.0, min(1.0, (best_score + 1.0) / 2.0)), 3),
            "provider": "huggingface",
            "fallback_used": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except Exception:
        query_tokens = _tokenize(query)
        scored_chunks = []
        for chunk in chunks:
            chunk_tokens = _tokenize(f"{chunk['chapter_title']} {chunk['text']}")
            if not query_tokens or not chunk_tokens:
                score = 0.0
            else:
                overlap = len(query_tokens.intersection(chunk_tokens))
                score = overlap / max(1, len(query_tokens))
            scored_chunks.append((score, chunk))

        best_score, fallback = max(scored_chunks, key=lambda item: item[0])
        return {
            "position_seconds": float(fallback["start_seconds"]),
            "chapter_index": int(fallback["chapter_index"]),
            "chapter_title": str(fallback["chapter_title"]),
            "match_excerpt": fallback["text"][:280],
            "confidence": round(max(0.3, min(0.75, best_score + 0.2)), 3),
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
