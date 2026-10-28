"""Pull non-RSS API evidence into Situation hub notes.

Sources already in NI (not new collectors):
  - intelligence.macro_series_observations (FRED/ALFRED + EIA/trade import path)
  - intelligence.sanctions_actions (OFAC / EU / UN)
  - Federal Register public API (energy/minerals/sanctions notices)
  - intelligence.quiver_congress_trades (Quiver congress filings — DB-backed)
  - Optional GDELT doc count via existing GDELTRAGService (best-effort)

Writes a replaceable ``## Non-RSS evidence (API)`` section on cluster hubs so
CURRENT BRIEF stays RSS/corpus-grounded while series/sanctions fill blanks.

Finance hubs (``resource_movements``, ``market_trends``) also get a dedicated
replaceable finance section: prefer Quiver congress trades when rows exist,
else EIA macro rows (``source=eia_api``), else recent energy/rates history
already in ``macro_series_observations`` (FRED-sourced WTI / Fed funds).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import requests

from shared.database.connection import get_db_connection_context

logger = logging.getLogger(__name__)

API_SECTION_HEADER = "## Non-RSS evidence (API)"
_API_SECTION_RE = re.compile(
    r"\n## Non-RSS evidence \(API\)\n(?:.*?)(?=\n## |\Z)",
    re.S,
)

# Dedicated finance-API section (Quiver preferred; EIA / macro fallback)
FINANCE_QUIVER_HEADER = "## Congress trades (Quiver)"
FINANCE_EIA_HEADER = "## Energy (EIA)"
FINANCE_MACRO_HEADER = "## Energy / rates (macro series)"
_FINANCE_SECTION_RE = re.compile(
    r"\n## (?:Congress trades \(Quiver\)|Energy \(EIA\)|Energy / rates \(macro series\))\n"
    r"(?:.*?)(?=\n## |\Z)",
    re.S,
)

# Hub → FRED/macro series to surface (latest observation)
HUB_SERIES: dict[str, list[tuple[str, str]]] = {
    "market_trends": [
        ("FEDFUNDS", "Fed funds"),
        ("CPIAUCSL", "CPI (all urban)"),
        ("UNRATE", "Unemployment"),
        ("DTWEXBGS", "Trade-weighted USD"),
        ("DCOILWTICO", "WTI crude"),
    ],
    "resource_movements": [
        ("DCOILWTICO", "WTI crude"),
        ("DTWEXBGS", "Trade-weighted USD"),
        ("GPRHICU", "Geopolitical risk (GPR)"),
        ("GPRTOT", "GPR total"),
    ],
    "china_trade_tech": [
        ("DTWEXBGS", "Trade-weighted USD"),
        ("DCOILWTICO", "WTI crude"),
        ("GEPUCURRENT", "Global EPU"),
    ],
    "inflation_iran_war": [
        ("DCOILWTICO", "WTI crude"),
        ("CPIAUCSL", "CPI (all urban)"),
        ("GPRHICU", "Geopolitical risk (GPR)"),
    ],
    "climate_resource_policy": [
        ("DCOILWTICO", "WTI crude"),
    ],
}

# Hub → sanctions name ILIKE patterns
HUB_SANCTIONS: dict[str, list[str]] = {
    "venezuela_boe_gold": ["%venezuela%", "%maduro%", "%pdvsa%"],
    "iran_war": ["%iran%", "%irgc%", "%tehran%"],
    "inflation_iran_war": ["%iran%", "%irgc%"],
    "china_trade_tech": ["%china%", "%huawei%", "%xinjiang%"],
    "resource_movements": ["%iran%", "%russia%", "%venezuela%"],
}

HUB_FEDREG_TERMS: dict[str, str] = {
    "china_trade_tech": "export controls OR rare earth OR china tariffs",
    "resource_movements": "petroleum OR sanctions OR strategic petroleum",
    "climate_resource_policy": "climate OR critical minerals OR EPA",
    "venezuela_boe_gold": "Venezuela OR OFAC Venezuela",
    "ai_governance": "artificial intelligence OR machine learning governance",
    "us_institutions": "executive order OR Department of Justice OR State Department",
}

# Hub → Quiver ticker filters (empty list = any recent trades)
HUB_QUIVER_TICKERS: dict[str, list[str]] = {
    "resource_movements": [
        "XOM",
        "CVX",
        "COP",
        "OXY",
        "BP",
        "SHEL",
        "SLB",
        "HAL",
        "XLE",
        "XOP",
        "USO",
        "UNG",
        "GLD",
        "IAU",
        "GDX",
    ],
    "market_trends": [
        "SPY",
        "QQQ",
        "IWM",
        "TLT",
        "IEF",
        "HYG",
        "XLF",
        "XLE",
        "GLD",
        "NVDA",
        "AAPL",
        "MSFT",
        "JPM",
        "GS",
    ],
}

# Hub → recent macro history when Quiver/EIA empty (durable DB rows)
HUB_FINANCE_MACRO_HISTORY: dict[str, list[tuple[str, str]]] = {
    "resource_movements": [
        ("DCOILWTICO", "WTI crude"),
        ("DTWEXBGS", "Trade-weighted USD"),
    ],
    "market_trends": [
        ("FEDFUNDS", "Fed funds"),
        ("CPIAUCSL", "CPI (all urban)"),
        ("DCOILWTICO", "WTI crude"),
        ("DTWEXBGS", "Trade-weighted USD"),
    ],
}

FINANCE_API_HUBS = ("resource_movements", "market_trends")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def latest_macro_points(series_ids: list[str]) -> list[dict[str, Any]]:
    """One latest row per series_id from macro_series_observations."""
    if not series_ids:
        return []
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (series_id)
                    series_id, observation_date, value, source
                FROM intelligence.macro_series_observations
                WHERE series_id = ANY(%s)
                ORDER BY series_id, observation_date DESC, vintage_date DESC NULLS LAST
                """,
                (list(series_ids),),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in (cur.fetchall() or [])]


