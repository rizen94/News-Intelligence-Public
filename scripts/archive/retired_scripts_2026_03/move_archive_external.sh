#!/usr/bin/env bash
# Move archive/ out of project to free 27GB and reduce file count
# Run from News Intelligence project root

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ARCHIVE_DEST="${ARCHIVE_DEST:-$(dirname "$PROJECT_ROOT")/News-Intelligence-Archive}"

echo "Moving archive from $PROJECT_ROOT/archive to $ARCHIVE_DEST"
echo "This may take several minutes (27GB, 508k files)..."
read -p "Continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

mkdir -p "$ARCHIVE_DEST"
mv "$PROJECT_ROOT/archive" "$ARCHIVE_DEST/archive_$(date +%Y%m%d)"
echo "Done. Archive relocated to $ARCHIVE_DEST"
echo "Add archive/ to .gitignore to prevent re-adding."
