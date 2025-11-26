"""Minimal Flask app to run the upload blueprint locally.

This file is optional: if you prefer to run the Node `server/index.mjs` that ships
with the repo you do not need this file. Use this app to run the Python/Flask
backend on `http://localhost:5000` and keep frontend running separately on
`http://localhost:5173`.

The app attempts to register `upload_routes.upload_bp`. If imports inside that
module fail (missing local helpers), the app will register fallback endpoints
which return a helpful 501 message.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import logging
import traceback
import requests

app = Flask(__name__)
# Configure CORS explicitly for local development so browsers allow Authorization and credentials.
# Allow common local dev origins and enable credentials so `fetch(..., credentials: 'include')` succeeds.
local_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
]

CORS(
    app,
    resources={r"/api/*": {"origins": local_origins}},
    supports_credentials=True,
    allow_headers=[
        "Content-Type",
        "Authorization",
        "apikey",
        "X-Requested-With",
        "Accept",
    ],
    expose_headers=["Content-Type", "Authorization", "apikey"],
)

# Configure structured logging to stdout for local development and CI
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("backend")


@app.before_request
def log_request_summary():
    try:
        method = request.method
        path = request.path
        remote = request.remote_addr
        content_type = request.headers.get("Content-Type") or request.content_type
        content_length = request.headers.get("Content-Length")
        auth = request.headers.get("Authorization")
        auth_present = bool(auth)
        auth_preview = (auth[:32] + "...") if auth and len(auth) > 36 else auth
        logger.info(
            "Incoming request: %s %s from %s; Content-Type=%s; Content-Length=%s; Authorization present=%s; AuthPreview=%s",
            method,
            path,
            remote,
            content_type,
            content_length,
            auth_present,
            auth_preview,
        )
    except Exception:
        logger.exception("Failed to log request summary")


# If the blueprint import fails, capture the import error text here so
# fallback view functions can safely reference it even when the Flask
# reloader restarts the process.
import_error = None
try:
    # upload_routes is the blueprint provided in this repo
    from upload_routes import upload_bp

    app.register_blueprint(upload_bp)
    logger.info("Registered upload_routes blueprint")
except Exception:
    # If the blueprint cannot be imported (missing helper modules), provide
    # stable fallback endpoints so the server can run and respond safely.
    import_error = traceback.format_exc()
    logger.exception("Could not register upload_routes blueprint")


@app.route("/api/signin", methods=["POST"])
def signin_not_configured():
    # Implement a simple Supabase sign-in flow here so the frontend can call
    # `/api/signin` regardless of whether the Node demo server is used.
    # This endpoint accepts JSON { email, password } and forwards to
    # Supabase Auth to get a user/session.
    from flask import request

    try:
        data = request.get_json() or {}
        email = data.get("email")
        password = data.get("password")
        if not email or not password:
            return jsonify({"error": "email and password required"}), 400

        # Determine Supabase URL and anon key for sign-in
        supabase_url = (
            os.getenv("SUPABASE_URL")
            or os.getenv("SUPABASE_URL_DEV")
            or os.getenv("SUPABASE_URL_PROD")
        )
        supabase_anon = (
            os.getenv("SUPABASE_KEY")
            or os.getenv("SUPABASE_KEY_DEV")
            or os.getenv("SUPABASE_KEY_PROD")
        )
        if not supabase_url or not supabase_anon:
            logger.error("Supabase URL/key not configured")
            return jsonify({"error": "Supabase not configured on server"}), 500

        auth_url = f"{supabase_url}/auth/v1/token?grant_type=password"
        headers = {"apikey": supabase_anon, "Content-Type": "application/json"}
        resp = requests.post(
            auth_url,
            headers=headers,
            json={"email": email, "password": password},
            timeout=10,
        )
        if resp.status_code >= 400:
            try:
                return jsonify(resp.json()), resp.status_code
            except Exception:
                return jsonify(
                    {"error": "Sign-in failed", "detail": resp.text}
                ), resp.status_code

        session = resp.json()
        user = session.get("user") or {}

        # Resolve org_id via UserProfiles
        org_id = None
        try:
            from database.supabase_helper import supabase_functions

            profile_resp = supabase_functions.fetch_user_profiles(
                {"id": user.get("id")}
            )
            if getattr(profile_resp, "data", None) and len(profile_resp.data) > 0:
                profile = profile_resp.data[0]
                org_id = profile.get("org_id")
        except Exception:
            logger.exception("Error resolving org_id for user")

        logger.info(
            "Sign-in successful for user id=%s org_id=%s", user.get("id"), org_id
        )
        return jsonify(
            {
                "success": True,
                "user": {"id": user.get("id"), "email": user.get("email")},
                "org_id": org_id,
                "session": session,
            }
        ), 200
    except Exception:
        logger.exception("Unexpected error in /api/signin")
        return jsonify({"error": "Unexpected server error"}), 500


if import_error is not None:

    @app.route("/api/organizations/me/documents", methods=["POST"])
    def upload_not_configured():
        logger.warning(
            "/api/organizations/me/documents called but backend not fully configured"
        )
        return jsonify(
            {
                "error": "Backend not fully configured: upload_routes import failed.",
                "detail": import_error,
            }
        ), 501


@app.route("/api/debug/import_error", methods=["GET"])
def debug_import_error():
    """Development helper: returns the import error traceback for debugging.

    WARNING: Only enabled for local development. Do not expose in production.
    """
    if import_error is None:
        return jsonify({"import_error": None}), 200
    return jsonify({"import_error": import_error}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"Starting Flask dev server on http://{host}:{port}")
    app.run(host=host, port=port, debug=True)
