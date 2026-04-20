#!/usr/bin/env python3
"""
Documentation obfuscation helper: expand public <TOKENS> to local values, or scrub
local values to public tokens. Mapping file: configs/doc_obfuscation.local.yaml
(copy from configs/doc_obfuscation.example.yaml). The local file is gitignored.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        print("PyYAML required: uv add pyyaml", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _ordered_pairs(data: dict) -> list[tuple[str, str]]:
    subs = data.get("substitutions") or []
    pairs: list[tuple[str, str]] = []
    for item in subs:
        pub = item.get("public")
        priv = item.get("private")
        if pub and priv:
            pairs.append((str(pub), str(priv)))
    # Longest private first (avoid replacing substrings of another address)
    pairs.sort(key=lambda x: len(x[1]), reverse=True)
    return pairs


def expand_text(text: str, pairs: list[tuple[str, str]]) -> str:
    for public, private in pairs:
        text = text.replace(public, private)
    return text


def scrub_text(text: str, pairs: list[tuple[str, str]]) -> str:
    for public, private in pairs:
        text = text.replace(private, public)
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description="Doc obfuscation expand/scrub")
    ap.add_argument(
        "command",
        choices=("expand", "scrub"),
        help="expand: public→private; scrub: private→public",
    )
    ap.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "doc_obfuscation.local.yaml",
        help="Path to local mapping (default: configs/doc_obfuscation.local.yaml)",
    )
    ap.add_argument(
        "--paths",
        nargs="*",
        default=["docs", "AGENTS.md", "QUICK_START.md"],
        help="Files or directories to process (for expand)",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=PROJECT_ROOT / "docs" / "_local_expanded",
        help="Output directory for expand (default: docs/_local_expanded)",
    )
    ap.add_argument("--in", dest="in_path", type=Path, help="Single input file (scrub)")
    ap.add_argument("--out", dest="out_path", type=Path, help="Single output file (scrub)")
    args = ap.parse_args()

    cfg_path = args.config
    if not cfg_path.is_file():
        print(
            f"Missing {cfg_path}. Copy configs/doc_obfuscation.example.yaml and set private values.",
            file=sys.stderr,
        )
        return 1

    data = _load_yaml(cfg_path)
    pairs = _ordered_pairs(data)
    if not pairs:
        print("No substitutions in config.", file=sys.stderr)
        return 1

    if args.command == "scrub":
        if not args.in_path or not args.out_path:
            print("scrub requires --in and --out", file=sys.stderr)
            return 1
        text = args.in_path.read_text(encoding="utf-8")
        args.out_path.write_text(scrub_text(text, pairs), encoding="utf-8")
        print(f"Wrote {args.out_path}")
        return 0

    # expand
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    def collect_files() -> list[Path]:
        files: list[Path] = []
        for p in args.paths:
            path = Path(p)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            if path.is_file():
                files.append(path)
            elif path.is_dir():
                for ext in (".md", ".mdx"):
                    for f in path.rglob(f"*{ext}"):
                        if "_local_expanded" in f.parts:
                            continue
                        files.append(f)
            else:
                print(f"Skip missing: {path}", file=sys.stderr)
        return sorted(set(files))

    n = 0
    for src in collect_files():
        try:
            rel = src.relative_to(PROJECT_ROOT)
        except ValueError:
            rel = src.name
        dest = out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text(encoding="utf-8")
        dest.write_text(expand_text(text, pairs), encoding="utf-8")
        n += 1
    print(f"Expanded {n} file(s) under {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