def refresh_macro_if_needed(series_ids: list[str]) -> dict[str, Any]:
    """Best-effort FRED refresh for missing/stale series (needs FRED_API_KEY)."""
    try:
        from services.macro_series_service import refresh_longitudinal_macro_series

        return refresh_longitudinal_macro_series(series_ids=series_ids)
    except Exception as e:
        logger.warning("macro refresh: %s", e)
        return {"success": False, "error": str(e)}


def sanctions_hits(patterns: list[str], *, limit: int = 8) -> list[dict[str, Any]]:
    if not patterns:
        return []
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema='intelligence' AND table_name='sanctions_actions'
                    """
                )
                cols = {r[0] for r in (cur.fetchall() or [])}
                if not cols:
                    return []
                name_col = next(
                    (c for c in ("entity_name", "name", "subject", "target_name") if c in cols),
                    None,
                )
                summary_col = next(
                    (c for c in ("summary", "title", "description", "action_summary") if c in cols),
                    None,
                )
                source_col = "source" if "source" in cols else "NULL::text"
                ts_col = next(
                    (c for c in ("created_at", "action_date", "listed_at", "updated_at") if c in cols),
                    None,
                )
                name_expr = name_col or "''"
                summary_expr = summary_col or "''"
                order_expr = ts_col or "1"
                or_bits = []
                params: list[Any] = []
                for p in patterns:
                    or_bits.append(
                        f"COALESCE({name_expr}::text, '') ILIKE %s "
                        f"OR COALESCE({summary_expr}::text, '') ILIKE %s"
                    )
                    params.extend([p, p])
                params.append(limit)
                cur.execute(
                    f"""
                    SELECT {source_col} AS source,
                           COALESCE({name_expr}::text, '') AS entity_name,
                           LEFT(COALESCE({summary_expr}::text, ''), 160) AS summary,
                           {order_expr} AS created_at
                    FROM intelligence.sanctions_actions
                    WHERE {' OR '.join(or_bits)}
                    ORDER BY {order_expr} DESC NULLS LAST
                    LIMIT %s
                    """,
                    tuple(params),
                )
                cnames = [d[0] for d in cur.description]
                return [dict(zip(cnames, r)) for r in (cur.fetchall() or [])]
    except Exception as e:
        logger.warning("sanctions_hits: %s", e)
        return []


def federal_register_notices(term: str, *, limit: int = 5) -> list[dict[str, Any]]:
    url = "https://www.federalregister.gov/api/v1/documents.json"
    params = {
        "conditions[term]": term,
        "per_page": min(limit, 20),
        "order": "newest",
        "fields[]": ["publication_date", "title", "html_url", "agencies"],
    }
    try:
        r = requests.get(url, params=params, timeout=45)
        r.raise_for_status()
        out = []
        for doc in r.json().get("results") or []:
            out.append(
                {
                    "date": doc.get("publication_date"),
                    "title": (doc.get("title") or "")[:180],
                    "url": doc.get("html_url") or "",
                }
            )
        return out
    except Exception as e:
        logger.warning("federal register: %s", e)
        return []


def quiver_congress_trades(
    tickers: list[str] | None = None,
    *,
    limit: int = 12,
    days: int = 365,
) -> list[dict[str, Any]]:
    """Recent rows from intelligence.quiver_congress_trades (DB only)."""
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            # Table may exist empty — never invent rows
            if tickers:
                cur.execute(
                    """
                    SELECT politician_name, ticker, company_name, transaction_type,
                           amount_range, traded_date, filed_date, chamber, party
                    FROM intelligence.quiver_congress_trades
                    WHERE ticker = ANY(%s)
                      AND (
                        traded_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
                        OR filed_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
                      )
                    ORDER BY COALESCE(traded_date, filed_date) DESC NULLS LAST
                    LIMIT %s
                    """,
                    (list(tickers), int(days), int(days), limit),
                )
            else:
                cur.execute(
                    """
                    SELECT politician_name, ticker, company_name, transaction_type,
                           amount_range, traded_date, filed_date, chamber, party
                    FROM intelligence.quiver_congress_trades
                    WHERE traded_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
                       OR filed_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
                    ORDER BY COALESCE(traded_date, filed_date) DESC NULLS LAST
                    LIMIT %s
                    """,
                    (int(days), int(days), limit),
                )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in (cur.fetchall() or [])]


def eia_macro_points(series_ids: list[str] | None = None, *, limit_per: int = 6) -> list[dict[str, Any]]:
    """Rows from macro_series_observations with source=eia_api (durable EIA import)."""
    sids = list(series_ids) if series_ids else ["WTI_SPOT"]
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT series_id, observation_date, value, source
                FROM (
                    SELECT series_id, observation_date, value, source,
                           ROW_NUMBER() OVER (
                             PARTITION BY series_id
                             ORDER BY observation_date DESC, vintage_date DESC NULLS LAST
                           ) AS rn
                    FROM intelligence.macro_series_observations
                    WHERE source = 'eia_api'
                      AND series_id = ANY(%s)
                      -- Drop gasoline-range pollution from multi-product spot route
                      AND NOT (
                        series_id ILIKE 'WTI%%'
                        AND value IS NOT NULL
                        AND value < 15
                      )
                ) t
                WHERE rn <= %s
                ORDER BY series_id, observation_date DESC
                """,
                (sids, limit_per),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in (cur.fetchall() or [])]


