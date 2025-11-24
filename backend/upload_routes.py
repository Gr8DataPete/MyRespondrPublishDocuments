"""
Simple upload blueprint for organization-scoped document uploads.
This is a lightweight scaffold demonstrating how to:
 - determine current user's org_id
 - accept a multipart file upload
 - upload to Supabase storage via existing helper
 - persist a simple OrganizationDocuments row using the existing supabase helper

Integrate this blueprint in your main Flask app (register the blueprint).
"""
from flask import Blueprint, request, jsonify
import logging
import uuid
import os

from services.core.auth_service import get_current_user
from database.supabase_helper import supabase_functions

logger = logging.getLogger(__name__)

upload_bp = Blueprint("upload_document", __name__)

# Default bucket name for organization documents
DEFAULT_BUCKET = os.getenv("ORG_DOCUMENT_BUCKET", "organization-documents")
# Server-side validations
# Max upload size: 10 MB by default (can be overridden by ORG_DOC_MAX_BYTES env var)
MAX_FILE_SIZE_BYTES = int(os.getenv("ORG_DOC_MAX_BYTES", str(10 * 1024 * 1024)))
# Allowed MIME types (common document/image types)
ALLOWED_MIME_TYPES = set(
    os.getenv(
        "ORG_DOC_ALLOWED_MIME",
        "application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,image/png,image/jpeg",
    ).split(",")
)


def _resolve_org_id_from_user():
    """Resolve the organization id for the current authenticated user.
    Strategy:
    1) Try the auth user metadata via get_current_user()
    2) Fallback to the UserProfiles table via fetch_user_profiles
    Returns: org_id string or None
    """
    try:
        resp = get_current_user()
        if resp and getattr(resp, "user", None):
            user = resp.user
            # Some Supabase responses keep user_metadata under user.user_metadata
            meta = getattr(user, "user_metadata", None) or {}
            org_id = meta.get("org_id")
            if org_id:
                return org_id
            # fallback to profile
            user_id = user.id
        else:
            user_id = None
    except Exception:
        user_id = None

    try:
        if user_id:
            profile_resp = supabase_functions.fetch_user_profiles({"id": user_id})
            if getattr(profile_resp, "data", None) and len(profile_resp.data) > 0:
                profile = profile_resp.data[0]
                return profile.get("org_id")
    except Exception:
        pass

    return None


@upload_bp.route("/api/organizations/me/documents", methods=["POST"])
def upload_organization_document():
    """Accept a multipart/form-data file upload, store in Supabase storage under org, and record metadata.

    Expected form-data fields:
    - file: the uploaded file
    - description (optional): text describing the document

    Response: JSON with document_id (UUID), storage_path and public_url (if available)
    """
    try:
        # Authenticate
        user_resp = get_current_user()
        if not user_resp or not getattr(user_resp, "user", None):
            return jsonify({"error": "Not authenticated"}), 401

        # Resolve organization for user
        org_id = _resolve_org_id_from_user()
        if not org_id:
            return jsonify({"error": "User is not associated with an organization"}), 403

        if "file" not in request.files:
            return jsonify({"error": "No file uploaded (field name must be 'file')"}), 400

        file = request.files["file"]
        filename = file.filename or "uploaded"
        content_type = file.content_type or "application/octet-stream"

        # Validate MIME type
        if content_type not in ALLOWED_MIME_TYPES:
            return (
                jsonify({
                    "error": "Unsupported media type",
                    "detail": f"Uploaded MIME type '{content_type}' is not allowed",
                }),
                415,
            )

        # Determine size without consuming the stream (seek/tell)
        try:
            stream = file.stream
            # Some file storages may not support seek; fall back to reading size
            stream.seek(0, os.SEEK_END)
            filesize = stream.tell()
            stream.seek(0)
        except Exception:
            # Fallback: read into memory to determine size
            content = file.read()
            filesize = len(content)
            # reset BytesIO
            try:
                from io import BytesIO

                file.stream = BytesIO(content)
            except Exception:
                pass

        if filesize > MAX_FILE_SIZE_BYTES:
            return (
                jsonify({
                    "error": "File too large",
                    "detail": f"Files must be <= {MAX_FILE_SIZE_BYTES} bytes",
                }),
                413,
            )

        # If we haven't read content yet, read it now
        if 'content' not in locals():
            content = file.read()

        # Generate a stable document UUID
        doc_id = str(uuid.uuid4())

        # Preserve extension if present
        _, ext = os.path.splitext(filename)
        ext = ext or ""

        # Build storage path: orgs/<org_id>/documents/<doc_id><ext>
        storage_path = f"orgs/{org_id}/documents/{doc_id}{ext}"

        public_url, error = supabase_functions.upload_file_to_storage(
            DEFAULT_BUCKET, storage_path, content, content_type
        )

        if error:
            logger.error("Upload failed: %s", error)
            return jsonify({"error": "Upload failed", "detail": str(error)}), 500

        # Persist document record using helper
        doc_record = {
            "id": doc_id,
            "org_id": org_id,
            "filename": filename,
            "storage_path": storage_path,
            "public_url": public_url,
            "content_type": content_type,
            "uploaded_by": getattr(user_resp.user, "id", None),
            "created_at": "now()",
            "description": request.form.get("description"),
        }

        try:
            insert_resp = supabase_functions.add_organization_document(doc_record)
            if getattr(insert_resp, "data", None):
                return jsonify({"document_id": doc_id, "public_url": public_url}), 201
            else:
                logger.warning("Document uploaded but DB insert returned no data: %s", insert_resp)
                return jsonify({"document_id": doc_id, "public_url": public_url, "warning": "DB insert may have failed"}), 201
        except Exception as e:
            logger.exception("Failed to persist document record using add_organization_document: %s", e)
            # Still return uploaded URL but surface the persistence issue
            return jsonify({"document_id": doc_id, "public_url": public_url, "warning": "DB insert failed"}), 201

    except Exception as e:
        logger.exception("Unexpected error in upload endpoint: %s", e)
        return jsonify({"error": str(e)}), 500
