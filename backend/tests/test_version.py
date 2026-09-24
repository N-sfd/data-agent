"""Regression: /version must describe the running process's own startup
snapshot, never a value recomputed against whatever the repo's current
HEAD happens to be at request time (the exact gap that let a stale
uvicorn process misreport a commit it never actually loaded)."""

from app.core import version as version_module


def test_version_metadata_has_required_fields() -> None:
    metadata = version_module.get_version_metadata()
    assert set(metadata) == {"app_version", "git_commit_sha", "build_id", "started_at"}
    assert metadata["git_commit_sha"]
    assert metadata["started_at"]


def test_version_metadata_is_captured_once_not_recomputed_per_call() -> None:
    first = version_module.get_version_metadata()
    second = version_module.get_version_metadata()
    assert first == second
    assert first["started_at"] == version_module.STARTED_AT
    assert first["git_commit_sha"] == version_module.GIT_COMMIT_SHA


def test_resolve_git_sha_matches_module_level_snapshot() -> None:
    assert version_module.resolve_git_sha() == version_module.GIT_COMMIT_SHA
