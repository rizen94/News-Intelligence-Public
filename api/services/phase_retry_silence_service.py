"""Phase E: config-driven per-phase retry/backoff and auto-silence on persistent failure."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BACKOFF_BASE = 60
_DEFAULT_BACKOFF_CAP = 300
_DEFAULT_SILENCE_AFTER = 3


def _policy_cfg() -> dict[str, Any]:
    try:
        from config.orchestrator_governance import get_orchestrator_governance_config

        cfg = get_orchestrator_governance_config() or {}
        block = cfg.get("phase_retry_policy") or {}
        return block if isinstance(block, dict) else {}
    except Exception:
        return {}


def phase_retry_policy_enabled() -> bool:
    block = _policy_cfg()
    if "enabled" in block:
        return bool(block.get("enabled"))
    try:
        from config.feature_registry import is_feature_enabled

        return bool(is_feature_enabled("phase_auto_silence"))
    except Exception:
        return True


def max_retries_for_phase(phase_name: str) -> int:
    block = _policy_cfg()
    overrides = block.get("phases") or {}
    if isinstance(overrides, dict) and phase_name in overrides:
        raw = (overrides[phase_name] or {}).get("max_retries")
        if raw is not None:
            return max(0, int(raw))
    return max(0, int(block.get("max_retries", _DEFAULT_MAX_RETRIES)))


def backoff_seconds_for_retry(phase_name: str, retry_count: int) -> int:
    block = _policy_cfg()
    overrides = block.get("phases") or {}
    base = _DEFAULT_BACKOFF_BASE
    cap = _DEFAULT_BACKOFF_CAP
    if isinstance(overrides, dict) and phase_name in overrides:
        o = overrides[phase_name] or {}
        if o.get("backoff_base_sec") is not None:
            base = int(o["backoff_base_sec"])
        if o.get("backoff_cap_sec") is not None:
            cap = int(o["backoff_cap_sec"])
    else:
        base = int(block.get("backoff_base_sec", base))
        cap = int(block.get("backoff_cap_sec", cap))
    n = max(1, int(retry_count) + 1)
    return min(base * n, max(base, cap))


def silence_after_failing_streak(phase_name: str) -> int:
    block = _policy_cfg()
    overrides = block.get("phases") or {}
    if isinstance(overrides, dict) and phase_name in overrides:
        raw = (overrides[phase_name] or {}).get("silence_after_failing_streak")
        if raw is not None:
            return max(1, int(raw))
    return max(1, int(block.get("silence_after_failing_streak", _DEFAULT_SILENCE_AFTER)))


def list_auto_silenced_phases() -> set[str]:
    """Active auto-silences (cleared_at IS NULL)."""
    out: set[str] = set()
    try:
        from shared.database.connection import get_ui_db_connection_context

        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT phase_name FROM public.phase_silence_state
                    WHERE cleared_at IS NULL AND auto_silenced = TRUE
                    """
                )
                for row in cur.fetchall() or []:
                    name = row[0] if not isinstance(row, dict) else row.get("phase_name")
                    if name:
                        out.add(str(name))
    except Exception as e:
        logger.debug("list_auto_silenced_phases: %s", e)
    return out


def is_phase_auto_silenced(phase_name: str) -> bool:
    return phase_name.strip() in list_auto_silenced_phases()


def silence_phase(
    phase_name: str,
    *,
    reason: str,
    health_status: str | None = None,
    failing_streak: int = 0,
    detail: dict[str, Any] | None = None,
) -> None:
    import json

    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.phase_silence_state (
                        phase_name, silenced_at, reason, health_status,
                        failing_streak, auto_silenced, cleared_at, detail
                    ) VALUES (%s, NOW(), %s, %s, %s, TRUE, NULL, %s::jsonb)
                    ON CONFLICT (phase_name) DO UPDATE SET
                        silenced_at = NOW(),
                        reason = EXCLUDED.reason,
                        health_status = EXCLUDED.health_status,
                        failing_streak = EXCLUDED.failing_streak,
                        auto_silenced = TRUE,
                        cleared_at = NULL,
                        detail = EXCLUDED.detail
                    """,
                    (
                        phase_name,
                        (reason or "")[:500],
                        health_status,
                        int(failing_streak),
                        json.dumps(detail or {}),
                    ),
                )
            conn.commit()
        logger.warning(
            "phase_auto_silence:%s status=%s reason=%s",
            phase_name,
            health_status,
            (reason or "")[:120],
        )
        try:
            from services.pipeline_phase_heartbeat_service import record_phase_heartbeat

            record_phase_heartbeat(
                phase_name,
                scheduler_path="widow",
                success=False,
                items_processed=0,
                detail={
                    "status": "silenced",
                    "reason": reason,
                    "health_status": health_status,
                },
            )
        except Exception:
            pass
    except Exception as e:
        logger.warning("silence_phase %s failed: %s", phase_name, e)


def clear_phase_silence(phase_name: str) -> None:
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE public.phase_silence_state
                    SET cleared_at = NOW()
                    WHERE phase_name = %s AND cleared_at IS NULL
                    """,
                    (phase_name,),
                )
            conn.commit()
    except Exception as e:
        logger.debug("clear_phase_silence %s: %s", phase_name, e)


def apply_auto_silence_from_health(phase_health: dict[str, Any]) -> list[str]:
    """
    Persist silence when a phase is failing/stalled for N consecutive controller assessments.
    Returns newly silenced phase names.
    """
    if not phase_retry_policy_enabled():
        return []
    newly: list[str] = []
    dry_run = bool(_policy_cfg().get("dry_run", False))
    for phase, health in (phase_health or {}).items():
        status = getattr(health, "status", None) or (
            health.get("status") if isinstance(health, dict) else None
        )
        detail = getattr(health, "detail", None) or (
            health.get("detail") if isinstance(health, dict) else ""
        )
        if status not in ("failing", "stalled"):
            # Clear streak bookkeeping via detail on heartbeat only; keep silence until operator clear.
            continue
        streak = _bump_failing_streak(phase, status=str(status))
        threshold = silence_after_failing_streak(phase)
        if streak < threshold:
            continue
        if is_phase_auto_silenced(phase):
            continue
        reason = f"auto-silence after {streak}x {status}: {detail or ''}"
        if dry_run:
            logger.info("phase_auto_silence dry_run:%s %s", phase, reason[:120])
            continue
        silence_phase(
            phase,
            reason=reason,
            health_status=str(status),
            failing_streak=streak,
            detail={"detail": detail},
        )
        newly.append(phase)
    return newly


def _bump_failing_streak(phase: str, *, status: str) -> int:
    """Track consecutive failing assessments in automation_state JSON."""
    import json

    key = "phase_failing_streaks"
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value FROM public.automation_state WHERE key = %s",
                    (key,),
                )
                row = cur.fetchone()
                data: dict[str, Any] = {}
                if row and row[0]:
                    raw = row[0]
                    data = json.loads(raw) if isinstance(raw, str) else dict(raw)
                entry = data.get(phase) or {"streak": 0, "status": status}
                if entry.get("status") == status:
                    entry["streak"] = int(entry.get("streak") or 0) + 1
                else:
                    entry = {"streak": 1, "status": status}
                data[phase] = entry
                cur.execute(
                    """
                    INSERT INTO public.automation_state (key, value, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                    """,
                    (key, json.dumps(data)),
                )
            conn.commit()
            return int(entry["streak"])
    except Exception as e:
        logger.debug("_bump_failing_streak %s: %s", phase, e)
        return 1
