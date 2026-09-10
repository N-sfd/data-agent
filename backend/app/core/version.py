"""Deployment fingerprint helpers for release certification."""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache
def resolve_git_sha() -> str:
    """Best-effort deployed revision for /ready and smoke fingerprinting.

    Preference order:
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
