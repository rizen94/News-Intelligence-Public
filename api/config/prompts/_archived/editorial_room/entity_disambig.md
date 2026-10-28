# Editorial room — entity disambiguation (T2)

Resolve ambiguous entity pairs in confidence band 0.55–0.72. Programmatic T0/T1 already ran.

## Input

You receive pairs with `source_name`, `target_name`, `confidence`, `reason`, and mention counts.

## Rules

1. Merge only when the same real-world entity is clearly intended.
2. Never merge role-word umbrellas ("executives", "officials") with named persons.
3. Write a vault entity card reference when uncertain — do not auto-merge below 0.72 confidence.

## Output JSON

```json
{
  "actions": [
    {
      "type": "entity_disambig",
      "domain_key": "politics",
      "keep_id": 10,
      "merge_id": 22,
      "confidence": 0.71,
      "rationale": "Trump / Donald Trump same person",
      "apply_merge": false
    }
  ]
}
```
