import re
import time
from collections import Counter
from difflib import SequenceMatcher
from typing import Any

from .ai_providers import AIProviderError, cosine_similarity, groq_chat_json, hf_embed


STOPWORDS = {
    "about",
    "after",
    "again",
    "all",
    "also",
    "and",
    "are",
    "because",
    "been",
    "before",
    "being",
    "between",
    "both",
    "but",
    "came",
    "can",
    "could",
    "did",
    "does",
    "doing",
    "during",
    "each",
    "from",
    "has",
    "have",
    "having",
    "here",
    "into",
    "its",
    "just",
    "made",
    "make",
    "many",
    "more",
    "most",
    "much",
    "need",
    "not",
    "only",
    "over",
    "said",
    "same",
    "should",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "time",
    "very",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
    "your",
}


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


def _split_paragraphs(text: str) -> list[str]:
    return [paragraph.strip() for paragraph in re.split(r"\n\s*\n+", text.strip()) if paragraph.strip()]


def _sample_text_for_detection(text: str, max_chars: int = 18000) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned

    slice_size = max_chars // 3
    middle_start = max(0, (len(cleaned) // 2) - (slice_size // 2))
    middle_end = middle_start + slice_size

    sampled = "\n\n".join(
        [
            cleaned[:slice_size],
            cleaned[middle_start:middle_end],
            cleaned[-slice_size:],
        ]
    )
    return sampled


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

    token_counts = Counter(token for token in re.findall(r"[a-z0-9]+", cleaned.lower()) if token not in STOPWORDS and len(token) > 2)
    if not token_counts:
        return " ".join(sentences[:max_sentences])[:480]

    scored: list[tuple[float, int, str]] = []
    for index, sentence in enumerate(sentences):
        sentence_tokens = [token for token in re.findall(r"[a-z0-9]+", sentence.lower()) if token not in STOPWORDS and len(token) > 2]
        if not sentence_tokens:
            continue
        score = sum(token_counts.get(token, 0) for token in sentence_tokens) / max(1, len(sentence_tokens))
        scored.append((score, index, sentence))

    if not scored:
        return " ".join(sentences[:max_sentences])[:480]

    best = sorted(scored, key=lambda item: item[0], reverse=True)[:max_sentences]
    best = sorted(best, key=lambda item: item[1])
    summary = " ".join(item[2] for item in best)
    return summary[:480]


def _is_heading_line(line: str) -> bool:
    return bool(
        re.match(r"^(chapter|part|section)\s+\d+([\.:\-]\s*.*)?$", line, flags=re.IGNORECASE)
        or (len(line.split()) <= 10 and (line.isupper() or line.istitle()))
    )


def _title_from_chunk(text: str, index: int) -> str:
    tokens = [token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in STOPWORDS and len(token) > 2]
    if not tokens:
        return f"Chapter {index + 1}"

    counts = Counter(tokens)
    ordered: list[str] = []
    for token, _count in counts.most_common():
        if token not in ordered:
            ordered.append(token)
        if len(ordered) == 4:
            break

    if not ordered:
        return f"Chapter {index + 1}"

    return " ".join(word.capitalize() for word in ordered)


def _chunk_text(paragraphs: list[str], target_count: int) -> list[str]:
    if not paragraphs:
        return []

    if target_count <= 1:
        return [" ".join(paragraphs)]

    total_words = sum(len(paragraph.split()) for paragraph in paragraphs) or 1
    goal_words = max(1, total_words // target_count)

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for paragraph in paragraphs:
        paragraph_words = len(paragraph.split())
        current.append(paragraph)
        current_words += paragraph_words

        if len(chunks) < target_count - 1 and current_words >= goal_words:
            chunks.append(" ".join(current).strip())
            current = []
            current_words = 0

    if current:
        chunks.append(" ".join(current).strip())

    return [chunk for chunk in chunks if chunk]


def _build_local_chapters(text: str) -> list[dict[str, Any]]:
    cleaned = text.strip()
    if not cleaned:
        return []

    paragraphs = _split_paragraphs(cleaned)
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    heading_lines = [line for line in lines if _is_heading_line(line)]

    words = cleaned.split()
    total_duration = max(60.0, len(words) / 2.3)

    if heading_lines:
        chapters = []
        chapter_count = min(len(heading_lines), 12)
        step = total_duration / max(1, chapter_count)
        for index, heading in enumerate(heading_lines[:chapter_count]):
            chapters.append(
                {
                    "index": index,
                    "title": heading[:120],
                    "start_seconds": round(index * step, 2),
                    "end_seconds": round((index + 1) * step, 2),
                    "confidence": 0.52,
                    "aliases": [heading[:120].lower()],
                }
            )
        return chapters

    chunk_count = max(1, min(8, max(1, len(words) // 220)))
    chunks = _chunk_text(paragraphs or [cleaned], chunk_count)
    total_chunk_words = sum(len(chunk.split()) for chunk in chunks) or 1

    chapters = []
    running_words = 0
    for index, chunk in enumerate(chunks):
        chunk_words = len(chunk.split())
        start_seconds = round((running_words / total_chunk_words) * total_duration, 2)
        running_words += chunk_words
        end_seconds = round((running_words / total_chunk_words) * total_duration, 2)
        title = _title_from_chunk(chunk, index)
        confidence = min(0.68, 0.42 + (len(_tokenize(title)) * 0.05))
        chapters.append(
            {
                "index": index,
                "title": title[:120],
                "start_seconds": start_seconds,
                "end_seconds": max(start_seconds + 1.0, end_seconds),
                "confidence": round(confidence, 3),
                "aliases": [title[:120].lower()],
            }
        )

    return chapters


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

    chapters = _build_local_chapters(cleaned)

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

    sampled_text = _sample_text_for_detection(cleaned)
    system_prompt = (
        "You are a chapter detection and summarization engine for audiobooks. "
        "Return strict JSON only with keys: summary (string), chapters (array of objects with title, confidence 0-1, aliases array). "
        "The summary must be 2-4 concise sentences suitable for a reader preview. "
        "Create 3-12 chapters, keep titles short and descriptive, and include likely alternate names in aliases."
    )
    user_prompt = (
        "Analyze this extracted book text sample and infer a high-quality chapter map and summary.\n"
        "Keep chapter ordering coherent and avoid generic labels like 'Chapter 1' when better labels are possible.\n\n"
        f"TEXT SAMPLE:\n{sampled_text}"
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
        summary = str(data.get("summary", "")).strip()
        if not summary or len(summary) < 40:
            summary = _extractive_summary(cleaned) or "AI chapter detection completed."

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
        fallback_summary = _extractive_summary(cleaned)
        if fallback_summary:
            fallback["summary"] = fallback_summary
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

    max_end_seconds = max(float(item.get("end_seconds", item.get("start_seconds", 0.0))) for item in chapters)
    estimated_total_duration = max(max_end_seconds, len(words) / 2.3, 60.0)

    chunks: list[dict[str, Any]] = []
    for chapter in chapters:
        index = int(chapter.get("index", 0))
        start_seconds = float(chapter.get("start_seconds", 0.0))
        end_seconds = float(chapter.get("end_seconds", start_seconds + 1.0))

        start_ratio = max(0.0, min(1.0, start_seconds / estimated_total_duration))
        end_ratio = max(start_ratio, min(1.0, end_seconds / estimated_total_duration))

        start_word = int(start_ratio * len(words))
        end_word = int(end_ratio * len(words))
        if end_word <= start_word:
            end_word = min(len(words), start_word + max(40, len(words) // max(1, len(chapters))))

        excerpt_words = words[start_word:end_word]
        if len(excerpt_words) < 40:
            neighborhood = max(60, len(words) // max(1, len(chapters)))
            start_word = max(0, start_word - neighborhood // 2)
            end_word = min(len(words), start_word + neighborhood)
            excerpt_words = words[start_word:end_word]

        aliases = chapter.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = []

        chunks.append(
            {
                "chapter_index": index,
                "chapter_title": chapter.get("title", "Unknown chapter"),
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "aliases": [str(alias) for alias in aliases if str(alias).strip()][:6],
                "text": " ".join(excerpt_words),
            }
        )

    return chunks


def _score_local_chunk(query: str, chunk: dict[str, Any]) -> float:
    query_tokens = _tokenize(query)
    chunk_title = str(chunk.get("chapter_title", ""))
    chunk_text = str(chunk.get("text", ""))
    combined_tokens = _tokenize(f"{chunk_title} {chunk_text}")
    title_tokens = _tokenize(chunk_title)

    if not query_tokens or not combined_tokens:
        return 0.0

    overlap_score = len(query_tokens.intersection(combined_tokens)) / len(query_tokens)
    title_score = len(query_tokens.intersection(title_tokens)) / len(query_tokens)
    phrase_score = SequenceMatcher(None, query.lower(), f"{chunk_title} {chunk_text[:1200]}".lower()).ratio()
    return min(1.0, (overlap_score * 0.5) + (title_score * 0.3) + (phrase_score * 0.2))


def semantic_seek_ai(text: str, chapters: list[dict[str, Any]], query: str) -> dict[str, Any]:
    started = time.perf_counter()
    if not query.strip():
        raise ValueError("Query is required.")
    if not chapters:
        raise ValueError("No chapter map available for semantic seek.")

    chunks = _chapter_chunks(text, chapters)
    if not chunks:
        raise ValueError("Could not build searchable chapter chunks.")

    lexical_scores = {index: _score_local_chunk(query, chunk) for index, chunk in enumerate(chunks)}

    try:
        embedding_inputs = [
            f"{item['chapter_title']} {' '.join(item.get('aliases', []))} {item['text']}" for item in chunks
        ]
        vectors = hf_embed([query] + embedding_inputs)
        query_vector = vectors[0]
        chunk_vectors = vectors[1:]

        scored = []
        for index, (vector, chunk) in enumerate(zip(chunk_vectors, chunks)):
            semantic_score = max(0.0, min(1.0, (cosine_similarity(query_vector, vector) + 1.0) / 2.0))
            lexical_score = lexical_scores.get(index, 0.0)
            hybrid_score = (semantic_score * 0.72) + (lexical_score * 0.28)
            scored.append((hybrid_score, semantic_score, lexical_score, chunk))

        best_hybrid, _best_semantic, _best_lexical, best_chunk = max(scored, key=lambda item: item[0])
        return {
            "position_seconds": float(best_chunk["start_seconds"]),
            "chapter_index": int(best_chunk["chapter_index"]),
            "chapter_title": str(best_chunk["chapter_title"]),
            "match_excerpt": best_chunk["text"][:280],
            "confidence": round(max(0.25, min(0.98, best_hybrid)), 3),
            "provider": "huggingface+hints",
            "fallback_used": False,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except Exception:
        scored_chunks = []
        for index, chunk in enumerate(chunks):
            score = lexical_scores.get(index, 0.0)
            scored_chunks.append((score, chunk))

        best_score, fallback = max(scored_chunks, key=lambda item: item[0])
        return {
            "position_seconds": float(fallback["start_seconds"]),
            "chapter_index": int(fallback["chapter_index"]),
            "chapter_title": str(fallback["chapter_title"]),
            "match_excerpt": fallback["text"][:280],
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
