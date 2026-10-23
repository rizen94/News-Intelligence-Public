"""Shared eligibility for content_refinement_queue pending counts / claim."""


def sql_content_refinement_queue_pending(alias: str = "q") -> str:
    """Jobs waiting for a worker (migration 181)."""
    return f"{alias}.status = 'pending'"
