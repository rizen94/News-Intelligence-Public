"""Minimal FastAPI app for NRI health and lookup stubs."""

from fastapi import FastAPI

from nri_core.spine.api.lookup import get_entity, match_mention

app = FastAPI(title="News Review Investigator API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "nri-api"}


@app.get("/entities/{entity_id}")
def entity_lookup(entity_id: str) -> dict:
    result = get_entity(entity_id)
    if result is None:
        return {"found": False, "entity_id": entity_id}
    return {"found": True, "entity": result}


@app.get("/match")
def mention_match(q: str, schema: str | None = None, limit: int = 5) -> dict:
    return {"query": q, "candidates": match_mention(q, schema=schema, limit=limit)}
