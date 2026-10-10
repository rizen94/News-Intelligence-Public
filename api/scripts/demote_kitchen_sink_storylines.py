#!/usr/bin/env python3
"""
Demote bridge-title kitchen-sink storylines and restore soft-magnet false positives.

Dry-run by default; pass --apply to write.

  PYTHONPATH=api python3 api/scripts/demote_kitchen_sink_storylines.py --domain politics
  PYTHONPATH=api python3 api/scripts/demote_kitchen_sink_storylines.py --all --apply
  PYTHONPATH=api python3 api/scripts/demote_kitchen_sink_storylines.py --domain politics --apply \\
      --min-canon-restore 500

Demote: title_looks_mega_bag → is_mega_storyline=true, automation_enabled=false.
Restore: soft_magnet demotes whose title is not a bridge bag and still match
         title↔signature (or have a substantial finished narrative).
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection_context  # noqa: E402
from shared.domain_registry import (  # noqa: E402
    get_pipeline_active_domain_keys,
    resolve_domain_schema,
)


def _load_title_looks_mega_bag():
    """Load helper without importing services/__init__ (psutil etc.)."""
    import importlib.util

    path = ROOT / "api" / "services" / "storyline_coherence_guardrails.py"
    name = "storyline_coherence_guardrails_demote_script"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod.title_looks_mega_bag


title_looks_mega_bag = _load_title_looks_mega_bag()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("demote_kitchen_sink_storylines")

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'-]{2,}", re.I)
_DEMOTE_META = {
    "demote_reason": "kitchen_sink_mega_bag",
    "demoted_by": "demote_kitchen_sink_storylines",
}
_RESTORE_META = {
    "restored_from": "soft_magnet",
    "restored_by": "demote_kitchen_sink_storylines",
}


def _title_tokens(title: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(title or "")}


def _sig_name_tokens(sig: object) -> set[str]:
    if isinstance(sig, str):
        try:
            sig = json.loads(sig)
        except Exception:
            return set()
    if not isinstance(sig, dict):
        return set()
    out: set[str] = set()
    for x in list(sig.get("identity") or []) + list(sig.get("supporting") or []):
        s = str(x).strip().lower()
        if not s or s.startswith("cid:"):
            continue
        out |= _title_tokens(s)
        out.add(s)
    return out


def _title_sig_mismatch(title: str, sig: object) -> bool:
    names = _sig_name_tokens(sig)
    if not names:
        return True
    title_toks = _title_tokens(title)
    if not title_toks:
        return False
    return names.isdisjoint(title_toks)


def run_domain(
    domain_key: str,
    *,
    apply: bool,
    min_canon_restore: int,
    demote_only: bool,
    restore_only: bool,
) -> dict[str, Any]:
    schema = resolve_domain_schema(domain_key)
    stats: dict[str, Any] = {
        "domain": domain_key,
        "schema": schema,
        "bridge_demoted": 0,
        "soft_magnet_restored": 0,
        "eels_unquarantined": 0,
        "demote_ids": [],
        "restore_ids": [],
        "apply": bool(apply),
    }
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            if not restore_only:
                cur.execute(
                    f"""
                    SELECT id, title,
                           COALESCE(is_mega_storyline, FALSE),
                           COALESCE(automation_enabled, TRUE)
                    FROM {schema}.storylines
                    WHERE COALESCE(status, 'active')
                          NOT IN ('archived', 'merged', 'deleted')
                    """
                )
                demote_ids: list[int] = []
                for sid, title, mega, auto in cur.fetchall() or []:
                    if not title_looks_mega_bag(title):
                        continue
                    if mega and not auto:
                        continue
                    demote_ids.append(int(sid))
                    logger.info(
                        "[%s] demote id=%s mega=%s auto=%s title=%s",
                        domain_key,
                        sid,
                        mega,
                        auto,
                        (title or "")[:70],
                    )
                stats["demote_ids"] = demote_ids
                if apply and demote_ids:
                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET is_mega_storyline = TRUE,
                            automation_enabled = FALSE,
                            metadata = COALESCE(metadata, '{{}}'::jsonb) || %s::jsonb,
                            updated_at = NOW()
                        WHERE id = ANY(%s)
                        """,
                        (json.dumps(_DEMOTE_META), demote_ids),
                    )
                    stats["bridge_demoted"] = int(cur.rowcount or 0)
                else:
                    stats["bridge_demoted"] = len(demote_ids)

            if not demote_only:
                cur.execute(
                    f"""
                    SELECT id, title, anchor_signature,
                           length(COALESCE(canonical_narrative, '')),
                           metadata->>'magnet_reason'
                    FROM {schema}.storylines
                    WHERE COALESCE(status, 'active')
                          NOT IN ('archived', 'merged', 'deleted')
                      AND metadata->>'demote_reason' = 'soft_magnet'
                      AND COALESCE(is_mega_storyline, FALSE) = TRUE
                    """
                )
                restore_ids: list[int] = []
                for sid, title, sig, clen, _mreason in cur.fetchall() or []:
                    if title_looks_mega_bag(title):
                        continue
                    if _title_sig_mismatch(title or "", sig) and int(clen or 0) < int(
                        min_canon_restore
                    ):
                        continue
                    restore_ids.append(int(sid))
                    logger.info(
                        "[%s] restore soft_magnet id=%s canon=%s title=%s",
                        domain_key,
                        sid,
                        clen,
                        (title or "")[:70],
                    )
                stats["restore_ids"] = restore_ids
                if apply and restore_ids:
                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET story_kind = 'event_narrative',
                            is_mega_storyline = FALSE,
                            automation_enabled = FALSE,
                            episode_state = CASE
                              WHEN COALESCE(episode_state, '')
                                   IN ('concluded', 'dormant') THEN 'active'
                              ELSE COALESCE(episode_state, 'active')
                            END,
                            metadata = (
                              COALESCE(metadata, '{{}}'::jsonb)
                              - 'demote_reason'
                              - 'magnet_reason'
                              - 'magnet_eels_at_demote'
                              - 'assembly_role'
                            ) || %s::jsonb,
                            updated_at = NOW()
                        WHERE id = ANY(%s)
                        """,
                        (json.dumps(_RESTORE_META), restore_ids),
                    )
                    stats["soft_magnet_restored"] = int(cur.rowcount or 0)
                    cur.execute(
                        """
                        UPDATE intelligence.event_episode_links
                        SET inference_stage = 'candidate',
                            updated_at = NOW(),
                            metadata = COALESCE(metadata, '{}'::jsonb)
                                || '{"restored_from":"soft_magnet"}'::jsonb
                        WHERE domain_key = %s
                          AND episode_id = ANY(%s)
                          AND inference_stage = 'quarantined'
                          AND COALESCE(metadata->>'quarantine_reason', '') = 'soft_magnet'
                        """,
                        (domain_key, restore_ids),
                    )
                    stats["eels_unquarantined"] = int(cur.rowcount or 0)
                else:
                    stats["soft_magnet_restored"] = len(restore_ids)

            if apply:
                conn.commit()
            else:
                conn.rollback()
    return stats


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domain")
    p.add_argument("--all", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--demote-only", action="store_true")
    p.add_argument("--restore-only", action="store_true")
    p.add_argument(
        "--min-canon-restore",
        type=int,
        default=500,
        help="Restore soft_magnet rows with finished narrative >= this length "
        "even if title↔signature still mismatches (default 500)",
    )
    args = p.parse_args()
    if args.demote_only and args.restore_only:
        p.error("Pass only one of --demote-only / --restore-only")
    domains = (
        list(get_pipeline_active_domain_keys())
        if args.all
        else ([args.domain] if args.domain else [])
    )
    if not domains:
        p.error("Pass --domain KEY or --all")
    out = []
    for dk in domains:
        st = run_domain(
            dk,
            apply=bool(args.apply),
            min_canon_restore=int(args.min_canon_restore),
            demote_only=bool(args.demote_only),
            restore_only=bool(args.restore_only),
        )
        out.append(st)
        logger.info("stats %s", st)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
