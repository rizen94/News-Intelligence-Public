# Editorial room — causal narrative scaffold (Phase A)

When synthesizing a storyline or tracked-event narrative:

1. **Load the causal subgraph** — use only `intelligence.causal_edges` (and linked evidence_context_ids) provided in context.
2. **Chain-of-thought** — emit explicit steps: (a) which edges apply, (b) evidence grade, (c) what is *not* claimed.
3. **Narrative** — write prose that cites `edge_id=N` for every causal claim. If no typed edge exists, use correlational language only ("coincided with", "followed") — never "caused" / "led to" / "because of".
4. **Persist** — return `reasoning_steps` JSON alongside the narrative for the Reasoning UI panel.

## Output JSON

```json
{
  "reasoning_steps": [
    {"step": 1, "claim": "...", "edge_ids": [12], "evidence_grade": "moderate"},
    {"step": 2, "claim": "...", "edge_ids": [], "note": "correlation only"}
  ],
  "narrative": "...",
  "cited_edge_ids": [12]
}
```
