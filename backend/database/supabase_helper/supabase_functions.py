"""Supabase-backed helpers using the Supabase HTTP API (PostgREST + Auth + Storage).

This module uses the REST endpoints of Supabase to:
- query `UserProfiles`
- upload files to Supabase Storage (PUT to storage object)
- insert rows into `Organization_Documents` via PostgREST

It expects environment variables to be present (loaded from `.env`) and
prefers `SUPABASE_UPLOAD_URL`/`SUPABASE_UPLOAD_KEY` for storage operations and
`SUPABASE_URL`/`SUPABASE_KEY` (service role) for PostgREST/inserts.

NOTE: Using the service role key in server-side code is acceptable for
trusted backend environments. Do NOT expose service-role keys to browsers.
"""

import os
import requests
import json
import logging
from types import SimpleNamespace
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _supabase_base():
    return (
        os.getenv("SUPABASE_URL")
        or os.getenv("SUPABASE_URL_DEV")
        or os.getenv("SUPABASE_URL_PROD")
    )


def _supabase_key():
    # Prefer an explicit server key (service role / upload key)
    return (
        os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_KEY_DEV")
        or os.getenv("SUPABASE_KEY_PROD")
    )


def _upload_base():
    return os.getenv("SUPABASE_UPLOAD_URL") or _supabase_base()


def _upload_key():
    return os.getenv("SUPABASE_UPLOAD_KEY") or _supabase_key()


def fetch_user_profiles(filters):
    """Query UserProfiles table via PostgREST.

    `filters` is expected to be a dict like {"id": <user_id>}.
    Returns a SimpleNamespace with `.data` attribute (list of rows) to match
    the shape used by the existing code.
    """
    base = _supabase_base()
    key = _supabase_key()
    if not base or not key:
        return SimpleNamespace(data=[])

    # Build simple eq filter for id if provided
    params = None
    if isinstance(filters, dict) and filters.get("id"):
        user_id = filters.get("id")
        params = {"id": f"eq.{user_id}"}

    url = f"{base}/rest/v1/UserProfiles"
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=5)
        if resp.status_code in (200, 206):
            return SimpleNamespace(data=resp.json())
        return SimpleNamespace(data=[])
    except Exception:
        return SimpleNamespace(data=[])


def upload_file_to_storage(bucket, storage_path, content, content_type):
    """Upload file bytes to Supabase Storage object endpoint.

    Tries the Supabase Storage PUT endpoint using the `SUPABASE_UPLOAD_KEY`.
    On failure, falls back to writing the file under `backend/uploads/` and
    returns a `file://` URL.

    Returns: (public_url, error)
    """
    upload_base = _upload_base()
    upload_key = _upload_key()

    # Ensure bytes
    data = (
        content
        if isinstance(content, (bytes, bytearray))
        else (content.encode("utf-8") if content is not None else b"")
    )

    if upload_base and upload_key:
        try:
            # Use PUT to write the object at the given path
            url = f"{upload_base}/storage/v1/object/{bucket}/{storage_path}"
            # Include both Authorization and apikey headers — Supabase often requires both for server-side uploads
            headers = {
                "Authorization": f"Bearer {upload_key}",
                "apikey": upload_key,
                "Content-Type": content_type,
            }
            resp = requests.put(url, headers=headers, data=data, timeout=15)
            if 200 <= resp.status_code < 300:
                # Public URL pattern (public path)
                public_url = (
                    f"{upload_base}/storage/v1/object/public/{bucket}/{storage_path}"
                )
                return public_url, None
            # Log and surface error details for easier debugging
            logger.error(
                "Supabase storage upload failed: %s %s", resp.status_code, resp.text
            )
            return None, f"Storage upload failed: {resp.status_code} {resp.text}"
        except Exception as e:
            logger.exception("Exception during Supabase storage upload: %s", e)
            # proceed to fallback
            pass

    # Fallback: write to local uploads directory
    uploads_dir = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
    uploads_dir = os.path.abspath(uploads_dir)
    os.makedirs(uploads_dir, exist_ok=True)
    safe_name = storage_path.replace("/", "_").replace("..", "_")
    out_path = os.path.join(uploads_dir, safe_name)
    try:
        with open(out_path, "wb") as f:
            f.write(data)
        return f"file://{out_path}", None
    except Exception as e:
        return None, str(e)


def add_organization_document(doc_record):
    """Insert `doc_record` into `Organization_Documents` via PostgREST.

    Returns a SimpleNamespace with `.data` containing the inserted row(s) on success.
    """
    # Use the upload-specific Supabase project (DB) when available
    base = _upload_base()
    key = _upload_key()
    if not base or not key:
        return SimpleNamespace(data=None)

    url = f"{base}/rest/v1/Organization_Documents"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    # Log which Supabase base/key we are using for the insert (do not print full key)
    try:
        logger.info(
            "add_organization_document using base=%s (key_preview=%s...)",
            base,
            (key[:12] if key else None),
        )
    except Exception:
        pass
    try:
        # Try sending as an array (bulk insert) first — some clients use this pattern
        resp = requests.post(
            url, headers=headers, data=json.dumps([doc_record]), timeout=10
        )
        if 200 <= resp.status_code < 300:
            try:
                return SimpleNamespace(data=resp.json())
            except Exception:
                return SimpleNamespace(data=None)

        # Log failure details for debugging
        try:
            logger = logging.getLogger(__name__)
            logger.error(
                "PostgREST insert failed (array body): %s %s",
                resp.status_code,
                resp.text,
            )
        except Exception:
            pass

        # Fallback: try sending a single object (some PostgREST setups prefer this)
        try:
            resp2 = requests.post(
                url, headers=headers, data=json.dumps(doc_record), timeout=10
            )
            if 200 <= resp2.status_code < 300:
                try:
                    return SimpleNamespace(data=resp2.json())
                except Exception:
                    return SimpleNamespace(data=None)
            try:
                logger.error(
                    "PostgREST insert failed (single object): %s %s",
                    resp2.status_code,
                    resp2.text,
                )
            except Exception:
                pass
        except Exception:
            pass

        return SimpleNamespace(data=None)
    except Exception as e:
        try:
            logging.getLogger(__name__).exception(
                "Exception during add_organization_document: %s", e
            )
        except Exception:
            pass
        return SimpleNamespace(data=None)
