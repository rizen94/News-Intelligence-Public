#!/usr/bin/env bash
set -euo pipefail

TARGET="api/services/article_entity_extraction_service.py"

if [[ ! -f "$TARGET" ]]; then
    echo "ERROR: $TARGET not found"
    exit 1
fi

BACKUP="${TARGET}.bak.$(date +%Y%m%d_%H%M%S)"
cp "$TARGET" "$BACKUP"
echo "Backup: $BACKUP"

python3 << 'PYEOF'
import sys

path = "api/services/article_entity_extraction_service.py"
with open(path, "r") as f:
    content = f.read()

original = content
fixes = []

if '    "united arab emirates": "AE",\n}\n\n}\n' in content:
    content = content.replace(
        '    "united arab emirates": "AE",\n}\n\n}\n',
        '    "united arab emirates": "AE",\n}\n\n',
    )
    fixes.append("Removed stray duplicate } after COUNTRY_ALIASES")

if "class ArticleEntityExtractionService:\nclass ArticleEntityExtractionService:" in content:
    content = content.replace(
        "class ArticleEntityExtractionService:\nclass ArticleEntityExtractionService:",
        "class ArticleEntityExtractionService:",
    )
    fixes.append("Removed duplicate class definition line")

old_check = '    if n.startswith("none ") or n.startswith("no ") or n.startswith("not "):\n        return True'
new_check = '''    if n.startswith("none ") or n.startswith("not "):
        return True
    NO_GARBAGE_PHRASES = ("no results", "no data", "no information", "no details",
                          "no name", "no names", "no persons", "no organizations")
    if n in NO_GARBAGE_PHRASES:
        return True'''
if old_check in content:
    content = content.replace(old_check, new_check)
    fixes.append("Replaced broad startswith('no ') with targeted phrases")

if content == original:
    print("No changes needed")
    sys.exit(0)

with open(path, "w") as f:
    f.write(content)

for i, fix in enumerate(fixes, 1):
    print(f"  {i}. {fix}")
print(f"Applied {len(fixes)} fix(es)")
PYEOF

echo ""
python3 -c "import ast; ast.parse(open('$TARGET').read()); print('Syntax OK')"
