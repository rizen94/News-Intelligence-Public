# Statuses we should consider when applying reader preferences (covers all quality-assured states).
QUALITY_DOCUMENT_STATUSES = frozenset([
    "package_projected", "desk_promoted", "refined",
    "rag_analyzed", "draft", "auto_seeded",
])