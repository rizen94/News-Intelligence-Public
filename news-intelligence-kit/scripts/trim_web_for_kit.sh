#!/usr/bin/env bash
# Apply kit frontend patches before npm run build (run from repo root)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WEB="$ROOT/web"

[[ -d "$WEB/src" ]] || { echo "web/src missing"; exit 1; }

python3 << PY
from pathlib import Path
p = Path("$WEB/src/utils/domainHelper.ts")
text = p.read_text(encoding="utf-8")
old = """const FALLBACK_DOMAINS: Domain[] = [
  { key: 'politics', name: 'Politics', schema: 'politics' },
  { key: 'finance', name: 'Finance', schema: 'finance' },
  { key: 'artificial-intelligence', name: 'Artificial Intelligence', schema: 'artificial_intelligence' },
  { key: 'medicine', name: 'Medicine', schema: 'medicine' },
  { key: 'legal', name: 'Legal', schema: 'legal' },
];"""
new = "const FALLBACK_DOMAINS: Domain[] = [];"
if old in text:
    p.write_text(text.replace(old, new), encoding="utf-8")
    print("domainHelper: cleared FALLBACK_DOMAINS")
else:
    print("domainHelper: already patched or pattern changed")
PY

echo "trim_web_for_kit: run 'cd web && npm run build' then rebuild intake-web image"
