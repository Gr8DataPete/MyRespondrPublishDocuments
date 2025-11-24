**Upload Document scaffold**

**Overview**
- **Purpose:** Minimal scaffold for uploading organization-scoped documents and persisting a small document record.
- **Intent:** Demonstrates server-side org resolution, file upload to storage, and a lightweight frontend uploader component.

**Repository Structure**
- **`backend/upload_routes.py`**: Python API routes (upload endpoints).
- **`frontend/index.html`**: Static entry for the UI (simple demo or integration point).
- **`frontend/env-config.js`**: Frontend environment configuration (generated/consumed by build or scripts).
- **`frontend/OrganizationDocumentUploader.tsx`**: React/TSX uploader component used by the demo UI.
- **`server/index.mjs`**: Small Node server (may be used to serve the UI or act as a lightweight proxy).
- **`scripts/generate_frontend_env.mjs`**: Helper to generate frontend environment files.
- **`scripts/login_and_print_org.mjs`**: Helper script used to log in and print an example org id (utility/testing).
- **`setup/*.sql`**: SQL schema files to create the required DB tables.

**Quick Start (recommended minimal checks)**
1. Inspect `backend/upload_routes.py` to confirm the Python framework (Flask/FastAPI). Create a virtual environment and install requirements if present:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# If you have a requirements.txt
pip install -r requirements.txt
```

2. Run the backend (example commands depending on framework):

```powershell
# Flask (if the file defines a blueprint/app):
# set FLASK_APP=backend.upload_routes
# flask run

# FastAPI (if it exports an ASGI app named `app`):
# pip install "uvicorn[standard]"
# uvicorn backend.upload_routes:app --reload --port 8000
```

3. Serve the frontend for local testing (quick options):

```powershell
# Quick static serve (Node http-server)
npx http-server ./frontend -p 8080

# Or with Python
cd frontend
python -m http.server 8080
```

4. Configure environment values used by the frontend: edit `frontend/env-config.js` or run `scripts/generate_frontend_env.mjs` if you prefer an automated approach.

**Environment & configuration**
- The frontend reads `env-config.js` for runtime values (API base, keys, etc.).
- The backend likely expects DB and storage configuration (check env vars referenced in `backend/upload_routes.py`).
- The `setup` SQL files create the DB tables referenced by the scaffold; run them against your Postgres if you want to bootstrap the schema.

**Potentially Removable / Optional Files**
- **`server/index.mjs`** — May be unnecessary if you serve the frontend statically and run the Python backend directly. Keep it if you rely on a Node proxy or static server.
- **`scripts/generate_frontend_env.mjs`** and **`scripts/login_and_print_org.mjs`** — Helpful automation, but optional. If you never use them you can archive or remove them.
- Nothing in the repository looks _definitively_ useless from filenames alone; removal should be based on whether the file is referenced by your run/deploy workflow. I recommend running a quick search for imports/usages before deleting.

**How I can help next**
- I can scan the repo to find which files are not referenced (imports, calls, or npm scripts) and provide a safe list of candidates to remove.
- I can update the backend run instructions once you confirm the Python framework used in `backend/upload_routes.py`.
- I can wire up a tiny `package.json` + `npm` scripts for serving the frontend if you want smoother local dev.

If you want me to automatically check for unused files now, say "Please scan for unused files" and I'll run a usage search and return a precise list and suggested deletions.
