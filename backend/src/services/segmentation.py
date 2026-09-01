"""Canonical document segmentation.

Single source of truth for how an extracted document is split into ordered,
contiguous, non-overlapping sections. Chapter detection (and, if ever wired,
semantic seek) both consume the *same* segments, so section N always means the
same span of text — and because the split covers the text exactly once with no
gaps or overlaps, an audiobook read section-by-section plays the whole book in
order, with nothing repeated and nothing skipped.

The split is deterministic: given the same ``text`` and ``chapter_map`` it always
produces the same segments. Timestamps are intentionally *not* assigned here — in
the local-first player each section is its own audio clip, so the browser knows
each section's real duration natively; the server only decides *what* the
sections are.
"""

from __future__ import annotations

import re
import os
import json
from collections import Counter
from typing import Any

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None


STOPWORDS = {
    "about", "after", "again", "all", "also", "and", "are", "because", "been",
    "before", "being", "between", "both", "but", "came", "can", "could", "did",
    "does", "doing", "during", "each", "from", "get", "got", "had", "has",
    "have", "having", "her", "here", "him", "his", "into", "its", "just",
    "made", "make", "many", "more", "most", "much", "need", "not", "only",
    "our", "out", "over", "said", "same", "she", "should", "some", "such",
    "than", "that", "the", "their", "them", "then", "there", "these", "they",
    "this", "those", "through", "time", "very", "was", "were", "what", "when",
    "where", "which", "who", "will", "with", "would", "your",
}

# Roughly one section per this many words, clamped to [MIN, MAX] sections.
WORDS_PER_SEGMENT = 180
MIN_SEGMENTS = 1
MAX_SEGMENTS = 12
# Heading-based splitting can produce more (real) chapters than the heuristic.
MAX_HEADING_SEGMENTS = 60

# Explicit chapter markers, e.g. "Chapter 3", "CHAPTER IV", "Part Two", "Book One".
_HEADING_RE = re.compile(
    r"^\s*(chapter|part|section|book)\s+"
    r"(\d{1,3}|[ivxlcdm]{1,7}|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    r"nineteen|twenty|thirty|forty|fifty)\b",
    re.IGNORECASE,
)


def tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


def keyword_title(text: str, index: int) -> str:
    """Derive a short, human-readable title from the most frequent keywords."""
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in STOPWORDS and len(token) > 2
    ]
    if not tokens:
        return f"Section {index + 1}"

    ordered: list[str] = []
    for token, _count in Counter(tokens).most_common():
        if token not in ordered:
            ordered.append(token)
        if len(ordered) == 4:
            break

    return " ".join(word.capitalize() for word in ordered) or f"Section {index + 1}"


