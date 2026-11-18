# Adrobot

Adrobot is a FastAPI + SQLAlchemy application for creating Keitaro campaigns and editing offers in existing campaign streams.

## Features

- Creates a campaign with a country-filtered Google redirect stream and a fallback offer stream.
- Loads domains, campaign groups, traffic sources, and offers from Keitaro.
- Opens any existing campaign by its Keitaro ID.
- Stages offer and stream changes locally; only the explicit save command writes them to Keitaro.
- Keeps the first stream as the undeletable base stream and highlights pending changes in yellow.
- Balances offer shares to 100% while respecting pinned shares and reserving at least 1% per unpinned offer.
- Shows per-offer clicks, conversions, revenue, and CR for a selected reporting period.

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

## Administrator login

The app has one administrator account configured outside the source code. Generate an Argon2 password hash:

```powershell
.\.venv\Scripts\python.exe -m app.password_hash
```

Set the generated hash in `ADMIN_PASSWORD_HASH`, choose `ADMIN_USERNAME`, and set a persistent random `SESSION_SECRET_KEY` in `.env`. Generate the session key with:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Do not put the plain administrator password in `.env`. Sessions use a signed, HTTP-only, SameSite=Lax cookie and expire after eight hours. Set `SESSION_COOKIE_SECURE=true` when serving the site through HTTPS; keep it `false` for local HTTP development.

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

Open <http://127.0.0.1:8000> and sign in. Interactive API documentation at <http://127.0.0.1:8000/docs> is also protected by login.

## Deployment to `adrobot.iversdev.ru` (Ubuntu + Nginx)

The local deployment branch is `deploy/adrobot-nginx`. Push it to the configured remote after committing the changes:

```powershell
git push -u origin deploy/adrobot-nginx
```

The repository includes an HTTP reverse-proxy config at `deploy/nginx/adrobot.iversdev.ru.conf` and a systemd unit at `deploy/systemd/adrobot.service`. Before deploying, point the domain's DNS A record at the server's public IP and allow inbound ports 80 and 443.

On the Ubuntu server:

```bash
sudo apt update
sudo apt install -y git nginx certbot python3-certbot-nginx python3-venv
sudo adduser --system --group --home /opt/adrobot --shell /usr/sbin/nologin adrobot
sudo -u adrobot git clone -b deploy/adrobot-nginx <GIT_REPOSITORY_URL> /opt/adrobot
sudo -u adrobot python3 -m venv /opt/adrobot/.venv
sudo -u adrobot /opt/adrobot/.venv/bin/pip install -r /opt/adrobot/requirements.txt
sudo mkdir -p /etc/adrobot /var/lib/adrobot
sudo chown adrobot:adrobot /var/lib/adrobot
```

Create `/etc/adrobot/adrobot.env` with the Keitaro URL and API key, `ADMIN_USERNAME`, the Argon2 `ADMIN_PASSWORD_HASH`, and a persistent random `SESSION_SECRET_KEY`. Use:

```text
DATABASE_URL=sqlite:////var/lib/adrobot/adrobot.db
SESSION_COOKIE_SECURE=true
```

Generate the password hash with `/opt/adrobot/.venv/bin/python -m app.password_hash` from `/opt/adrobot`, and generate the session key with `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`. Store the env file securely:

```bash
sudo chown root:adrobot /etc/adrobot/adrobot.env
sudo chmod 640 /etc/adrobot/adrobot.env
```

Install and enable the provided service and Nginx site:

```bash
sudo cp /opt/adrobot/deploy/systemd/adrobot.service /etc/systemd/system/adrobot.service
sudo cp /opt/adrobot/deploy/nginx/adrobot.iversdev.ru.conf /etc/nginx/sites-available/adrobot.iversdev.ru
sudo ln -s /etc/nginx/sites-available/adrobot.iversdev.ru /etc/nginx/sites-enabled/adrobot.iversdev.ru
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable --now adrobot nginx
sudo certbot --nginx -d adrobot.iversdev.ru
sudo systemctl restart adrobot
```

The systemd service binds Uvicorn to localhost, runs Alembic migrations before startup, and writes SQLite data only under `/var/lib/adrobot`. Nginx proxies the site, rate-limits login attempts, and Certbot configures HTTPS. Check service logs with `sudo journalctl -u adrobot -f`. Port 8000 should not be exposed publicly.

## Keitaro API compatibility

The integration is contained in `app/keitaro/client.py`. Keitaro Admin API versions can differ in accepted stream and report payload shapes; if the API documentation in your instance specifies different fields or endpoint names, update this adapter and its payload tests. The application returns upstream failures as HTTP 502 responses rather than silently pretending an operation succeeded.

## Tests

```powershell
pytest
```
