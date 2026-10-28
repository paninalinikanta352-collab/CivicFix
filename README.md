# CivicFix

CivicFix is a civic issue reporting and resolution platform. Residents can submit reports with a photo and location, then track progress. Administrators review and prioritize reports, assign municipal workers, and workers update the status of assigned issues.

## Features

- Account registration and JWT-based login
- Issue reports with a required JPEG, PNG, or WebP photo (up to 8 MB)
- GPS coordinates and an optional address or landmark
- Rule-based risk priority score from 0 to 100
- Optional AI photo-analysis metadata
- Resident issue tracking and status history
- Admin tools for triage, worker creation, assignment, and statistics
- Worker dashboard for assigned issues and progress updates

Risk scores are heuristic priority scores, not calibrated probabilities. The backend calculates them from the issue category, description, and location text; the frontend displays the returned score.

## Technology

- **Frontend:** Next.js 15 and React 18
- **Backend:** Python and FastAPI
- **Database:** SQLite
- **Authentication:** JWT

## Repository layout

    CivicFix/
    ├── Backend/
    │   └── Backend/           # FastAPI application and requirements
    ├── frontend/
    │   └── frontend/          # Next.js application
    ├── TEAM.md                # Team information
    └── start_servers.bat      # Windows launcher

The SQLite database is created at Backend/database/civicfix.db. Uploaded photos are stored under Backend/uploads/. These are local runtime data and should not be committed.

## Run locally on Windows

Open two PowerShell windows from the repository root.

### Start the backend

    cd Backend\Backend
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    Copy-Item .env.example .env

Edit Backend/Backend/.env and set CIVICFIX_SECRET_KEY to a long random value. To create an administrator on first startup, also set CIVICFIX_ADMIN_EMAIL and CIVICFIX_ADMIN_PASSWORD. Keep .env private; it is ignored by Git.

Then start the API:

    python -m uvicorn main:app --reload

The API is at http://localhost:8000; interactive documentation is at http://localhost:8000/docs. Database tables are initialized at startup.

### Start the frontend

In a second window, return to the repository root if needed:

    cd frontend\frontend
    Copy-Item .env.example .env.local
    npm install
    npm run dev

The app is at http://localhost:3000. NEXT_PUBLIC_API_BASE in .env.local defaults to http://localhost:8000.

## Main API routes

| Method | Route | Purpose |
|---|---|---|
| POST | /api/auth/register | Register a resident account |
| POST | /api/auth/login | Log in and receive a token |
| GET | /api/auth/me | Get the signed-in account |
| GET | /api/issues | Browse reports |
| POST | /api/issues | Submit a report (authenticated multipart form with an image) |
| GET | /api/issues/{id} | View a report |
| PATCH | /api/issues/{id} | Edit report details (reporter or admin) |
| GET | /api/issues/{id}/updates | View status history |
| POST | /api/issues/{id}/status | Update status (assigned worker or admin) |
| GET | /api/worker/assignments | List the signed-in worker's assignments |
| GET, POST | /api/admin/workers | List or create worker accounts |
| GET | /api/admin/issues | List reports ordered by risk and age |
| POST | /api/admin/issues/{id}/assign | Assign a report to a worker |
| GET | /api/admin/stats | View issue and worker statistics |
| GET | /api/health | Check API availability |

Issue creation expects title, description, category, optional lat, lng, and address, plus a required image upload. Categories are roads, water, electricity, cleanliness, and other. Statuses are reported, assigned, in_progress, resolved, and rejected.

## Risk display

Use the backend's risk_percentage response field (integer from 0 to 100) and display a label with the number:

- **0–39:** Low
- **40–69:** Medium
- **70–100:** High

The score uses category baselines, description keywords, and sensitive-place terms in the address. Simple keyword rules can misread negation and context.

## Tests

From the backend directory:

    cd Backend\Backend
    python -m unittest discover -s tests -v

## Configuration

Backend settings are listed in Backend/Backend/.env.example:

- CIVICFIX_SECRET_KEY — signing key for JWTs; replace the example value
- CIVICFIX_TOKEN_MINUTES — token lifetime
- CIVICFIX_CORS_ORIGINS — comma-separated allowed frontend origins
- CIVICFIX_ADMIN_EMAIL, CIVICFIX_ADMIN_PASSWORD, and CIVICFIX_ADMIN_NAME — optional initial administrator setup

The frontend setting is NEXT_PUBLIC_API_BASE. Never commit real secrets, local database files, uploaded photos, or environment files.

## Team

See TEAM.md for current team information and roles.
