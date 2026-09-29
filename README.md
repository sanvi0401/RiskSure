# RiskSure

RiskSure is a two-part insurance risk assessment project:

- `frontend/`: Next.js 15 app (login with Google Authenticator, application flow, dashboards).
- `backend/`: Flask API with an XGBoost underwriting model, PostgreSQL via SQLAlchemy, and JWT auth.

In production the browser only talks to the frontend. The frontend proxies
`/api/*` to the backend (see `frontend/next.config.mjs`), so there is no CORS
setup to get wrong.

```text
browser ──► frontend (Vercel)  ──/api/* rewrite──►  backend (Vercel / Docker)  ──►  PostgreSQL (Neon)
```

## Environment files

| File | Used for | Template |
| --- | --- | --- |
| `backend/.env` | Local backend run (gitignored) | `backend/.env.example` |
| `frontend/.env.local` | Local frontend run (gitignored) | `frontend/.env.example` |

In production, put the same variables in your host's dashboard instead of files.

## Run locally

Requirements: Python 3.12, Node.js 18+.

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py            # http://localhost:5001  (5000 is taken by macOS AirPlay)
```

On macOS, `brew install libomp` enables the XGBoost model. Without it the API
still runs and uses a deterministic fallback formula; `/health` shows `model_loaded`.

```bash
cd frontend
npm install
npm run dev              # http://localhost:3000
```

`frontend/.env.local` already points `BACKEND_API_URL` at `http://localhost:5001`.

### First admin account

Public sign-up only creates customers. Create an admin (then promote other staff from the Admin page):

```bash
cd backend && source .venv/bin/activate
flask --app app create-admin --email you@example.com
```

Against production, run the same command locally with `DATABASE_URL` in `backend/.env` set to the production database.

## Deploy to production (Vercel)

Create two Vercel projects from this repository.

### 1. Backend project

- Root Directory: `backend`. It uses `backend/vercel.json`.
- Environment variables (Production):
  - `FLASK_ENV=production`
  - `DATABASE_URL`: your Neon/Postgres connection string
  - `JWT_SECRET_KEY` and `TOTP_ENCRYPTION_KEY`: use the values generated in `backend/.env`
  - `AUTO_CREATE_TABLES=true`
- Deploy, then open `https://<backend>.vercel.app/health/detailed`. It should show `"database": true` and `"model_loaded": true`.

### 2. Frontend project

- Root Directory: `frontend`, Framework: Next.js.
- Environment variables:
  - `NEXT_PUBLIC_API_BASE_URL=/api`
  - `BACKEND_API_URL=https://<backend>.vercel.app` (no trailing slash)
- Deploy. `BACKEND_API_URL` is read at build time, so **redeploy the frontend after changing it**.
- Check `https://<frontend>.vercel.app/api/health`. It should return the backend's JSON.

### Alternative: Docker (Render, Railway, Fly.io, a VPS)

```bash
cd backend
docker build -t risksure-backend .
docker run -p 8000:8000 --env-file .env -e FLASK_ENV=production risksure-backend
```

Then set the frontend's `BACKEND_API_URL` to that service's URL.

## Database schema

With `AUTO_CREATE_TABLES=true` (default) the backend creates missing tables and
widens legacy columns on startup. That is idempotent and suits Vercel, which has
no release step. To manage the schema with migrations instead, set it to `false` and run:

```bash
flask --app app db upgrade        # fresh database
flask --app app db stamp 0001_initial && flask --app app db upgrade   # database created earlier by create_all
```

## Tests

```bash
cd backend && pip install pytest && python -m pytest tests
cd frontend && npm run typecheck && npm run build
```

## Retraining the model

```bash
cd backend
pip install -r requirements-training.txt
python retrain_model.py
```

This regenerates `model/insurance_xgb_model.json`, `model/risk_bounds.pkl` and
`model/feature_metadata.json`. `tests/test_smoke.py` checks that predictions stay plausible.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Frontend shows "Endpoint not found" or 404 on every action | `BACKEND_API_URL` not set on the frontend project, or set after the last build. Set it and redeploy. |
| `/api/health` works but login fails with 500 | Check backend logs. Usually `DATABASE_URL` is unreachable; `/health/detailed` shows `database: false`. |
| Authenticator codes rejected after a redeploy | `TOTP_ENCRYPTION_KEY` changed. It must stay constant once users enrol. |
| Everyone logged out after a redeploy | `JWT_SECRET_KEY` changed. |
| Local frontend gets 403 from `localhost:5000` | That port is macOS AirPlay. The backend runs on 5001. |
| Backend function too large on Vercel | Use the Docker deployment instead. |


## Vercel build optimization

The frontend and backend Vercel projects use `frontend` and `backend` as their Root Directories. Each has an `ignoreCommand` so a change outside that project directory skips its build. Keep `NEXT_PUBLIC_API_BASE_URL=/api` for the frontend proxy and set the frontend project's `BACKEND_API_URL` to the deployed backend URL. Configure the backend `FRONTEND_URL` or `FRONTEND_ORIGINS` with the deployed frontend origin so browser requests are allowed.