def choose_segment_count(word_count: int, requested: int | None = None) -> int:
    if requested and requested > 0:
        return max(MIN_SEGMENTS, min(MAX_SEGMENTS, requested))
    if word_count <= 0:
        return MIN_SEGMENTS
    estimated = max(MIN_SEGMENTS, word_count // WORDS_PER_SEGMENT)
    return max(MIN_SEGMENTS, min(MAX_SEGMENTS, estimated))


def _balanced_word_ranges(word_count: int, segment_count: int) -> list[tuple[int, int]]:
    """Split ``word_count`` words into ``segment_count`` contiguous, near-equal ranges."""
    if word_count <= 0 or segment_count <= 0:
        return []

    segment_count = min(segment_count, word_count)
    base = word_count // segment_count
    remainder = word_count % segment_count

    ranges: list[tuple[int, int]] = []
    start = 0
    for index in range(segment_count):
        # Distribute the remainder across the first few sections so lengths differ
        # by at most one word.
        length = base + (1 if index < remainder else 0)
        end = start + length
        ranges.append((start, end))
        start = end
    return ranges


def _norm_token(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", word.lower())


def _find_subsequence(haystack: list[str], needle: list[str], start: int = 0) -> int | None:
    length = len(needle)
    if length == 0:
        return None
    for index in range(max(0, start), len(haystack) - length + 1):
        if haystack[index : index + length] == needle:
            return index
    return None


def segments_from_anchors(text: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cut the document at AI-provided chapter start anchors (real boundaries).

    Each ``entry`` may carry ``start_text`` — a short verbatim excerpt the model
    copied from where that chapter begins. We locate it in the actual text and
    cut there, so the sections match what the model actually identified rather
    than an even split. Returns ``[]`` when fewer than two anchors can be located
    (caller then falls back to an even split or the heading heuristic).
    """
    cleaned = (text or "").strip()
    words = cleaned.split()
    if not words or not entries:
        return []

    normalized = [_norm_token(word) for word in words]

    located: list[tuple[int, dict[str, Any]]] = []
    search_from = 0
    for entry in entries:
        anchor = str(entry.get("start_text") or "").strip() or str(entry.get("title") or "").strip()
        anchor_tokens = [token for token in (_norm_token(part) for part in anchor.split()) if token][:6]
        if len(anchor_tokens) < 2:
            continue
        index = _find_subsequence(normalized, anchor_tokens, search_from)
        if index is None:
            continue
        located.append((index, entry))
        search_from = index + 1

    if len(located) < 2:
        return []

    # Any text before the first located anchor: keep as its own intro if it is
    # substantial, otherwise fold it into the first chapter.
    ranges: list[tuple[int, int, dict[str, Any]]] = []
    first_index = located[0][0]
    if first_index >= 15:
        ranges.append((0, first_index, {"title": "Introduction", "aliases": [], "confidence": 0.6}))
    elif first_index > 0:
        located[0] = (0, located[0][1])

    for order, (start_index, entry) in enumerate(located):
        end_index = located[order + 1][0] if order + 1 < len(located) else len(words)
        ranges.append((start_index, end_index, entry))

    segments: list[dict[str, Any]] = []
    for order, (start_index, end_index, entry) in enumerate(sorted(ranges, key=lambda item: item[0])):
        chunk_text = " ".join(words[start_index:end_index]).strip()
        if not chunk_text:
            continue

        title = str(entry.get("title") or "").strip() or keyword_title(chunk_text, order)
        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = []
        aliases = [str(alias).strip() for alias in aliases if str(alias).strip()]

        segment: dict[str, Any] = {
            "index": order,
            "title": title[:120],
            "text": chunk_text,
            "excerpt": chunk_text[:280],
            "aliases": aliases[:6],
        }
        if entry.get("confidence") is not None:
            segment["confidence"] = float(entry["confidence"])
        segments.append(segment)

    return segments


def _is_heading_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped.split()) > 12:
        return False
    return bool(_HEADING_RE.match(stripped))


def _heading_segments(cleaned: str) -> list[dict[str, Any]] | None:
    """Split on explicit chapter/part/section headings when the book has them.

    Returns ``None`` when fewer than two headings are found, so the caller can
    fall back to balanced word chunks. The heading line stays in the section
    text (nice to hear a chapter announced) and also becomes the title, so the
    concatenated sections still reproduce the whole document.
    """
    lines = cleaned.split("\n")
    heading_indices = [index for index, line in enumerate(lines) if _is_heading_line(line)]
    if len(heading_indices) < 2 or len(heading_indices) > MAX_HEADING_SEGMENTS:
        return None

    # Boundaries: any text before the first heading becomes an intro section.
    boundaries = heading_indices[:]
    if boundaries[0] != 0:
        boundaries.insert(0, 0)

    segments: list[dict[str, Any]] = []
    for order, start_line in enumerate(boundaries):
        end_line = boundaries[order + 1] if order + 1 < len(boundaries) else len(lines)
        block = "\n".join(lines[start_line:end_line])
        block_text = re.sub(r"\s+", " ", block).strip()
        if not block_text:
            continue

        if _is_heading_line(lines[start_line]):
            title = lines[start_line].strip()[:120]
        else:
            title = "Introduction"

        segments.append(
            {
                "index": len(segments),
                "title": title,
                "text": block_text,
                "excerpt": block_text[:280],
                "aliases": [],
            }
        )

    return segments or None


def generate_chapter_map_with_ai(text: str) -> list[dict[str, Any]] | None:
    """Use Google Gemini to detect chapter boundaries and generate a chapter map."""
    if not genai:
        print("google-genai is not installed, skipping AI segmentation.")
        return None
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is not set, skipping AI segmentation.")
        return None

    try:
        client = genai.Client(api_key=api_key)
        prompt = (
            "You are an expert at text segmentation and document analysis. "
            "Your task is to identify the logical chapters, sections, or general segments in the following book/document text. "
            "For each chapter or segment, provide a fitting 'title', and the exact 'start_text' snippet where it begins. "
            "The 'start_text' must be a verbatim excerpt (approx 4-10 words) from the actual text where the chapter starts. "
            "Return the output as a JSON list of objects, where each object has 'title' and 'start_text' string fields."
        )
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, text],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        data = response.text
        if data:
            chapters = json.loads(data)
            if isinstance(chapters, list):
                return chapters
    except Exception as e:
        print(f"Error during AI segmentation: {e}")
        
    return None


def build_segments(text: str, chapter_map: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Split ``text`` into the canonical ordered sections.

    If ``chapter_map`` is provided its length fixes the number of sections and
    its titles/aliases are reused, so re-running after chapter detection keeps
    the same structure. Otherwise a word-count heuristic chooses the count and
    titles are generated from keywords.

    Returned sections carry ``index``, ``title``, ``text``, ``excerpt`` and
    ``aliases``. Concatenating the sections' text in order reproduces the input
    exactly (no gaps, no overlaps).
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    words = cleaned.split()
    if not words:
        return []

    chapters = list(chapter_map or [])

    if not chapters:
        # Try AI segmentation first
        ai_chapters = generate_chapter_map_with_ai(cleaned)
        if ai_chapters:
            ai_segments = segments_from_anchors(cleaned, ai_chapters)
            if ai_segments:
                return ai_segments

        # Fallback to heading-based heuristic
        heading_based = _heading_segments(cleaned)
        if heading_based:
            return heading_based

    segment_count = choose_segment_count(len(words), requested=len(chapters) or None)
    ranges = _balanced_word_ranges(len(words), segment_count)

    segments: list[dict[str, Any]] = []
    for index, (start, end) in enumerate(ranges):
        chunk_text = " ".join(words[start:end]).strip()
        if not chunk_text:
            continue

        chapter = chapters[index] if index < len(chapters) else {}
        title = str(chapter.get("title") or "").strip() or keyword_title(chunk_text, index)
        aliases = chapter.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = []
        aliases = [str(alias).strip() for alias in aliases if str(alias).strip()]

        segments.append(
            {
                "index": index,
                "title": title[:120],
                "text": chunk_text,
                "excerpt": chunk_text[:280],
                "aliases": aliases[:6],
            }
        )

    return segments
