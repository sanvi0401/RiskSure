# RiskSure

RiskSure is a two-part insurance risk assessment project:

- `frontend/` is a Next.js app for the user flow.
- `backend/` is a Flask API that loads the ML model and returns underwriting results.

## Canonical project structure

Use the top-level folders below as the real project:

```text
backend/
  app.py
  retrain_model.py
  requirements.txt
  model/
frontend/
  app/
  components/
  context/
  hooks/
  lib/
  public/
  .env.example
  package.json
PROJECT_ANALYSIS.md
README.md
```

Legacy duplicate folders also exist inside `risksure2 - Copy - Copy/`. They are older copied files and are not needed to run the app.

## High-level analysis

- The frontend implements a multi-step workflow: login, new application, risk, underwriting, premium, final review, and dashboard.
- The backend exposes `GET /`, `GET /health`, `POST /process`, `POST /save`, and `GET /applications`.
- The machine learning model files are already present in `backend/model/`.
- If you install backend dependencies with Python 3.12, run `py -3 retrain_model.py` once so those model files match the installed library versions.
- Saved applications are stored in memory, not in a database. Restarting the backend clears them.
- Frontend API calls are centralized in `frontend/lib/api.ts`, which reads `NEXT_PUBLIC_API_BASE_URL`.

For a more detailed breakdown, see [PROJECT_ANALYSIS.md](./PROJECT_ANALYSIS.md).

## Requirements

- Python 3.10+
- Node.js 18+
- npm

Recommended:

- Python 3.11 is the safest option for this project.
- Python 3.12 works with the version-aware dependency pins in `backend/requirements.txt`.

## Step-by-step run guide

### 1. Open the root folder

```powershell
cd "c:\Users\pc\Downloads\risksure2 - Copy - Copy"
```

### 2. Start the backend

Open terminal 1:

```powershell
cd backend
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
py -3 retrain_model.py
py -3 app.py
```

Expected backend URL:

```text
http://localhost:5000
```

Health check:

```text
http://localhost:5000/health
```

### 3. Start the frontend

Open terminal 2:

```powershell
cd "c:\Users\pc\Downloads\risksure2 - Copy - Copy\frontend"
Copy-Item .env.example .env.local -Force
npm install
npm run dev
```

Expected frontend URL:

```text
http://localhost:3000
```

### 4. Use the application

1. Open `http://localhost:3000`.
2. Go through login.
3. Create a new application.
4. Fill in risk details and calculate the score.
5. Continue through underwriting and premium review.
6. Save the application.
7. Open the dashboard to view saved records.

## Optional: retrain the model

From `backend/`:

```powershell
.venv\Scripts\activate
py -3 retrain_model.py
```

This regenerates:

- `backend/model/insurance_model.pkl`
- `backend/model/insurance_scaler.pkl`
- `backend/model/risk_bounds.pkl`

## Troubleshooting

- If `py` does not work, try `python` instead of `py -3`.
- If `pip install -r requirements.txt` fails on Python 3.12, first run `python -m pip install --upgrade pip setuptools wheel`.
- If the frontend cannot reach the backend, check `frontend/.env.local` and confirm `NEXT_PUBLIC_API_BASE_URL=http://localhost:5000`.
- If you see no saved applications after a restart, that is expected because storage is in memory only.