def macro_history_points(
    series_spec: list[tuple[str, str]],
    *,
    limit_per: int = 6,
) -> list[dict[str, Any]]:
    """Recent observations per series_id from macro_series_observations (any source)."""
    if not series_spec:
        return []
    sids = [s for s, _ in series_spec]
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT series_id, observation_date, value, source
                FROM (
                    SELECT series_id, observation_date, value, source,
                           ROW_NUMBER() OVER (
                             PARTITION BY series_id
                             ORDER BY observation_date DESC, vintage_date DESC NULLS LAST
                           ) AS rn
                    FROM intelligence.macro_series_observations
                    WHERE series_id = ANY(%s)
                ) t
                WHERE rn <= %s
                ORDER BY series_id, observation_date DESC
                """,
                (sids, limit_per),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in (cur.fetchall() or [])]


def build_finance_api_markdown(cluster_key: str) -> dict[str, Any]:
    """Prefer Quiver DB rows; else EIA macro; else FRED/macro history already in DB."""
    if cluster_key not in FINANCE_API_HUBS:
        return {"ok": False, "skipped": "not_finance_hub", "markdown": ""}

    tickers = HUB_QUIVER_TICKERS.get(cluster_key) or []
    trades: list[dict[str, Any]] = []
    try:
        trades = quiver_congress_trades(tickers or None, limit=12, days=540)
        # If ticker filter returned nothing, try any recent trades for awareness
        if not trades and tickers:
            trades = quiver_congress_trades(None, limit=8, days=180)
    except Exception as e:
        logger.warning("quiver_congress_trades %s: %s", cluster_key, e)

    if trades:
        lines = [
            FINANCE_QUIVER_HEADER,
            "",
            f"_Updated {_now_iso()[:19]}Z from ``intelligence.quiver_congress_trades`` "
            f"(Quiver filings already in NI — not a live API call)._ ",
            "",
            f"_Hub: `{cluster_key}`"
            + (f"; ticker filter: {', '.join(tickers[:8])}" if tickers else "")
            + "_",
            "",
        ]
        for t in trades:
            day = str(t.get("traded_date") or t.get("filed_date") or "")[:10]
            who = (t.get("politician_name") or "member").strip()
            ticker = (t.get("ticker") or "?").strip()
            side = (t.get("transaction_type") or "").strip()
            amt = (t.get("amount_range") or "").strip()
            co = (t.get("company_name") or "").strip()
            party = (t.get("party") or "").strip()
            chamber = (t.get("chamber") or "").strip()
            meta = " / ".join(x for x in (chamber, party) if x)
            extra = f" — {co}" if co else ""
            amt_s = f" · {amt}" if amt else ""
            lines.append(
                f"- {day} — **{who}** ({meta}): {side} `{ticker}`{extra}{amt_s}"
            )
        lines.append("")
        lines.append("- Source: Quiver Quantitative → `intelligence.quiver_congress_trades`")
        lines.append("")
        return {
            "ok": True,
            "source": "quiver",
            "header": FINANCE_QUIVER_HEADER,
            "row_n": len(trades),
            "markdown": "\n".join(lines).rstrip() + "\n",
        }

    eia_rows: list[dict[str, Any]] = []
    try:
        eia_rows = eia_macro_points(limit_per=6)
    except Exception as e:
        logger.warning("eia_macro_points %s: %s", cluster_key, e)

    if eia_rows:
        lines = [
            FINANCE_EIA_HEADER,
            "",
            f"_Updated {_now_iso()[:19]}Z from ``macro_series_observations`` "
            f"(source=`eia_api`). Quiver congress trades table was empty._",
            "",
            f"_Hub: `{cluster_key}`_",
            "",
        ]
        by_series: dict[str, list[dict[str, Any]]] = {}
        for r in eia_rows:
            by_series.setdefault(str(r["series_id"]), []).append(r)
        for sid, pts in by_series.items():
            lines.append(f"### `{sid}`")
            for p in pts:
                lines.append(
                    f"- {p['observation_date']}: **{p['value']}** ({p.get('source') or 'eia_api'})"
                )
            lines.append("")
        lines.append("- Source: EIA API import → `intelligence.macro_series_observations`")
        lines.append("")
        return {
            "ok": True,
            "source": "eia",
            "header": FINANCE_EIA_HEADER,
            "row_n": len(eia_rows),
            "markdown": "\n".join(lines).rstrip() + "\n",
        }

    # Durable fallback: FRED/macro history already in DB (WTI / Fed funds)
    series_spec = HUB_FINANCE_MACRO_HISTORY.get(cluster_key) or []
    hist = macro_history_points(series_spec, limit_per=6) if series_spec else []
    lines = [
        FINANCE_MACRO_HEADER,
        "",
        f"_Updated {_now_iso()[:19]}Z from ``macro_series_observations``. "
        f"Quiver trades and EIA (`eia_api`) rows were empty — using stored FRED/macro "
        f"history for this finance hub._",
        "",
        f"_Hub: `{cluster_key}`_",
        "",
    ]
    if not hist:
        lines.append("- _No macro history for configured series._")
        lines.append("")
    else:
        by_series: dict[str, list[dict[str, Any]]] = {}
        for r in hist:
            by_series.setdefault(str(r["series_id"]), []).append(r)
        for sid, lab in series_spec:
            pts = by_series.get(sid) or []
            lines.append(f"### {lab} (`{sid}`)")
            if not pts:
                lines.append("- _missing_")
            else:
                for p in pts:
                    lines.append(
                        f"- {p['observation_date']}: **{p['value']}** "
                        f"({p.get('source') or 'macro'})"
                    )
            lines.append("")
        lines.append(
            "- Source: NI macro store (typically FRED) → "
            "`intelligence.macro_series_observations`"
        )
        lines.append("")

    return {
        "ok": True,
        "source": "macro_fallback",
        "header": FINANCE_MACRO_HEADER,
        "row_n": len(hist),
        "markdown": "\n".join(lines).rstrip() + "\n",
        "note": "quiver_and_eia_empty",
    }


def patch_finance_api_section(body: str, finance_md: str) -> str:
    text = body or ""
    block = "\n" + finance_md.strip() + "\n"
    if _FINANCE_SECTION_RE.search(text):
        return _FINANCE_SECTION_RE.sub(block, text, count=1)
    # Place after Non-RSS API section when present, else before Sources
    if "\n## Non-RSS evidence (API)\n" in text:
        # Append immediately after the Non-RSS block
        m = _API_SECTION_RE.search(text)
        if m:
            end = m.end()
            return text[:end] + block + text[end:]
    for marker in ("\n## Sources\n", "\n## Timeline\n"):
        if marker in text:
            return text.replace(marker, block + marker, 1)
    return text.rstrip() + "\n" + block


def build_evidence_markdown(cluster_key: str, *, refresh_macro: bool = True) -> str:
    lines = [
        API_SECTION_HEADER,
        "",
        f"_Updated {_now_iso()[:19]}Z from NI API stores (not RSS)._ ",
        "",
    ]

    series_spec = HUB_SERIES.get(cluster_key) or []
    if series_spec:
        sids = [s for s, _ in series_spec]
        if refresh_macro:
            refresh_macro_if_needed(sids)
        points = {p["series_id"]: p for p in latest_macro_points(sids)}
        lines.append("### Macro / series (FRED+)")
        if not points:
            lines.append("- _No macro_series_observations yet — check FRED_API_KEY / macro_series_refresh._")
        else:
            label = {s: lab for s, lab in series_spec}
            for sid, lab in series_spec:
                p = points.get(sid)
                if not p:
                    lines.append(f"- {lab} (`{sid}`): _missing_")
                    continue
                lines.append(
                    f"- {lab} (`{sid}`): **{p['value']}** as of {p['observation_date']} "
                    f"({p.get('source') or 'fred'})"
                )
        lines.append("")

    sanc_pats = HUB_SANCTIONS.get(cluster_key) or []
    if sanc_pats:
        hits = sanctions_hits(sanc_pats, limit=6)
        lines.append("### Sanctions ingest (OFAC/EU/UN)")
        if not hits:
            lines.append(
                "- _No matching sanctions_actions rows — run automation `sanctions_refresh`._"
            )
        else:
            for h in hits:
                name = (h.get("entity_name") or "").strip() or "entry"
                summ = (h.get("summary") or "").strip()
                src = h.get("source") or "sanctions"
                lines.append(f"- [{src}] {name}: {summ[:140]}")
        lines.append("")

    fr_term = HUB_FEDREG_TERMS.get(cluster_key)
    if fr_term:
        notices = federal_register_notices(fr_term, limit=4)
        lines.append("### Federal Register notices")
        if not notices:
            lines.append("- _No recent FR hits for this query._")
        else:
            for n in notices:
                title = n.get("title") or "notice"
                url = n.get("url") or ""
                day = n.get("date") or ""
                if url:
                    lines.append(f"- {day} — [{title}]({url})")
                else:
                    lines.append(f"- {day} — {title}")
        lines.append("")

    if len(lines) <= 4:
        lines.append("_No API evidence mappings configured for this hub._")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def patch_hub_api_section(body: str, evidence_md: str) -> str:
    text = body or ""
    block = "\n" + evidence_md.strip() + "\n"
    if _API_SECTION_RE.search(text):
        return _API_SECTION_RE.sub(block, text, count=1)
    # Insert before Sources if present, else append
    if "\n## Sources\n" in text:
        return text.replace("\n## Sources\n", block + "\n## Sources\n", 1)
    return text.rstrip() + "\n" + block


def apply_evidence_to_hub(
    cluster_key: str,
    *,
    refresh_macro: bool = True,
    dry_run: bool = False,
    include_finance_api: bool = True,
) -> dict[str, Any]:
    from services.vault_bridge_service import vault_root
    from services.vault_cluster_hub_service import get_cluster_hub
    from services.vault_notes_registry_service import upsert_vault_note

    hub = get_cluster_hub(cluster_key=cluster_key)
    if not hub:
        return {"ok": False, "cluster_key": cluster_key, "error": "hub_missing"}
    path = str(hub.get("vault_path") or "")
    if not path:
        return {"ok": False, "cluster_key": cluster_key, "error": "no_path"}
    evidence = build_evidence_markdown(cluster_key, refresh_macro=refresh_macro)
    finance_info: dict[str, Any] | None = None
    if include_finance_api and cluster_key in FINANCE_API_HUBS:
        finance_info = build_finance_api_markdown(cluster_key)
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "cluster_key": cluster_key,
            "evidence_chars": len(evidence),
            "finance_api": (
                {
                    "source": (finance_info or {}).get("source"),
                    "row_n": (finance_info or {}).get("row_n"),
                    "chars": len((finance_info or {}).get("markdown") or ""),
                    "header": (finance_info or {}).get("header"),
                }
                if finance_info
                else None
            ),
        }

    root = vault_root()
    fp = root / path
    if not fp.is_file():
        return {"ok": False, "cluster_key": cluster_key, "error": "file_missing", "path": path}
    existing = fp.read_text(encoding="utf-8")
    if re.search(r"brief_locked:\s*(true|1|yes)", existing, re.I):
        # Still allow API evidence section — factual series, not brief rewrite
        pass
    patched = patch_hub_api_section(existing, evidence).replace("\x00", "")
    if finance_info and finance_info.get("markdown"):
        patched = patch_finance_api_section(patched, finance_info["markdown"]).replace(
            "\x00", ""
        )
    fp.write_text(patched, encoding="utf-8")

    meta = dict(hub.get("metadata") or {})
    meta["api_evidence_updated_at"] = _now_iso()
    meta["api_evidence_source"] = "situation_api_evidence_service"
    if finance_info and finance_info.get("ok"):
        meta["finance_api_evidence_updated_at"] = _now_iso()
        meta["finance_api_evidence_source"] = finance_info.get("source")
        meta["finance_api_evidence_header"] = finance_info.get("header")
        meta["finance_api_evidence_row_n"] = finance_info.get("row_n")
    upsert_vault_note(
        domain_key=str(hub.get("domain_key") or meta.get("domain_key") or "politics"),
        note_type="cluster",
        object_id=int(hub["object_id"]),
        vault_path=path,
        title=hub.get("title"),
        note_status="note_ready",
        lifecycle=str(hub.get("lifecycle") or "living"),
        body_md=patched,
        summary_md=(hub.get("summary_md") or None),
        metadata=meta,
        tags_source="ni_structural",
    )
    return {
        "ok": True,
        "cluster_key": cluster_key,
        "path": path,
        "evidence_chars": len(evidence),
        "finance_api": (
            {
                "source": finance_info.get("source"),
                "row_n": finance_info.get("row_n"),
                "header": finance_info.get("header"),
                "note": finance_info.get("note"),
            }
            if finance_info
            else None
        ),
    }


DEFAULT_HUBS = (
    "market_trends",
    "resource_movements",
    "china_trade_tech",
    "inflation_iran_war",
    "venezuela_boe_gold",
    "climate_resource_policy",
    "ai_governance",
    "us_institutions",
    "iran_war",
)


def apply_evidence_batch(
    cluster_keys: list[str] | None = None,
    *,
    refresh_macro: bool = True,
    dry_run: bool = False,
    include_finance_api: bool = True,
) -> dict[str, Any]:
    keys = list(cluster_keys or DEFAULT_HUBS)
    results = []
    for k in keys:
        try:
            results.append(
                apply_evidence_to_hub(
                    k,
                    refresh_macro=refresh_macro,
                    dry_run=dry_run,
                    include_finance_api=include_finance_api,
                )
            )
        except Exception as e:
            logger.exception("api evidence %s", k)
            results.append({"ok": False, "cluster_key": k, "error": str(e)})
    return {
        "ok": True,
        "n": len(results),
        "ok_n": sum(1 for r in results if r.get("ok")),
        "results": results,
    }
