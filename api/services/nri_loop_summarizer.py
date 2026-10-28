"""
NRI Loop Summarizer — generates human-readable session logs and vault index.

Runs after each NRI loop iteration (or on demand) to produce:
- 00_Inbox/nri-loop-summary-YYYYMMDD.md — per-iteration narrative
- 00_Inbox/vault-index.md — consolidated vault inventory
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.runtime import env_bool, env_str
from nri_core.config import get_config
from nri_core.vault.reader.hypothesis_reader import list_hypotheses, get_hypothesis
from services import vault_bridge_service as vault_bridge

logger = logging.getLogger(__name__)


def _vault_root() -> Path:
    root = Path(env_str("NEWS_INTEL_VAULT_PATH", "/mnt/news-intelligence-vault"))
    return root.resolve()


def _inbox_dir() -> Path:
    return _vault_root() / "00_Inbox"


def generate_loop_summary(
    iteration: int,
    *,
    entities: list[str],
    metrics: dict[str, int],
    hypotheses_written: int,
    skeptic_findings: list[dict[str, Any]],
    vault_coverage: dict[str, set[str]] | None = None,
) -> str:
    """Generate markdown summary for a single loop iteration."""
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    lines = [
        f"# NRI Loop Summary — Iteration {iteration} ({date_str})",
        "",
        "## Entities Processed",
    ]
    if entities:
        lines.extend([f"- {ftm_id}" for ftm_id in entities])
    else:
        lines.append("  (none)")
    lines.extend([
        "",
        "## Metrics",
        "| Metric | Count |",
        "|--------|-------|",
    ])
    for key in ["added", "killed", "demoted", "dormant"]:
        lines.append(f"| {key.title()} | {metrics.get(key, 0)} |")
    lines.append("")
    lines.append(f"## Hypotheses Written: {hypotheses_written}")
    lines.append("")

    if skeptic_findings:
        lines.append("## Skeptic Review")
        lines.append("| Hypothesis | Confidence Δ | Refuted? | Causal Flags |")
        lines.append("|------------|--------------|----------|--------------|")
        for sf in skeptic_findings:
            hyp = sf.get("hypothesis", "unknown")
            old_conf = sf.get("old_confidence", 0)
            new_conf = sf.get("new_confidence", old_conf)
            delta = round(new_conf - old_conf, 4)
            refuted = "Yes" if sf.get("refuted") else "No"
            flags = ", ".join(sf.get("causal_flags", [])) or "—"
            lines.append(f"| {hyp} | {old_conf} → {new_conf} ({delta:+}) | {refuted} | {flags} |")
        lines.append("")

    if vault_coverage:
        lines.append("## Vault Coverage (Sample)")
        for bucket, items in vault_coverage.items():
            if items:
                lines.append(f"- **{bucket}**: {len(items)} items (sample: {', '.join(list(items)[:5])})")
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated at {datetime.now(timezone.utc).isoformat()}*")
    return "\n".join(lines)


def write_loop_summary(content: str, iteration: int) -> dict[str, Any]:
    """Write iteration summary to vault."""
    if not vault_bridge.vault_write_enabled():
        return {"ok": False, "error": "vault write disabled"}

    inbox = _inbox_dir()
    inbox.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    rel = f"nri-loop-summary-{date_str}-iter{iteration}.md"
    path = inbox / rel

    # Append if exists (multiple iterations same day), else create
    if path.is_file():
        existing = path.read_text(encoding="utf-8")
        content = existing + "\n\n" + content

    path.write_text(content, encoding="utf-8")
    logger.info("Wrote NRI loop summary: %s", path)
    return {"ok": True, "path": rel}


def build_vault_index(
    *,
    hypothesis_limit: int = 200,
    tracking_days: int = 30,
) -> dict[str, Any]:
    """Build consolidated vault index."""
    cfg = get_config()
    vault_path = Path(cfg.vault_path) if cfg.vault_path else _vault_root()

    # --- Hypotheses ---
    hyp_result = list_hypotheses(limit=hypothesis_limit)
    hypotheses = hyp_result.get("items", [])

    hyp_table = []
    for h in hypotheses:
        hyp_table.append({
            "id": h.get("hyp_id"),
            "status": h.get("status", "unknown"),
            "confidence": h.get("confidence"),
            "ftm_id": h.get("subject_ftm_id"),
            "pattern": h.get("claim", "").replace("Pattern ", "").replace(" for ", " | ") if h.get("claim") else "unknown",
            "iteration": h.get("iteration_introduced"),
        })

    # --- Tracking Candidates (last N days) ---
    tracking_files = []
    if vault_path.is_dir():
        inbox = vault_path / "00_Inbox"
        if inbox.is_dir():
            cutoff = datetime.now(timezone.utc).timestamp() - (tracking_days * 86400)
            for f in sorted(inbox.glob("tracking-candidates-*.md"), reverse=True):
                try:
                    mtime = f.stat().st_mtime
                    if mtime >= cutoff:
                        tracking_files.append(f)
                    else:
                        break
                except OSError:
                    continue

    tracking_summary = []
    for f in tracking_files[:3]:
        try:
            text = f.read_text(encoding="utf-8")
            # Parse frontmatter + first table rows
            lines = text.splitlines()
            fm = {}
            in_fm = False
            for line in lines:
                if line.strip() == "---":
                    in_fm = not in_fm
                    continue
                if in_fm and ":" in line:
                    k, _, v = line.partition(":")
                    fm[k.strip()] = v.strip().strip('"').strip("'")

            # Find table rows
            rows = []
            for line in lines:
                if line.startswith("| ") and "Rank" not in line and "---" not in line:
                    parts = [p.strip() for p in line.split("|")[1:-1]]
                    if len(parts) >= 7:
                        rows.append({
                            "rank": parts[0],
                            "type": parts[1],
                            "title": parts[3],
                            "score": parts[5],
                            "action": parts[7],
                        })

            tracking_summary.append({
                "file": f.name,
                "scan_since": fm.get("scan_since", ""),
                "domains_scanned": fm.get("domains_scanned", ""),
                "candidate_count": int(fm.get("candidate_count", 0)),
                "top_candidates": rows[:5],
            })
        except Exception as e:
            logger.debug("Failed to parse tracking file %s: %s", f, e)

    # --- Investigations ---
    investigations = []
    inv_dir = vault_path / "20_Investigations"
    if inv_dir.is_dir():
        for f in sorted(inv_dir.glob("*.md")):
            try:
                text = f.read_text(encoding="utf-8")
                fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
                fm = {}
                if fm_match:
                    for line in fm_match.group(1).splitlines():
                        if ":" in line:
                            k, _, v = line.partition(":")
                            fm[k.strip()] = v.strip().strip('"').strip("'")

                investigations.append({
                    "id": fm.get("inv_id", f.stem),
                    "source_hypothesis": fm.get("source_hypothesis", ""),
                    "ftm_id": fm.get("ftm_id", ""),
                    "status": fm.get("status", "unknown"),
                    "created": fm.get("created", ""),
                })
            except Exception as e:
                logger.debug("Failed to parse investigation %s: %s", f, e)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hypotheses": hyp_table,
        "tracking_candidates": tracking_summary,
        "investigations": investigations,
        "counts": {
            "hypotheses_total": hyp_result.get("total", 0),
            "tracking_files_scanned": len(tracking_files),
            "investigations_active": len([i for i in investigations if i.get("status") == "active"]),
        },
    }


def write_vault_index(index: dict[str, Any]) -> dict[str, Any]:
    """Write vault index to 00_Inbox/vault-index.md."""
    if not vault_bridge.vault_write_enabled():
        return {"ok": False, "error": "vault write disabled"}

    inbox = _inbox_dir()
    inbox.mkdir(parents=True, exist_ok=True)
    path = inbox / "vault-index.md"

    lines = [
        f"# Vault Index — {index['generated_at'][:10]}",
        "",
        f"## Counts",
        f"- Hypotheses (total): {index['counts']['hypotheses_total']}",
        f"- Tracking candidate files (recent): {index['counts']['tracking_files_scanned']}",
        f"- Investigations (active): {index['counts']['investigations_active']}",
        "",
        "## Hypotheses",
        "| ID | Status | Confidence | FTM ID | Pattern | Iteration |",
        "|----|--------|------------|--------|---------|-----------|",
    ]
    for h in index["hypotheses"]:
        lines.append(
            f"| {h['id']} | {h['status']} | {h['confidence']} | {h['ftm_id']} | {h['pattern']} | {h['iteration']} |"
        )

    lines.append("")
    lines.append("## Tracking Candidates (Last 3 Runs)")
    for tc in index["tracking_candidates"]:
        lines.append(f"### {tc['file']}")
        lines.append(f"- Scan since: {tc['scan_since']}")
        lines.append(f"- Domains: {tc['domains_scanned']}")
        lines.append(f"- Candidates: {tc['candidate_count']}")
        if tc["top_candidates"]:
            lines.append("| Rank | Type | Title | Score | Action |")
            lines.append("|------|------|-------|-------|--------|")
            for r in tc["top_candidates"]:
                lines.append(f"| {r['rank']} | {r['type']} | {r['title']} | {r['score']} | {r['action']} |")
        lines.append("")

    lines.append("## Investigations")
    lines.append("| ID | Source Hypothesis | FTM ID | Status | Created |")
    lines.append("|----|-------------------|--------|--------|---------|")
    for inv in index["investigations"]:
        lines.append(f"| {inv['id']} | {inv['source_hypothesis']} | {inv['ftm_id']} | {inv['status']} | {inv['created']} |")

    lines.append("")
    lines.append(f"*Generated at {index['generated_at']}*")

    content = "\n".join(lines)
    path.write_text(content, encoding="utf-8")
    logger.info("Wrote vault index: %s", path)
    return {"ok": True, "path": "00_Inbox/vault-index.md"}


def run_summarizer(
    iteration: int,
    *,
    entities: list[str],
    metrics: dict[str, int],
    hypotheses_written: int,
    skeptic_findings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Convenience function: generate and write both summary and index."""
    summary = generate_loop_summary(
        iteration=iteration,
        entities=entities,
        metrics=metrics,
        hypotheses_written=hypotheses_written,
        skeptic_findings=skeptic_findings,
    )
    write_loop_summary(summary, iteration)

    index = build_vault_index()
    write_vault_index(index)

    return {"summary_written": True, "index_written": True}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    # Test run: build index only
    if len(sys.argv) > 1 and sys.argv[1] == "--index-only":
        idx = build_vault_index()
        result = write_vault_index(idx)
        print(result)
    else:
        print("Usage: python -m api.services.nri_loop_summarizer --index-only")