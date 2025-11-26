"""Supabase-backed authentication helper.

Implements `get_current_user()` by validating a Bearer JWT against the
Supabase Auth endpoint (`/auth/v1/user`). The endpoint returns the user
profile when a valid JWT is provided. On success this function returns an
object with a `.user` attribute (matching the shape expected by
`upload_routes.py`).

If no Authorization header is present the function returns `None`.
"""

from types import SimpleNamespace
from flask import request
import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("auth_service")


def _supabase_auth_url():
    # Prefer explicit upload URL for auth if provided, fall back to SUPABASE_URL
    return (
        os.getenv("SUPABASE_URL")
        or os.getenv("SUPABASE_URL_DEV")
        or os.getenv("SUPABASE_URL_PROD")
    )


def get_current_user():
    """Return a namespace with `.user` on valid Bearer token, else None.

    The frontend typically sends session JWT in the Authorization header.
    This helper calls Supabase `/auth/v1/user` to validate the token and
    returns a simple namespace with the user object on success.
    """
    auth_header = request.headers.get("Authorization") or request.headers.get(
        "authorization"
    )
    if not auth_header:
        logger.info("get_current_user: no Authorization header present")
        return None

    # Accept Bearer tokens or raw tokens
    token = None
    try:
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(None, 1)[1].strip()
        else:
            token = auth_header.strip()
    except Exception:
        logger.exception("Failed to parse Authorization header")
        return None
    supabase_url = _supabase_auth_url()
    if not supabase_url:
        return None

    url = f"{supabase_url}/auth/v1/user"
    # Prefer sending apikey header alongside Authorization for some Supabase setups
    apikey = (
        os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_KEY_DEV")
        or os.getenv("SUPABASE_KEY_PROD")
    )
    headers = {"Authorization": f"Bearer {token}"}
    if apikey:
        headers["apikey"] = apikey

    try:
        logger.info(
            "Verifying token with Supabase auth endpoint: %s (token preview=%s)",
            url,
            (token[:12] + "...") if token else None,
        )
        resp = requests.get(url, headers=headers, timeout=5)
        logger.info("Supabase /auth/v1/user response: status=%s", resp.status_code)
        text = resp.text
        # Try to parse minimal user fields for logging (do not log tokens)
        try:
            j = resp.json()
            uid = j.get("id") if isinstance(j, dict) else None
            email = j.get("email") if isinstance(j, dict) else None
            logger.info("Supabase returned user id=%s email=%s", uid, email)
        except Exception:
            logger.debug("Supabase /auth/v1/user response text: %s", text)

        if resp.status_code != 200:
            return None

        user_json = resp.json()
        # user_json shape follows Supabase Auth user object
        return SimpleNamespace(user=SimpleNamespace(**user_json))
    except Exception:
        logger.exception("Exception while calling Supabase /auth/v1/user")
        return None
