"""One-off: create or update a real admin actor for the Admin Session Key
control on the /api-keys page (until full Entra SSO login is wired up).

Run locally with your own DATABASE_URL — never paste that value into
chat. Uses the same api_key_hash scheme as app/core/auth.py (sha256
hex digest), so no dependency on the backend package itself.

Usage (PowerShell):
    $env:DATABASE_URL = "postgresql+psycopg://...your-current-connection-string..."
    $env:ADMIN_API_KEY = "choose-a-long-random-secret-yourself"
    python seed_admin_actor.py

Optional:
    $env:ADMIN_ACTOR_ID = "admin"          # default: "admin"
    $env:ADMIN_DISPLAY_NAME = "Admin"      # default: "Admin"
"""
import hashlib
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

ACTOR_ID = os.environ.get("ADMIN_ACTOR_ID", "admin").strip()
DISPLAY_NAME = os.environ.get("ADMIN_DISPLAY_NAME", "Admin").strip()
API_KEY = os.environ.get("ADMIN_API_KEY", "").strip()

if not API_KEY:
    sys.exit(
        "Set ADMIN_API_KEY in your shell first — choose your own long, "
        "random secret (this script does not generate one for you)."
    )
if len(API_KEY) < 20:
    sys.exit("ADMIN_API_KEY looks too short to be a real secret (< 20 chars).")

KEY_HASH = hashlib.sha256(API_KEY.encode("utf-8")).hexdigest()

db_url = os.environ.get("DATABASE_URL", "").strip()
if not db_url:
    sys.exit("Set DATABASE_URL in your shell first (not this script).")

engine = create_engine(db_url)
with engine.begin() as conn:
    conn.execute(
        text(
            """
            INSERT INTO actors (id, actor_type, display_name, email, role, api_key_hash, active, created_at)
            VALUES (:id, 'user', :display_name, NULL, 'admin', :key_hash, true, :now)
            ON CONFLICT (id) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                role = 'admin',
                api_key_hash = EXCLUDED.api_key_hash,
                active = true
            """
        ),
        {
            "id": ACTOR_ID,
            "display_name": DISPLAY_NAME,
            "key_hash": KEY_HASH,
            "now": datetime.now(timezone.utc),
        },
    )

print(f"OK — actor '{ACTOR_ID}' seeded with role=admin.")
print("Paste your ADMIN_API_KEY value into the Admin Session Key box on /api-keys.")
print(f"Revoke later with: DELETE FROM actors WHERE id = '{ACTOR_ID}';")
