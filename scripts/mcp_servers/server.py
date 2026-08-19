"""
Obsidian vault MCP (SSE): read/write markdown notes under VAULT_ROOT.
Exposed via SSE for remote MCP clients.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from mcp.server import Server
from mcp.types import TextContent, Tool
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import Response
import uvicorn

_vault_raw = os.environ.get("OBSIDIAN_VAULT_PATH", "").strip()
VAULT_ROOT = Path(_vault_raw).resolve() if _vault_raw else Path("")
MAX_BYTES = int(os.environ.get("OBSIDIAN_MAX_FILE_BYTES", "512000"))
MAX_MATCHES = int(os.environ.get("OBSIDIAN_SEARCH_MAX_MATCHES", "40"))
WRITE_ENABLED = os.environ.get("OBSIDIAN_WRITE_ENABLED", "true").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)
_BLOCKED_PREFIXES = (".obsidian", ".git", ".trash", ".attachments")

server = Server("obsidian-vault-mcp")
sse = SseServerTransport("/messages/")


def _under_vault(path: Path) -> bool:
    try:
        path.resolve().relative_to(VAULT_ROOT)
        return True
    except ValueError:
        return False


def _safe_join(relative: str) -> Path:
    rel = (relative or "").strip().lstrip("/")
    candidate = (VAULT_ROOT / rel).resolve()
    if not _under_vault(candidate):
        raise ValueError("Path escapes vault root")
    return candidate


def _assert_writable_relative(relative: str) -> Path:
    if not WRITE_ENABLED:
        raise ValueError("Obsidian vault writes are disabled (OBSIDIAN_WRITE_ENABLED=false)")
    rel = (relative or "").strip().lstrip("/")
    if not rel:
        raise ValueError("relative_path is required")
    if not rel.lower().endswith(".md"):
        raise ValueError("Only .md files may be written")
    parts = Path(rel).parts
    for part in parts:
        if part.startswith("."):
            raise ValueError(f"Hidden path segments are not writable: {part}")
    for blocked in _BLOCKED_PREFIXES:
        if rel == blocked or rel.startswith(f"{blocked}/"):
            raise ValueError(f"Path is not writable: {blocked}")
    return _safe_join(rel)


def _write_guard(content: str) -> None:
    if len(content.encode("utf-8")) > MAX_BYTES:
        raise ValueError(f"Content exceeds OBSIDIAN_MAX_FILE_BYTES ({MAX_BYTES})")


def _parse_ymd(value: str) -> date:
    return date.fromisoformat(value.strip()[:10])


def _mtime_on_local_day(path: Path, day: date) -> bool:
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return mtime.date() == day


def _files_for_day(base: Path, day: date, max_files: int) -> list[dict]:
    rows: list[dict] = []
    for p in base.rglob("*.md"):
        if not _under_vault(p):
            continue
        try:
            if not _mtime_on_local_day(p, day):
                continue
        except OSError:
            continue
        mtime = datetime.fromtimestamp(p.stat().st_mtime)
        rows.append(_file_row(p, mtime))
        if len(rows) >= max_files:
            break
    rows.sort(key=lambda r: r["modified_at"], reverse=True)
    return rows


def _file_row(path: Path, mtime: datetime) -> dict:
    return {
        "path": str(path.relative_to(VAULT_ROOT)),
        "modified_at": mtime.isoformat(timespec="seconds"),
        "size_bytes": path.stat().st_size,
    }


def _files_recent(base: Path, days: int, max_files: int) -> list[dict]:
    if days < 1:
        days = 1
    today = date.today()
    since = today - timedelta(days=days - 1)
    rows: list[dict] = []
    for p in base.rglob("*.md"):
        if not _under_vault(p):
            continue
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
            mday = mtime.date()
        except OSError:
            continue
        if mday < since or mday > today:
            continue
        rows.append(_file_row(p, mtime))
    rows.sort(key=lambda r: r["modified_at"], reverse=True)
    return rows[:max_files]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="vault_resolve_path",
            description="Return whether OBSIDIAN_VAULT_PATH is set and the resolved absolute path. Call first if unsure the server is configured.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="vault_list_markdown",
            description="List markdown files (.md) recursively under a relative folder within the vault (default: vault root).",
            inputSchema={
                "type": "object",
                "properties": {
                    "relative_dir": {
                        "type": "string",
                        "description": "Subfolder relative to vault root; empty for entire vault.",
                    },
                    "max_files": {
                        "type": "integer",
                        "description": "Stop after this many files (default 200).",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="vault_read_note",
            description="Read a markdown file from the vault by path relative to vault root.",
            inputSchema={
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "Path under the vault, e.g. Projects/HomeLab/README.md",
                    }
                },
                "required": ["relative_path"],
            },
        ),
        Tool(
            name="vault_search_text",
            description="Simple case-insensitive substring search across .md files (first max_matches snippets).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text to search for."},
                    "relative_dir": {
                        "type": "string",
                        "description": "Optional subfolder to limit search.",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="vault_list_by_date",
            description=(
                "List markdown files modified on a calendar day (local filesystem mtime). "
                "Use for questions like 'what did I write last Monday?' — compute the ISO date "
                "first (e.g. 2026-05-11), then call this tool. Does not search note body text."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "on_date": {
                        "type": "string",
                        "description": "Calendar day YYYY-MM-DD (local mtime).",
                    },
                    "relative_dir": {
                        "type": "string",
                        "description": "Optional subfolder under vault root.",
                    },
                    "max_files": {
                        "type": "integer",
                        "description": "Max files to return (default 100).",
                    },
                },
                "required": ["on_date"],
            },
        ),
        Tool(
            name="vault_list_recent",
            description=(
                "List markdown files modified in the last N calendar days (local mtime, inclusive). "
                "Use days=7 for 'last week', days=1 for 'today/yesterday' style windows when exact "
                "dates are uncertain. Then vault_read_note on paths of interest."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "How many calendar days back from today to include (default 7).",
                    },
                    "relative_dir": {
                        "type": "string",
                        "description": "Optional subfolder under vault root.",
                    },
                    "max_files": {
                        "type": "integer",
                        "description": "Max files to return (default 100).",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="vault_write_note",
            description=(
                "Create or replace a markdown note in the vault. Use for daily notes, ideation, "
                "narratives, homebrew, and session prep — not for distilled code facts (use MemPalace). "
                "Prefer 00_Inbox/, 40_Reference/, or user-named folders; .md only."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "Path under vault root, e.g. 00_Inbox/idea-spark.md",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full markdown body (include YAML frontmatter if desired).",
                    },
                    "if_exists": {
                        "type": "string",
                        "enum": ["overwrite", "fail"],
                        "description": "overwrite (default) replaces existing file; fail errors if present.",
                    },
                },
                "required": ["relative_path", "content"],
            },
        ),
        Tool(
            name="vault_append_note",
            description=(
                "Append markdown to an existing note, or create it if missing. "
                "Good for daily logs, running ideation threads, and incremental session notes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "Path under vault root, e.g. 00_Inbox/daily/2026-06-13.md",
                    },
                    "content": {
                        "type": "string",
                        "description": "Markdown chunk to append.",
                    },
                    "separator": {
                        "type": "string",
                        "description": "Inserted between existing body and new content (default blank line).",
                    },
                },
                "required": ["relative_path", "content"],
            },
        ),
        Tool(
            name="vault_delete_note",
            description=(
                "Delete a markdown note from the vault. Use when a draft or thread is wrong or abandoned "
                "so you do not leave stale conclusions. Prefer vault_write_note with if_exists=overwrite "
                "for corrections; delete for retracted or mistaken notes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "Path under vault root, e.g. 20_Investigations/foo/thread.md",
                    }
                },
                "required": ["relative_path"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if not _vault_raw:
        return [
            TextContent(
                type="text",
                text="OBSIDIAN_VAULT_PATH is not set. Set it in the environment and restart.",
            )
        ]

    if name == "vault_resolve_path":
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"vault_root": str(VAULT_ROOT), "exists": VAULT_ROOT.exists()}, indent=2
                ),
            )
        ]

    if name == "vault_list_markdown":
        relative_dir = arguments.get("relative_dir", "")
        max_files = arguments.get("max_files", 200)
        base = _safe_join(relative_dir) if relative_dir else VAULT_ROOT
        files = [str(p.relative_to(VAULT_ROOT)) for p in base.rglob("*.md") if _under_vault(p)]
        return [TextContent(type="text", text=json.dumps(files[:max_files], indent=2))]

    if name == "vault_read_note":
        path = _safe_join(arguments["relative_path"])
        if not path.exists():
            return [TextContent(type="text", text=f"File not found: {arguments['relative_path']}")]
        if path.stat().st_size > MAX_BYTES:
            return [
                TextContent(
                    type="text",
                    text=f"File exceeds OBSIDIAN_MAX_FILE_BYTES ({MAX_BYTES})",
                )
            ]
        content = path.read_text(encoding="utf-8")
        return [TextContent(type="text", text=content)]

    if name == "vault_search_text":
        query = arguments["query"].lower()
        relative_dir = arguments.get("relative_dir", "")
        base = _safe_join(relative_dir) if relative_dir else VAULT_ROOT
        results = []
        for p in base.rglob("*.md"):
            if not _under_vault(p):
                continue
            try:
                content = p.read_text(encoding="utf-8")
            except OSError:
                continue
            if query in content.lower():
                idx = content.lower().index(query)
                start = max(0, idx - 100)
                end = min(len(content), idx + len(query) + 100)
                snippet = content[start:end]
                results.append({"path": str(p.relative_to(VAULT_ROOT)), "snippet": snippet})
                if len(results) >= MAX_MATCHES:
                    break
        return [TextContent(type="text", text=json.dumps(results, indent=2))]

    if name == "vault_list_by_date":
        on_date = _parse_ymd(arguments["on_date"])
        relative_dir = arguments.get("relative_dir", "")
        max_files = arguments.get("max_files", 100)
        base = _safe_join(relative_dir) if relative_dir else VAULT_ROOT
        files = _files_for_day(base, on_date, max_files)
        return [TextContent(type="text", text=json.dumps(files, indent=2))]

    if name == "vault_list_recent":
        days = arguments.get("days", 7)
        relative_dir = arguments.get("relative_dir", "")
        max_files = arguments.get("max_files", 100)
        base = _safe_join(relative_dir) if relative_dir else VAULT_ROOT
        files = _files_recent(base, days, max_files)
        return [TextContent(type="text", text=json.dumps(files, indent=2))]

    if name == "vault_write_note":
        path = _assert_writable_relative(arguments["relative_path"])
        content = arguments["content"]
        if_exists = arguments.get("if_exists", "overwrite")
        _write_guard(content)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and if_exists == "fail":
            return [TextContent(type="text", text=f"File exists: {arguments['relative_path']}")]
        path.write_text(content, encoding="utf-8")
        return [TextContent(type="text", text=f"Written: {arguments['relative_path']}")]

    if name == "vault_append_note":
        path = _assert_writable_relative(arguments["relative_path"])
        content = arguments["content"]
        separator = arguments.get("separator", "\n\n")
        _write_guard(content)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        new_content = existing + separator + content if existing else content
        path.write_text(new_content, encoding="utf-8")
        return [TextContent(type="text", text=f"Appended to: {arguments['relative_path']}")]

    if name == "vault_delete_note":
        path = _safe_join(arguments["relative_path"])
        if not path.exists():
            return [TextContent(type="text", text=f"File not found: {arguments['relative_path']}")]
        path.unlink()
        return [TextContent(type="text", text=f"Deleted: {arguments['relative_path']}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


# Custom SSE endpoint that works with Starlette/FastAPI routing
async def handle_sse(request):
    """Handle SSE connections - returns EventSourceResponse for Starlette compatibility."""
    import logging
    logger = logging.getLogger(__name__)

    # Use the MCP SSE transport directly
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


# Create Starlette app with proper routing
app = Starlette(
    routes=[
        Route("/sse", handle_sse, methods=["GET"]),
        Mount("/messages", app=sse.handle_post_message),
        Mount("/messages/", app=sse.handle_post_message),
    ]
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")