"""
Semantic article → context chunking for long-form intake.
"""

from __future__ import annotations

import logging
import re

from config.settings import (
    context_chunk_max_chunks,
    context_chunk_min_chars,
    context_chunk_overlap_tokens,
    context_chunk_size_tokens,
    context_chunking_enabled,
)

logger = logging.getLogger(__name__)


def _split_by_paragraphs(text: str, *, max_chars: int, overlap: int) -> list[str]:
    """Fallback when semantic-text-splitter is unavailable."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paras:
        paras = [text.strip()] if text.strip() else []
    chunks: list[str] = []
    buf = ""
    for para in paras:
        if len(buf) + len(para) + 2 <= max_chars:
            buf = f"{buf}\n\n{para}".strip() if buf else para
            continue
        if buf:
            chunks.append(buf)
        if len(para) <= max_chars:
            buf = para
            continue
        start = 0
        while start < len(para):
            end = min(len(para), start + max_chars)
            chunks.append(para[start:end])
            if end >= len(para):
                break
            start = max(start + 1, end - overlap)
        buf = ""
    if buf:
        chunks.append(buf)
    return chunks


def split_article_into_context_chunks(title: str, content: str) -> list[tuple[str, str]]:
    """
    Return (chunk_title, chunk_content) rows for context creation.
    Single chunk when below threshold or chunking disabled.
    """
    body = (content or "").strip()
    if not context_chunking_enabled() or len(body) < context_chunk_min_chars():
        return [(title or "", body)]

    max_chunks = context_chunk_max_chunks()
    try:
        from semantic_text_splitter import TextSplitter

        splitter = TextSplitter.from_tiktoken_model(
            "gpt-3.5-turbo",
            context_chunk_size_tokens(),
            overlap=context_chunk_overlap_tokens(),
        )
        pieces = splitter.chunks(body)
        pieces = [p.strip() for p in pieces if p and p.strip()]
    except Exception as e:
        logger.debug("semantic-text-splitter fallback: %s", e)
        approx_chars = max(2000, context_chunk_size_tokens() * 4)
        pieces = _split_by_paragraphs(
            body,
            max_chars=approx_chars,
            overlap=max(200, context_chunk_overlap_tokens() * 4),
        )

    if not pieces:
        return [(title or "", body)]
    if len(pieces) == 1:
        return [(title or "", pieces[0])]

    pieces = pieces[:max_chunks]
    out: list[tuple[str, str]] = []
    total = len(pieces)
    base_title = (title or "Article")[:1800]
    for idx, piece in enumerate(pieces):
        chunk_title = f"{base_title} [{idx + 1}/{total}]" if total > 1 else base_title
        out.append((chunk_title, piece[:500000]))
    return out
