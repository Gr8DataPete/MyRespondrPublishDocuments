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
1. cd .\frontend\
2. npm run start-ui