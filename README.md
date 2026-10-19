# Shortly - URL Shortener

Django + DRF + PostgreSQL + Redis + Celery + JWT + Docker

## Run

    cp .env.example .env        # then edit SECRET_KEY and POSTGRES_PASSWORD
    docker compose up --build

API: http://localhost:8000/api/ · Admin: `docker compose exec web python manage.py createsuperuser`

## Try it

    # 1. register + login
    curl -X POST localhost:8000/api/auth/register/ -H 'Content-Type: application/json' \
         -d '{"username":"ram","password":"S3cure-pass-9"}'
    curl -X POST localhost:8000/api/auth/token/ -H 'Content-Type: application/json' \
         -d '{"username":"ram","password":"S3cure-pass-9"}'      # -> {"access": "...", "refresh": "..."}

    # 2. create a short link (optional: custom_alias, expires_at)
    curl -X POST localhost:8000/api/urls/ -H "Authorization: Bearer $TOKEN" \
         -H 'Content-Type: application/json' -d '{"original_url":"https://example.com/very/long/path"}'

    # 3. open it (public, no auth)
    curl -i localhost:8000/<short_code>/       # 302 + Location header

    # 4. manage / analytics
    GET    /api/urls/                    list yours (paginated)
    GET    /api/urls/<code>/stats/       total clicks, last 30 days per day, top referers
    PATCH  /api/urls/<code>/             {"is_active": false} or {"expires_at": "..."}
    DELETE /api/urls/<code>/

## Endpoints

| Method | Path | Auth |
|---|---|---|
| POST | /api/auth/register/ | no |
| POST | /api/auth/token/ , /api/auth/token/refresh/ | no |
| GET/POST | /api/urls/ | JWT |
| GET/PATCH/DELETE | /api/urls/<code>/ | JWT (owner only) |
| GET | /api/urls/<code>/stats/ | JWT (owner only) |
| GET | /<code>/ | public redirect |
| GET | /healthz/ | public |

## Tests (no Docker needed)

    pip install -r requirements.txt
    USE_SQLITE=1 CELERY_TASK_ALWAYS_EAGER=1 python manage.py test

## Design decisions

- **Redirect hot path**: Redis `GET` -> 302. DB is touched only on a cache miss. If Redis is down, it falls back to the DB.
- **Analytics**: the view only enqueues a Celery task; the worker inserts a `ClickEvent` and does an atomic `F()` increment. If the broker is down, the redirect still works (one click event is lost).
- **Short codes**: 7 random base62 chars via `secrets` (not sequential IDs, so links can't be enumerated); collision -> retry.
- **302, not 301**: 301 is cached by browsers, so later clicks would never reach you and analytics would undercount.
- **Cache consistency**: PATCH/DELETE invalidate the key; TTL never exceeds `expires_at`.
- **Validation**: only http/https, links to this service itself are rejected (redirect loops), reserved aliases blocked.
- **JWT**: access 15 min, refresh 7 days. DRF throttling (60/min anon, 120/min user) is shared across workers through Redis.

## Not included yet (good next steps)

Negative caching of 404s, `click_count` batching (Redis INCR + periodic flush), ClickEvent partitioning/retention, GeoIP + user-agent parsing, Sentry/Prometheus, CI, HTTPS/reverse proxy (nginx/Caddy).
