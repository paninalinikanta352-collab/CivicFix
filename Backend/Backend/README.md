# CivicFix backend

FastAPI and SQLite API for civic issue reporting, admin assignment, and worker progress tracking.

## Run locally (PowerShell)

The Python source and `requirements.txt` are in `CivicFix\Backend\Backend`. In PowerShell:

    cd C:\Users\panin\OneDrive\Documents\CivicFix\Backend\Backend
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    python -m uvicorn main:app --reload

The app reads local settings from `.env` in this folder. `.env.example` lists the available settings. The real `.env` is ignored by Git. Set `CIVICFIX_ADMIN_EMAIL` and `CIVICFIX_ADMIN_PASSWORD` in `.env` before first startup if you want to create an initial admin account.

The database is stored at `CivicFix\Backend\database\civicfix.db`. Uploaded photos are stored at `CivicFix\Backend\uploads` and served at `/uploads/<filename>`. Issue creation accepts JPEG, PNG, or WebP photos up to 8 MB. Interactive API docs are at http://127.0.0.1:8000/docs.

## Main routes

- `POST /api/auth/register`, `POST /api/auth/login`; `GET /api/auth/me`
- `GET /api/issues` and `GET /api/issues/{id}` are public
- `POST /api/issues` requires a user token and accepts multipart fields `title`, `description`, `category`, optional `lat`, `lng`, and `address`, plus required file field `image`; the response includes `photo_url`
- `PATCH /api/issues/{id}` requires a user token
- `GET /api/issues/{id}/updates` shows status history
- `POST /api/issues/{id}/status` is available to the assigned worker or an admin
- `POST /api/admin/workers` creates workers; `GET /api/admin/workers` lists them
- `GET /api/admin/issues` sorts by risk and age; `POST /api/admin/issues/{id}/assign` assigns a worker
- `GET /api/admin/stats` returns dashboard counts

New registrations always receive the user role. Admins create worker accounts. Categories: roads, water, electricity, cleanliness, other. Statuses: reported, assigned, in_progress, resolved, rejected.

Risk percentage is currently an explainable keyword heuristic in `ai_service.py`, not a trained AI model.
