"""Deployment fingerprint helpers for release certification.

Quality-gate finding: the previous implementation resolved the git SHA
lazily (on first call, via `@lru_cache`) by shelling out to `git
rev-parse HEAD` against the repo's CURRENT working tree. In local
development that means `/version` can report a commit newer than what the
running process actually has loaded in memory — a stale `uvicorn`
process left over from an earlier session confirmed this: `/version`
kept reporting the latest commit on disk while serving old, pre-fix
extraction logic. All of the metadata below is captured exactly once, at
module import time (i.e. process startup) — editing files after the
process has started can never change what `/version` reports.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _read_git_sha() -> str:
    """Preference order:
    1. Explicit GIT_SHA (Docker build-arg / CI)
    2. Render / Vercel injected commit envs
    3. Local ``git rev-parse HEAD`` when a .git directory is present
    """

    for key in (
        "GIT_SHA",
        "RENDER_GIT_COMMIT",
        "VERCEL_GIT_COMMIT_SHA",
        "SOURCE_VERSION",
        "COMMIT_REF",
    ):
        value = (os.environ.get(key) or "").strip()
        if value:
            return value[:40]

    repo_root = Path(__file__).resolve().parents[3]
    git_dir = repo_root / ".git"
    if git_dir.exists():
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()[:40]
        except (OSError, subprocess.SubprocessError):
            pass

    return "unknown"


def _read_build_id(git_commit_sha: str, started_at: str) -> str:
    """Prefer an explicit CI/host-provided build identifier; fall back to
    a value derived from what this process actually has (its resolved
    commit + the moment it started), never recomputed later."""

    for key in ("RENDER_DEPLOY_ID", "BUILD_ID", "VERCEL_DEPLOYMENT_ID"):
        value = (os.environ.get(key) or "").strip()
        if value:
            return value
    return f"{git_commit_sha[:12]}@{started_at}"


# Captured exactly once, at import time (process startup) — never
# recomputed on a later request, so `/version` always describes the
# artifact this process actually loaded, not whatever is on disk now.
STARTED_AT: str = datetime.now(timezone.utc).isoformat()
GIT_COMMIT_SHA: str = _read_git_sha()
BUILD_ID: str = _read_build_id(GIT_COMMIT_SHA, STARTED_AT)
APP_VERSION: str = (os.environ.get("APP_VERSION") or "").strip() or GIT_COMMIT_SHA[:12]


def resolve_git_sha() -> str:
    """Back-compat accessor for the startup-captured commit SHA."""

    return GIT_COMMIT_SHA


def get_version_metadata() -> dict[str, str]:
    """Full startup-captured fingerprint for `/version` and smoke tests."""

    return {
        "app_version": APP_VERSION,
        "git_commit_sha": GIT_COMMIT_SHA,
        "build_id": BUILD_ID,
        "started_at": STARTED_AT,
    }
