"""Load .env and apply catch-up defaults for operator scripts."""

from __future__ import annotations

from pathlib import Path


def bootstrap_catchup(*, repo_root: Path | None = None, bulk_active: bool = False) -> Path:
    """Load repo .env (if present) and apply :mod:`config.catchup_defaults`."""
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent.parent
    env_file = repo_root / ".env"
    if env_file.is_file():
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)
    from config.catchup_defaults import apply_catchup_env_defaults

    apply_catchup_env_defaults(bulk_active=bulk_active)
    return repo_root
