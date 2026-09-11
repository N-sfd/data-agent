"""Upload size tiers for sync vs background preprocessing guidance."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SizeTier:
    small_mb: int = 10
    medium_mb: int = 50
    large_mb: int = 100


DEFAULT_TIERS = SizeTier()


def classify_upload_size(
    size_bytes: int, *, tiers: SizeTier = DEFAULT_TIERS
) -> str:
    mb = size_bytes / (1024 * 1024)
    if mb < tiers.small_mb:
        return "small"
    if mb < tiers.medium_mb:
        return "medium"
    if mb <= tiers.large_mb:
        return "large"
    return "very_large"


def prefer_background_processing(size_bytes: int) -> bool:
    return classify_upload_size(size_bytes) in {"medium", "large", "very_large"}
