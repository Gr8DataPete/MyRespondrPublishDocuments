**Project**
 -: Minimal demo for uploading organization documents using a Flask backend and a small frontend. The backend uses Supabase REST APIs for Auth, Storage and PostgREST operations.

**How To Run**

- **Frontend:**

	From the repository root, run:

	```powershell
	cd frontend
	npm install
	npm run dev
	```

	This serves the frontend (default demo) on `http://localhost:5173`.

- **Backend:**

	From the repository root, run:

	```powershell
	cd backend
	uv sync
	uv run pythonapp.py
	```

	Note: The above backend commands are provided as requested. If your backend entrypoint is `app.py` (the repository contains `app.py`), run:

	```powershell
	cd backend
	uv sync
	uv run app.py
	```

**Environment**

- Set Supabase-related env vars in a `.env` file or your environment when running locally:
	- `SUPABASE_URL`, `SUPABASE_KEY` (auth / PostgREST)
	- `SUPABASE_UPLOAD_URL`, `SUPABASE_UPLOAD_KEY`, `SUPABASE_UPLOAD_BUCKET` (storage / upload DB)

**Ports**

- Frontend: `5173` (http-server dev port)
- Backend: `5000` (Flask default when running `app.py`)

**Notes**

- Use `npm run format:check` in `frontend` to verify formatting (uses `prettier`). If `prettier` isn't installed locally, the script uses `npx` to run it temporarily.
- Backend formatting is enforced by `ruff`. Run `uv sync` then `uv run ruff format --check .` inside `backend` to verify formatting, or `uv run ruff format .` to auto-fix.


