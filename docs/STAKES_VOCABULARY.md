# Stakes vocabulary (blocking for L1 UI)

**Do not conflate these.** Wiring L1 intake UI to the wrong module will break editorial THIN.

| Name | What it is | Code / data |
|------|------------|-------------|
| **Editorial StakesGate** | THIN publish gate: identity actor + act-verb + citeable evidence; packages without reader sections (`What's new` / `Why this matters` / `Timeline` / `What to watch`) go thin. Nut graf + walkaway still count as aliases. | `api/shared/stakes_gate.py` · package compose |
| **Intake stakes modulator** (four-feature) | Proposed L1: `arousal` / `targeted_threat` / `source_surprise` / `frame_prior`, ~30% cap | **Not implemented** — no columns on `*.articles` yet |

## Required labels in future UI

- Package / editor surfaces → **“StakesGate”** or **“editorial stakes”** (only when referring to `stakes_gate.py`).
- Article intake L1 panel → **“intake stakes”** or **“stakes modulator”** — never bare “stakes” alone.

Put the same note in tickets before L1 work is scheduled. See also `docs/reviews/v12_visual_audit_verdict_2026-08-16.md`.
