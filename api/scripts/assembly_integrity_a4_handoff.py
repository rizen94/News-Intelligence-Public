#!/usr/bin/env python3
"""A4 thin handoff backfill: registry rows for vaulted briefs + clipping ensure for article members."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "api"))

env_file = _ROOT / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)
    except Exception:
        pass

logger = logging.getLogger("a4_handoff")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clip-limit", type=int, default=200, help="Max article members to clip")
    ap.add_argument("--brief-limit", type=int, default=200, help="Max vaulted briefs to register")
    args = ap.parse_args()

    from shared.database.connection import get_db_connection_context
    from services.vault_notes_registry_service import upsert_vault_note
    from shared.vault_note_contract import structural_tags_for_note
    from services.vault_mvp_ingest_service import file_article_to_vault

    brief_n = clip_n = clip_ok = 0
    with get_db_connection_context() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT b.package_id, b.vault_rel_path, b.lede, b.brief_md, b.expand_round,
                   p.working_title, p.domain_keys
            FROM intelligence.package_evidence_briefs b
            JOIN intelligence.editorial_packages p ON p.id = b.package_id
            WHERE COALESCE(b.vault_rel_path, '') <> ''
            ORDER BY b.updated_at DESC NULLS LAST
            LIMIT %s
            """,
            (int(args.brief_limit),),
        )
        briefs = cur.fetchall() or []
        cur.execute(
            """
            SELECT DISTINCT m.domain_key, m.member_id
            FROM intelligence.editorial_package_members m
            WHERE m.member_type = 'article'
              AND COALESCE(m.status, 'active') = 'active'
              AND m.added_at > NOW() - INTERVAL '90 days'
              AND COALESCE(m.domain_key, '') <> ''
              AND NOT EXISTS (
                SELECT 1 FROM intelligence.vault_notes vn
                WHERE vn.note_type = 'clipping'
                  AND vn.object_id = m.member_id
                  AND vn.domain_key = m.domain_key
              )
            ORDER BY m.member_id DESC
            LIMIT %s
            """,
            (int(args.clip_limit),),
        )
        arts = cur.fetchall() or []

    for pid, rel, lede, brief_md, expand_round, title, dks in briefs:
        domain_key = "global"
        if isinstance(dks, list) and dks:
            domain_key = str(dks[0])
        tags = structural_tags_for_note(
            note_type="cluster",
            domain_key=domain_key,
            extra=["package_evidence_brief", f"package/{int(pid)}"],
        )
        try:
            upsert_vault_note(
                domain_key=domain_key,
                note_type="cluster",
                object_id=int(pid),
                vault_path=str(rel),
                title=str(title or f"package-{pid}"),
                note_status="note_ready",
                lifecycle="living",
                tags=tags,
                body_md=(brief_md or "")[:12000],
                summary_md=(lede or "")[:320],
                metadata={
                    "package_id": int(pid),
                    "package_evidence_brief": True,
                    "expand_round": expand_round or 0,
                    "a4_backfill": True,
                },
                tags_source="ni_structural",
            )
            brief_n += 1
        except Exception as e:
            logger.warning("brief registry %s: %s", pid, e)

    for domain_key, aid in arts:
        clip_n += 1
        try:
            out = file_article_to_vault(
                domain_key=str(domain_key),
                article_id=int(aid),
                skip_llm_summary=True,
            )
            if out.get("ok") or out.get("skipped"):
                clip_ok += 1
            else:
                logger.warning("clip %s/%s: %s", domain_key, aid, out)
        except Exception as e:
            logger.warning("clip %s/%s: %s", domain_key, aid, e)

    print(f"brief_registry_upserts={brief_n} clipping_attempts={clip_n} clipping_okish={clip_ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
