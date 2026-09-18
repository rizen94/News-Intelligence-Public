#!/usr/bin/env python3
"""
CI: every ``/api/...`` path the SPA calls must exist in the FastAPI routing table.

Compares each ``/api/...`` string literal under ``web/src`` against ``main.app.routes``. Catches the
failure mode where a service, a router, and a page are each built but land on different path shapes,
so the page 404s in production with nothing failing loudly.

Known-unwired calls live in ``KNOWN_GAPS`` with the reason. Wire the route (or drop the call) and
remove the entry — a stale entry is reported as an error so the list cannot rot.

    PYTHONPATH=api python3 scripts/verify_frontend_route_wiring.py [--list]

Exit 0 when every literal resolves or is a known gap; 1 otherwise.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api"
WEB_SRC = ROOT / "web" / "src"
sys.path.insert(0, str(API))

# path -> why it has no route yet. Keep the reason specific enough to act on.
KNOWN_GAPS: dict[str, str] = {
    "/api/intelligence/matter_dockets/*": (
        "matter_docket_ledger_service.py exists and MatterDocketPage is routed, but no route was "
        "ever mounted. Wiring it means editing intelligence_hub/routes/__init__.py."
    ),
    "/api/intelligence/research_subjects": (
        "Research-subject services exist and ResearchSubjectPage is routed; route never mounted. "
        "Overlaps in-flight research work in intelligence_hub/routes."
    ),
}

_LITERAL = re.compile(r"""["'`](/api/[^"'`\s)]*)""")
_TEMPLATE_EXPR = re.compile(r"\$\{[^}]*\}")
_PATH_PARAM = re.compile(r"\{[^}]*\}")
_SOURCE_SUFFIXES = (".ts", ".tsx", ".js", ".jsx")


def _iter_source_files() -> list[Path]:
    return sorted(
        p
        for p in WEB_SRC.rglob("*")
        if p.suffix in _SOURCE_SUFFIXES and "node_modules" not in p.parts
    )


def normalize(path: str) -> str | None:
    """
    Reduce a literal or route path to comparable form: ``*`` per variable segment.

    Returns None for what cannot be compared: bare ``/api`` and doc prose.
    """
    out = _PATH_PARAM.sub("*", _TEMPLATE_EXPR.sub("*", path.split("?")[0]))
    out = re.sub(r"/+", "/", out).rstrip("/")
    if out in ("", "/api") or "..." in out:
        return None
    return out


def normalize_call(literal: str) -> tuple[str, bool] | None:
    """
    Normalise a frontend literal, returning ``(path, prefix_only)``.

    ``prefix_only`` is True when the literal cannot be compared end to end and only its leading
    segments are trustworthy. Two cases:

    * the extracting regex cut a template literal mid-expression, e.g.
      ``/api/x/${encodeURIComponent(y`` — the real path continues past the cut;
    * a template expression is glued to the final segment rather than forming its own segment, e.g.
      ``.../reject${params}``, which is a query string, not a path segment.

    Comparing those as complete paths is what previously produced both false positives and false
    negatives, so they are matched as prefixes instead.
    """
    raw = literal.split("?")[0]
    truncated = bool(_TEMPLATE_EXPR.sub("", raw).count("${"))
    if truncated:
        raw = raw[: raw.rfind("${")]
    glued = bool(re.search(r"[^/]\$\{[^}]*\}$", raw))

    norm = normalize(raw)
    if not norm:
        return None
    if truncated or glued:
        norm = norm.rstrip("*")
        norm = norm.rstrip("/") or "/api"
        if norm == "/api":
            return None
        return norm, True
    return norm, False


def collect_frontend_calls() -> dict[tuple[str, bool], set[str]]:
    calls: dict[tuple[str, bool], set[str]] = defaultdict(set)
    for path in _iter_source_files():
        rel = path.relative_to(ROOT)
        for line_no, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            for match in _LITERAL.finditer(line):
                parsed = normalize_call(match.group(1))
                if parsed:
                    calls[parsed].add(f"{rel}:{line_no}")
    return calls


def collect_routes() -> set[str]:
    logging.disable(logging.CRITICAL)
    import main  # noqa: PLC0415 — importing the app is the point

    routes = set()
    for route in main.app.routes:
        norm = normalize(getattr(route, "path", "") or "")
        if norm and norm.startswith("/api"):
            routes.add(norm)
    return routes


def _segments_match(call_parts: list[str], route_parts: list[str]) -> bool:
    return all(c == r or c == "*" or r == "*" for c, r in zip(call_parts, route_parts, strict=True))


def resolves(call: str, prefix_only: bool, routes: set[str]) -> bool:
    if not prefix_only and call in routes:
        return True
    call_parts = call.split("/")
    for route in routes:
        route_parts = route.split("/")
        if prefix_only:
            if len(route_parts) < len(call_parts):
                continue
            if _segments_match(call_parts, route_parts[: len(call_parts)]):
                return True
            continue
        if len(call_parts) != len(route_parts):
            continue
        if _segments_match(call_parts, route_parts):
            return True
    return False


def main_cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="print every resolved call too")
    args = parser.parse_args()

    calls = collect_frontend_calls()
    routes = collect_routes()

    unresolved: dict[str, set[str]] = {}
    for (call, prefix_only), where in sorted(calls.items()):
        if resolves(call, prefix_only, routes):
            if args.list:
                print(f"ok    {call}{'/*' if prefix_only else ''}")
            continue
        unresolved[call] = where

    errors: list[str] = []
    for call, where in unresolved.items():
        if call in KNOWN_GAPS:
            print(f"known {call}\n        {KNOWN_GAPS[call]}\n        called from: {sorted(where)[0]}")
            continue
        errors.append(
            f"{call} has no backend route; called from {', '.join(sorted(where)[:3])}"
        )

    for stale in sorted(set(KNOWN_GAPS) - set(unresolved)):
        errors.append(
            f"{stale} is listed in KNOWN_GAPS but now resolves (or is no longer called) — "
            "remove the entry"
        )

    print(
        f"\nfrontend /api literals: {len(calls)}   routes: {len(routes)}   "
        f"unresolved: {len(unresolved)}   known gaps: {len(KNOWN_GAPS)}"
    )
    if errors:
        print("\nFrontend route wiring errors:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("Frontend route wiring OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
