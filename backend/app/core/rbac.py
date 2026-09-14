"""RBAC roles and permission matrix for Data Agent.

Roles
-----
admin           Full control including users, providers, Oracle send
reviewer        View, source inspect, accept/edit/reject, export
analyst         Upload, extract, view; draft edit; no approve/send
viewer          Read-only repository/results (no review/export/send)
service_account API-only scoped extraction/export (and send if granted)
"""

from __future__ import annotations

from typing import Final, Literal

Role = Literal[
    "admin",
    "reviewer",
    "analyst",
    "viewer",
    "service_account",
]

Permission = Literal[
    "documents.view",
    "documents.upload",
    "documents.delete",
    "extraction.run",
    "fields.edit_draft",
    "review.accept",
    "review.edit",
    "review.reject",
    "export.read",
    "export.authoritative",
    "oracle.preview",
    "oracle.send",
    "admin.users",
    "admin.providers",
    "admin.integrations",
]

ROLE_PERMISSIONS: Final[dict[Role, frozenset[Permission]]] = {
    "admin": frozenset(
        {
            "documents.view",
            "documents.upload",
            "documents.delete",
            "extraction.run",
            "fields.edit_draft",
            "review.accept",
            "review.edit",
            "review.reject",
            "export.read",
            "export.authoritative",
            "oracle.preview",
            "oracle.send",
            "admin.users",
            "admin.providers",
            "admin.integrations",
        }
    ),
    "reviewer": frozenset(
        {
            "documents.view",
            "documents.upload",
            "extraction.run",
            "fields.edit_draft",
            "review.accept",
            "review.edit",
            "review.reject",
            "export.read",
            "export.authoritative",
            "oracle.preview",
            # no oracle.send, no admin.*
        }
    ),
    "analyst": frozenset(
        {
            "documents.view",
            "documents.upload",
            "extraction.run",
            "fields.edit_draft",
            "export.read",
            "oracle.preview",
            # no review.accept/reject (draft edit only via fields.edit_draft)
            # no oracle.send, no admin.*
        }
    ),
    "viewer": frozenset(
        {
            "documents.view",
            # stricter governance: no export, no review, no send
        }
    ),
    "service_account": frozenset(
        {
            "documents.view",
            "documents.upload",
            "extraction.run",
            "export.read",
            "export.authoritative",
            "oracle.preview",
            "oracle.send",
        }
    ),
}


def role_has_permission(role: str, permission: Permission) -> bool:
    perms = ROLE_PERMISSIONS.get(role)  # type: ignore[arg-type]
    if perms is None:
        return False
    return permission in perms
