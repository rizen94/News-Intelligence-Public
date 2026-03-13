#!/usr/bin/env bash
# Run Docker status + Pi-hole summary and write a single dated file for later review.
# Usage: ./scripts/pi_summary_doc.sh [user@host]
# Output: scripts/pi_reports/pi_summary_YYYY-MM-DD_HH-MM.txt (create dir if needed)

set -e
TARGET="${1:-petes@192.168.93.104}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_DIR="${SCRIPT_DIR}/pi_reports"
STAMP="$(date +%Y-%m-%d_%H-%M)"
OUTFILE="${REPORT_DIR}/pi_summary_${STAMP}.txt"

mkdir -p "$REPORT_DIR"

{
  echo "################################################################################"
  echo "# Pi monitoring summary — $TARGET"
  echo "# Generated: $(date -Iseconds)"
  echo "# Review this to improve Pi-hole efficiency and track Docker/container health."
  echo "################################################################################"
  echo ""

  "$SCRIPT_DIR/pi_docker_status.sh" "$TARGET"

  echo ""
  echo ""

  "$SCRIPT_DIR/pi_pihole_summary.sh" "$TARGET"

  echo ""
  echo "################################################################################"
  echo "# End of summary"
  echo "################################################################################"
} | tee "$OUTFILE"

echo ""
echo "Summary written to: $OUTFILE"
