"""Text metrics helpers for articles."""

from __future__ import annotations

import re


def compute_word_count(content: str | None) -> int:
    """Count words in article body text."""
    if not content or not str(content).strip():
        return 0
    return len(re.split(r"\s+", str(content).strip()))


def word_count_sql_expr(content_column: str = "content", word_count_column: str = "word_count") -> str:
    """SQL expression: prefer stored word_count, else compute from content."""
    return f"""CASE
        WHEN {word_count_column} IS NOT NULL AND {word_count_column} > 0 THEN {word_count_column}
        WHEN {content_column} IS NULL OR trim({content_column}) = '' THEN 0
        ELSE cardinality(regexp_split_to_array(trim({content_column}), '\\s+'))
    END"""
