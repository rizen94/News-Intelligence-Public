# Graph edge provenance (Postgres self-reviewing graph)

Auditable scoring for `intelligence.graph_connection_proposals` and materialized
`intelligence.graph_connection_links`. No separate Neo4j — Postgres is the graph SSOT.

## Evidence JSON contract

Both proposals (`evidence`) and links (`evidence`, migration 270) use:

```json
{
  "phase": "embedding_link_candidates",
  "method": "cosine_chunk|entity_jaccard|cross_domain_canonical|storyline_similarity",
  "score_parts": {
    "semantic": 0.71,
    "entity": 0.40,
    "overall": 0.62
  },
  "anchors": {
    "article_ids": [12345],
    "chunk_ids": ["article:politics:12345:0"],
    "canonical_ids": [99]
  },
  "refusal_key": null
}
```

| Field | Meaning |
|-------|---------|
| `phase` | Writer automation phase or service |
| `method` | Scoring technique |
| `score_parts` | Decomposed confidence |
| `anchors` | Row ids supporting the edge |
| `refusal_key` | Optional `graph_pattern_refusals.endpoint_key` |

## Inference stages (migration 275)

Chemistry model bands on `graph_connection_proposals.inference_stage` (and optional
`graph_connection_links.inference_stage`):

| Stage | Meaning |
|-------|---------|
| `hypothesized` | Random / weak collision (exploration) |
| `candidate` | Stimuli applied (score, review, RAG pull) |
| `established` | Survived — protein edge |
| `quarantined` | Failed stimulus / rejected |

Selective RAG tickets live in `intelligence.rag_evidence_pull_queue` (stimulus, not bulk PDF ingest).

## Link columns (270)

| Column | Purpose |
|--------|---------|
| `source` | Writer phase string (survives proposal delete) |
| `evidence` | Snapshot at materialize / re-score |
| `last_scored_at` | Drift review timestamp |

## Provenance chain

```
proposal.source + proposal.evidence
  → distillation (graph_connection_processor_service)
  → link.source_proposal_id + link.evidence + link.confidence
  → break/quarantine → graph_pattern_refusals
```

## Cross-domain associates

Proposals use `endpoints.left` / `endpoints.right` with `domain_key`, `kind`, `id`.
Materialized links use qualified kinds (`entity:politics`, `storyline:finance`) and
`link_role=associated_cross_domain` so same numeric ids in different silos are not self-loops.

## Related phases

| Phase | Flag (default) | Role |
|-------|----------------|------|
| `embedding_link_candidates` | `EMBEDDING_LINK_CANDIDATES_ENABLED=false` | Cosine-ranked proposals |
| `graph_connection_distillation` | on | Apply proposals → links |
| `graph_link_drift_review` | `GRAPH_LINK_DRIFT_REVIEW_ENABLED=false` | Re-score / quarantine stale edges |
| `storyline_membership_review` | `STORYLINE_MEMBERSHIP_REVIEW_ENABLED=false` | Article decoupling |
| `STORYLINE_MEMBERSHIP_LLM_ENABLED=false` | LLM mid-band on membership queue |

See [PIPELINE_AND_AUTOMATION.md](PIPELINE_AND_AUTOMATION.md) and [STORYLINE_CANONICAL_MODEL.md](STORYLINE_CANONICAL_MODEL.md).
