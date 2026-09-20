"""Version-controlled resolver judgements synced to git."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RESOLVER_DIR = Path(__file__).resolve().parents[1] / "data" / "resolver"


def resolver_file() -> Path:
    RESOLVER_DIR.mkdir(parents=True, exist_ok=True)
    return RESOLVER_DIR / "judgements.json"


def load_judgements() -> list[dict[str, Any]]:
    path = resolver_file()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_judgements(judgements: list[dict[str, Any]]) -> None:
    path = resolver_file()
    path.write_text(json.dumps(judgements, indent=2), encoding="utf-8")


def add_judgement(left_id: str, right_id: str, score: float, judgement: str) -> None:
    from nri_core.spine.store import postgres_store

    judgements = load_judgements()
    entry = {
        "left_id": left_id,
        "right_id": right_id,
        "score": score,
        "judgement": judgement,
    }
    judgements.append(entry)
    save_judgements(judgements)
    with postgres_store.spine_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO resolver_judgements (left_id, right_id, score, judgement)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (left_id, right_id) DO UPDATE SET
                    score = EXCLUDED.score,
                    judgement = EXCLUDED.judgement
                """,
                (left_id, right_id, score, judgement),
            )
