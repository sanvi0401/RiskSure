# Project Analysis

## 1. What this project is

RiskSure is a small full-stack underwriting demo with:

- a `Next.js` frontend in `frontend/`
- a `Flask` backend in `backend/`
- a pre-trained insurance model in `backend/model/`

The app collects applicant information, calculates a risk score, derives a premium, and saves the final application in backend memory.

## 2. Functional flow

The frontend flow is:

1. `login`
2. `new-application`
3. `risk`
4. `underwriting`
5. `premium`
6. `final`
7. `dashboard`

State is shared through `frontend/context/application-context.tsx`.

## 3. Backend analysis

Main backend file: `backend/app.py`

Responsibilities:

- loads the ML model, scaler, and risk bounds from `backend/model/`
- enables permissive CORS headers for local frontend access
- calculates underwriting results in `POST /process`
- stores submitted applications in an in-memory list in `POST /save`
- returns saved applications in `GET /applications`
- exposes `GET /health` for a quick server check

Important limitation:

- saved applications are not persisted to disk or a database

Supporting backend file: `backend/retrain_model.py`

Responsibilities:

- creates synthetic training data
- trains a linear regression model
- saves model artifacts back into `backend/model/`

## 4. Frontend analysis

Key frontend areas:

- `frontend/app/`: route pages
- `frontend/components/`: layout and UI components
- `frontend/context/`: shared application state
- `frontend/lib/api.ts`: backend base URL and endpoints

Notable behavior:

- the frontend uses `NEXT_PUBLIC_API_BASE_URL` from `.env.local`
- if backend calls fail in some pages, the UI falls back to simulated success values instead of hard failing

That makes the UI easier to demo, but it can hide real backend issues during development.

## 5. Structure issues found

### Good parts

- top-level `frontend/` and `backend/` are already clean and runnable
- API endpoint configuration is centralized
- model files are already present

### Issues

- a duplicate legacy copy exists under `risksure2 - Copy - Copy/`
- the project name at the filesystem level is noisy because of repeated `Copy` suffixes
- there is no database or persistent storage
- no automated test suite is present
- backend logic, storage, and API are all in one file

## 6. Recommended structure to treat as correct

Keep using this structure:

```text
backend/
frontend/
README.md
PROJECT_ANALYSIS.md
```

Treat this as legacy and ignore it during normal development:

```text
risksure2 - Copy - Copy/
```

## 7. Suggested next cleanup steps

If you want to improve the project further, the best next steps are:

1. Rename the root project folder to something simpler like `risksure2`.
2. Move the duplicate legacy copy into an `archive/` folder or delete it after backup.
3. Split `backend/app.py` into routes, services, and model-loading modules.
4. Add persistent storage using SQLite or PostgreSQL.
5. Add frontend and backend tests.
6. Add a single command runner such as a root `start` script or `docker-compose.yml`.

## 8. Exact commands to run

Backend:

```powershell
cd "c:\Users\pc\Downloads\risksure2 - Copy - Copy\backend"
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
py -3 retrain_model.py
py -3 app.py
```

Frontend:

```powershell
cd "c:\Users\pc\Downloads\risksure2 - Copy - Copy\frontend"
Copy-Item .env.example .env.local -Force
npm install
npm run dev
```
