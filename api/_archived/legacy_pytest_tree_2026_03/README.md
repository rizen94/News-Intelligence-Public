# Legacy pytest tree (archived 2026-03)

This tree was previously `api/tests/`. **CI** runs `tests/` at the repository root only (`pytest tests/unit/...`).

These files may still run manually with `PYTHONPATH=api uv run pytest api/_archived/legacy_pytest_tree_2026_03/...` but are unmaintained relative to CI. Prefer new tests under `tests/`.
