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
import base64

from services.core.auth_service import get_current_user
from database.supabase_helper import supabase_functions

logger = logging.getLogger(__name__)

upload_bp = Blueprint("upload_document", __name__)

# Default bucket name for organization documents
# Prefer the explicit SUPABASE_UPLOAD_BUCKET if provided in .env
DEFAULT_BUCKET = os.getenv("SUPABASE_UPLOAD_BUCKET") or os.getenv("ORG_DOCUMENT_BUCKET") or "organization-documents"
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
    logger.info("Received upload request from %s", request.remote_addr)
    # Always print a concise summary at INFO so it's visible in typical log levels
    try:
        auth_present = bool(request.headers.get("Authorization"))
        content_type_hdr = request.headers.get("Content-Type") or request.content_type
        content_len = request.headers.get("Content-Length")
        # Basic summary for quick debugging (do not print full tokens)
        auth_preview = None
        if auth_present:
            ah = request.headers.get("Authorization")
            auth_preview = ah[:32] + "..." if len(ah) > 36 else ah
        logger.info("Upload summary: Authorization present=%s, Authorization_preview=%s, Content-Type=%s, Content-Length=%s",
                    auth_present, auth_preview, content_type_hdr, content_len)
    except Exception:
        logger.exception("Failed to emit upload summary info")
    # Optional detailed request dump for debugging upload/client issues.
    # Set environment var `DEBUG_UPLOAD_REQUEST=1` to enable detailed logs.
    try:
        debug_enabled = os.getenv("DEBUG_UPLOAD_REQUEST", "1") in ("1", "true", "True")
    except Exception:
        debug_enabled = True
    if debug_enabled:
        try:
            # Log limited headers (avoid printing secrets fully)
            auth_header = request.headers.get("Authorization")
            if auth_header:
                short_auth = auth_header[:20] + "..." if len(auth_header) > 24 else auth_header
            else:
                short_auth = None
            hdrs = {k: (short_auth if k.lower() == "authorization" else v) for k, v in request.headers.items()}
            logger.debug("Upload request headers (partial): %s", hdrs)

            # Log form keys
            try:
                form_keys = list(request.form.keys())
            except Exception:
                form_keys = []
            logger.debug("Upload request form keys: %s", form_keys)

            # Log files metadata (filename, content_type, size when available)
            files_info = {}
            for name, fs in request.files.items():
                try:
                    filename = getattr(fs, "filename", None)
                    ctype = getattr(fs, "content_type", None)
                    size = None
                    # Try to determine size without consuming stream
                    try:
                        cur = fs.stream.tell()
                        fs.stream.seek(0, os.SEEK_END)
                        size = fs.stream.tell()
                        fs.stream.seek(cur)
                    except Exception:
                        try:
                            # Read into memory and restore BytesIO
                            data = fs.read()
                            size = len(data) if data is not None else None
                            from io import BytesIO

                            fs.stream = BytesIO(data if data is not None else b"")
                        except Exception:
                            size = None
                    files_info[name] = {"filename": filename, "content_type": ctype, "size": size}
                except Exception as e:
                    files_info[name] = {"error": str(e)}
            logger.debug("Upload request files: %s", files_info)
        except Exception:
            logger.exception("Failed to dump upload request details")
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

        # Build storage path: orgs/<org_id>/<doc_id><ext>  (removed 'documents' segment per request)
        storage_path = f"orgs/{org_id}/{doc_id}{ext}"

        # Log form fields and file metadata (avoid printing full auth tokens)
        try:
            form_items = {k: request.form.get(k) for k in list(request.form.keys())}
        except Exception:
            form_items = {}

        # Prepare a small sample of file bytes for debugging (base64) — keep small to avoid huge logs
        try:
            sample = None
            if isinstance(content, (bytes, bytearray)) and len(content) > 0:
                sample = base64.b64encode(content[:256]).decode('ascii')
        except Exception:
            sample = None

        # Color helper (green) for terminal output
        GREEN = "\x1b[32m"
        RESET = "\x1b[0m"

        try:
            summary_lines = []
            summary_lines.append(f"{GREEN}Upload Debug Summary{RESET}")
            summary_lines.append(f"  User ID: {GREEN}{form_items.get('user_id') or getattr(user_resp.user, 'id', None)}{RESET}")
            summary_lines.append(f"  Org ID: {GREEN}{org_id}{RESET}")
            summary_lines.append(f"  Doc ID: {GREEN}{doc_id}{RESET}")
            summary_lines.append(f"  Filename: {GREEN}{filename}{RESET}")
            summary_lines.append(f"  Storage Path: {GREEN}{storage_path}{RESET}")
            summary_lines.append(f"  Content-Type: {GREEN}{content_type}{RESET}")
            summary_lines.append(f"  File Size: {GREEN}{len(content) if content is not None else 'n/a'} bytes{RESET}")
            if sample:
                summary_lines.append(f"  File sample (base64, first 256 bytes): {GREEN}{sample}{RESET}")
            if form_items:
                summary_lines.append(f"  Other form fields: {GREEN}{form_items}{RESET}")
            logger.info('\n'.join(summary_lines))
        except Exception:
            logger.exception("Failed to log upload debug summary")

        public_url, error = supabase_functions.upload_file_to_storage(
            DEFAULT_BUCKET, storage_path, content, content_type
        )

        if error:
            logger.error("Upload failed: %s", error)
            return jsonify({"error": "Upload failed", "detail": str(error)}), 500

        # Persist document record using helper
        # Prepare record matching Organization_Documents table
        doc_record = {
            "document_id": doc_id,
            "user_id": getattr(user_resp.user, "id", None),
            "org_id": org_id,
            "filename": filename,
            "storage_path": storage_path,
            "bucket": DEFAULT_BUCKET,
            "content_type": content_type,
            "size_bytes": len(content) if content is not None else None,
            "description": request.form.get("description"),
            # Do NOT set uploaded_at here; let the DB default to now() or the server-side default
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
