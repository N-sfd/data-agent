"""Microsoft Entra ID (Azure AD) JWT validation for API access tokens."""

from __future__ import annotations

import time
from typing import Any

import httpx
from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.rbac import Role

# App role values expected on the Entra app registration (App roles).
DEFAULT_ENTRA_ROLE_MAP: dict[str, Role] = {
    "DataAgent.Admin": "admin",
    "DataAgent.Reviewer": "reviewer",
    "DataAgent.Analyst": "analyst",
    "DataAgent.Viewer": "viewer",
    "Admin": "admin",
    "Reviewer": "reviewer",
    "Analyst": "analyst",
    "Viewer": "viewer",
}

_ROLE_RANK: dict[str, int] = {
    "viewer": 1,
    "analyst": 2,
    "reviewer": 3,
    "service_account": 4,
    "admin": 5,
}

_jwks_cache: dict[str, Any] | None = None
_jwks_fetched_at: float = 0.0
_JWKS_TTL_SECONDS = 3600.0


def entra_issuer(tenant_id: str) -> str:
    return f"https://login.microsoftonline.com/{tenant_id}/v2.0"


def entra_jwks_url(tenant_id: str) -> str:
    return (
        f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    )


def _fetch_jwks(tenant_id: str) -> dict[str, Any]:
    global _jwks_cache, _jwks_fetched_at
    now = time.monotonic()
    if _jwks_cache is not None and (now - _jwks_fetched_at) < _JWKS_TTL_SECONDS:
        return _jwks_cache

    response = httpx.get(entra_jwks_url(tenant_id), timeout=10.0)
    response.raise_for_status()
    _jwks_cache = response.json()
    _jwks_fetched_at = now
    return _jwks_cache


def clear_jwks_cache() -> None:
    global _jwks_cache, _jwks_fetched_at
    _jwks_cache = None
    _jwks_fetched_at = 0.0


def _rsa_key_for_token(token: str, jwks: dict[str, Any]) -> dict[str, Any] | None:
    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        return None
    kid = header.get("kid")
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


def map_entra_roles(claims: dict[str, Any]) -> Role:
    """Pick the highest-privilege mapped role from token claims."""

    settings = get_settings()
    claim_name = settings.entra_role_claim or "roles"
    raw = claims.get(claim_name) or claims.get("roles") or []
    if isinstance(raw, str):
        raw = [raw]

    mapped: list[Role] = []
    for item in raw:
        role = DEFAULT_ENTRA_ROLE_MAP.get(str(item))
        if role:
            mapped.append(role)

    if not mapped:
        return settings.entra_default_role  # type: ignore[return-value]

    return max(mapped, key=lambda role: _ROLE_RANK.get(role, 0))


def validate_entra_access_token(token: str) -> dict[str, Any]:
    """Validate an Entra access token and return claims.

    Raises ``ValueError`` on any validation failure.
    """

    settings = get_settings()
    if not settings.entra_configured:
        raise ValueError("Entra ID is not configured.")

    tenant_id = settings.entra_tenant_id
    audience = settings.entra_api_audience
    assert tenant_id and audience

    try:
        jwks = _fetch_jwks(tenant_id)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Unable to fetch Entra JWKS: {exc}") from exc

    key = _rsa_key_for_token(token, jwks)
    if key is None:
        clear_jwks_cache()
        try:
            jwks = _fetch_jwks(tenant_id)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Unable to refresh Entra JWKS: {exc}") from exc
        key = _rsa_key_for_token(token, jwks)
    if key is None:
        raise ValueError("No matching JWKS key for token kid.")

    issuer = entra_issuer(tenant_id)
    try:
        claims = jwt.decode(
            token,
            key,  # type: ignore[arg-type]
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options={
                "verify_at_hash": False,
            },
        )
    except JWTError as exc:
        raise ValueError(f"Invalid Entra token: {exc}") from exc

    return claims


def claims_to_actor_fields(claims: dict[str, Any]) -> dict[str, Any]:
    oid = str(claims.get("oid") or claims.get("sub") or "").strip()
    if not oid:
        raise ValueError("Entra token missing oid/sub.")

    display = (
        claims.get("name")
        or claims.get("preferred_username")
        or claims.get("upn")
        or claims.get("unique_name")
        or oid
    )
    role = map_entra_roles(claims)
    email_raw = (
        claims.get("preferred_username")
        or claims.get("upn")
        or claims.get("email")
    )
    email = str(email_raw)[:255] if email_raw else None
    return {
        "id": f"entra-{oid}",
        "actor_type": "user",
        "display_name": str(display)[:120],
        "email": email,
        "role": role,
    }


def looks_like_jwt(token: str) -> bool:
    parts = token.split(".")
    return len(parts) == 3 and all(parts)
