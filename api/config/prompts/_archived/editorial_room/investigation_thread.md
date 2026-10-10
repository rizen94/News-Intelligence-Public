# Editorial room — investigation thread

Draft nonlinear investigation hypotheses in the vault (`20_Investigations/`), ported from ACH synthesizer patterns.

## Rules

1. Anchor every hypothesis to `tracked_event_id` and/or `context_id` in frontmatter.
2. List competing hypotheses (H1, H2) with evidence for/against — do not assert single truth.
3. Link to `graph_connection_links` neighbors when provided in context.
4. Investigation threads stay in vault until operator promotes to `tracked_events`.

## Output JSON

```json
{
  "actions": [
    {
      "type": "draft_investigation",
      "title": "payment-rail-inquiry",
      "tracked_event_id": 55,
      "domain_key": "finance",
      "hypotheses": [
        {"id": "H1", "statement": "...", "support": [], "contradict": []}
      ],
      "confidence": 0.6
    }
  ]
}
```
