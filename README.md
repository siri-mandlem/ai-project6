# Open Shelf Library Management System

A deployable library app for managing a book catalog, student accounts, loans, returns, and late-return fines.

## Features

- First account signup bootstraps the library administrator; later signups are student accounts.
- Secure password hashing and session-based authentication.
- Admin book catalog management and issue-to-student workflow.
- Students can search the catalog, issue available books, and review/return their own loans.
- Loan due dates default to 14 days. Late returns create an unpaid fine at `$0.50` per overdue day.
- Admins and students can review fines and mark them paid.
- PostgreSQL/Neon deployment and SQLite local development.

## Run locally

Python 3.11 or newer is recommended.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
$env:SECRET_KEY = "set-a-long-random-secret"
$env:DATABASE_URL = "sqlite:///library.db"
python -m flask --app backend.app run
```

Open `http://127.0.0.1:5000`. The first account registered becomes the library administrator. Create student accounts afterward.

## Deploy to Render

The deployment service uses:

- Build command: `pip install -r backend/requirements.txt`
- Start command: `gunicorn --bind 0.0.0.0:$PORT backend.app:app`

Set `DATABASE_URL` to a PostgreSQL connection URL and `SECRET_KEY` to a unique, randomly generated value in the Render environment. The deployment workflow supplies the Neon database URL and creates the required PostgreSQL tables from `database/schema.sql`. The app also runs `db.create_all()` during startup so it can initialize a fresh compatible database.

Optional settings:

- `LOAN_PERIOD_DAYS` — loan duration in days (default `14`).
- `FINE_PER_DAY` — late fine per day (default `0.50`).

`/health` is a liveness check and `/ready` verifies database connectivity. Never commit production secrets or use a development secret in a public deployment.

## API overview

- `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`
- `GET /api/books?q=...`, `POST /api/books` (admin)
- `GET /api/issues`, `POST /api/issues`, `POST /api/issues/<id>/return`
- `GET /api/fines`, `POST /api/fines/<id>/pay`
- `GET /api/dashboard`

Run the smoke tests from the project root with `python -m unittest discover -s tests`.
