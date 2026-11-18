# Adrobot

Adrobot is a FastAPI + SQLAlchemy application for creating Keitaro campaigns and editing offers in existing campaign streams.

## Features

- Creates a campaign with a country-filtered Google redirect stream and a fallback offer stream.
- Loads domains, campaign groups, traffic sources, and offers from Keitaro.
- Displays current names for saved campaigns from Keitaro and lets administrators delete offers from Keitaro.
- Opens any existing campaign by its Keitaro ID.
- Stages offer and stream changes locally; only the explicit save command writes them to Keitaro.
- Keeps the first stream as the undeletable base stream and highlights pending changes in yellow.
- Balances offer shares to 100% while respecting pinned shares and reserving at least 1% per unpinned offer.
- Shows per-offer clicks, conversions, revenue, and CR for a selected reporting period.

Deleting an offer from the homepage permanently removes the offer object via the Keitaro Admin API. This is different from removing an offer from one campaign stream and may affect every campaign using that offer. Keitaro may reject deletion when the offer is still in use.

## Requirements

- Python 3.11 (recommended; use a stable Python release)
- A Keitaro instance and an Admin API key with access to campaigns, streams, offers, and reports.

## Setup (Windows PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `KEITARO_URL` to the Keitaro host (without `/admin_api/v1`) and add the Admin API key to `.env`. Never commit `.env` or paste a live key into source files. Optionally set the default domain, group, and source IDs; otherwise choose them in the campaign form.

## Database migrations

Apply migrations before starting the application:

```powershell
alembic upgrade head
```

To create a migration after changing SQLAlchemy models:

```powershell
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

The default database is SQLite at `./adrobot.db`. Set `DATABASE_URL` to another SQLAlchemy URL to use a different database.

## Run

```powershell
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. Interactive API documentation is available at <http://127.0.0.1:8000/docs>.

## Keitaro API compatibility

The integration is contained in `app/keitaro/client.py`. Keitaro Admin API versions can differ in accepted stream and report payload shapes; if the API documentation in your instance specifies different fields or endpoint names, update this adapter and its payload tests. The application returns upstream failures as HTTP 502 responses rather than silently pretending an operation succeeded.

## Tests

```powershell
pytest
```
