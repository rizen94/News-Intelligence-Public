"""
Strip common LLM output noise (JSON fences, echoed keys) from strings shown as headlines or ledes.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional


def strip_llm_wrapping_artifacts(text: Optional[str], *, max_length: Optional[int] = None) -> str:
    """
    Remove markdown code fences, extract plain string from a lone JSON object when the model
    returns structured output in a field we display as prose, and drop obvious JSON key echoes.
    """
    if text is None:
        return ""
    s = str(text).strip()
    if not s:
        return ""

    # Fenced blocks ```json ... ```
    if s.startswith("```"):
        parts = s.split("\n", 1)
        if len(parts) > 1:
            s = parts[1]
        if "```" in s:
            s = s.rsplit("```", 1)[0].strip()

    # Whole value is JSON with a single narrative field
    if s.startswith("{") and s.endswith("}"):
        try:
            obj: Any = json.loads(s)
            if isinstance(obj, dict):
                for key in ("lede", "headline", "summary", "title", "text", "content"):
                    v = obj.get(key)
                    if isinstance(v, str) and v.strip():
                        s = v.strip()
                        break
                else:
                    # Avoid dumping raw dict into UI
                    s = ""
        except json.JSONDecodeError:
            pass

    # Line-by-line: drop lines that look like JSON key declarations or opening braces only
    lines_out: list[str] = []
    for line in s.split("\n"):
        t = line.strip()
        if not t:
            lines_out.append(line)
            continue
        if t in ("{", "}", "[", "]"):
            continue
        if re.match(r'^["\']?(lede|headline|summary|title|who|what|when|where)["\']?\s*:', t, re.I):
            continue
        if re.match(r"^[\{\[]\s*\"", t):
            continue
        lines_out.append(line)
    s = "\n".join(lines_out).strip()

    # Trailing JSON junk
    s = re.sub(r"\s*[\}\]]+\s*$", "", s).strip()

    # Collapse repeated whitespace for single-line headlines
    if "\n" not in s:
        s = re.sub(r"\s+", " ", s).strip()

    if max_length is not None and len(s) > max_length:
        s = s[: max_length - 1].rsplit(" ", 1)[0] + "…" if " " in s[:max_length] else s[:max_length]

    return s
