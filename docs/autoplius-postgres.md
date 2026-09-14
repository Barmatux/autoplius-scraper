# Autoplius → Postgres (scrape-platform)

Autoplius scraping now runs inside **scrape-platform**. Listings, runs, and `engine_catalog` live in the shared **Postgres** database. SQLite (`autoplius.db`) is deprecated for new scrapes.

## Why

- One control plane (worker / scheduler / UI) for auto24 + autoplius
- One DB consumers can query (`source = 'autoplius'`)
- Photos still go to Yandex Object Storage (`auto160-media`), same as before

```text
autoplius-scraper Flask UI ──► Postgres (scrape-platform)
                                      ▲
scrape-platform worker (adapter=autoplius) ──┘
```

## Connection

Prefer private network / same Docker host / SSH tunnel. Do **not** expose Postgres publicly without firewall rules.

Example DSN (compose on scrape VM exposes `5433→5432`):

```bash
DATABASE_URL=postgresql+psycopg://scrape:scrape@<scrape-host>:5433/scrape
```

Inside scrape-platform compose network:

```bash
DATABASE_URL=postgresql+psycopg://scrape:scrape@db:5432/scrape
```

Env for Autoplius UI / tools should switch from `DB_PATH=.../autoplius.db` to `DATABASE_URL=...`.

## Table mapping (SQLite → Postgres)

| SQLite | Postgres | Notes |
|--------|----------|-------|
| `listings.autoplius_id` | `listings.external_id` + `source='autoplius'` | Surrogate `listings.id` is internal PK |
| `parameters_json` | `listings.parameters` (JSONB) | |
| `photo_urls_json` | `listings.photo_urls` (JSONB) | |
| `manual_overrides_json` | `listings.manual_overrides` (JSONB) | |
| `engine_liters` | `listings.engine_liters` | |
| `scrape_runs.*` counters | `scrape_runs.counters` (JSONB) | Plus `source_id` → sources.key=`autoplius` |
| `run_listings(run_id, autoplius_id)` | `run_listings(run_id, listing_id)` | Join via `listings.external_id` |
| `engine_catalog` | `engine_catalog` | Same unique key `(make, model, engine_label, fuel)` |

Always filter Autoplius rows:

```sql
WHERE source = 'autoplius'
```

## Read contract (Flask UI / analytics)

- Catalog listing ID for Autoplius site = `listings.external_id` (string of former `autoplius_id`)
- Status: `active` / `archived`
- Photos: `photo_url`, `photo_urls` (often `/media/object?key=autoplius/...` served by scrape-platform)
- Admin locks: `manual_overrides` JSON object
- Engine volume denormalized on listing: `engine_liters`; catalog table for customs volumes: `engine_catalog`

Example:

```sql
SELECT external_id AS autoplius_id, title, price_eur, city, status, photo_urls
FROM listings
WHERE source = 'autoplius' AND status = 'active'
ORDER BY last_seen_at DESC NULLS LAST
LIMIT 50;
```

## Write contract

| Who writes | What |
|------------|------|
| **scrape-platform worker** | listings upsert, scrape_runs, run_listings, photo sync |
| **Autoplius Flask UI** (allowed) | `manual_overrides`, admin listing edits, `engine_catalog` customs |
| **autoplius-scraper worker/scheduler** | **must stop** after cutover — do not dual-write SQLite |

Start a scrape via scrape-platform:

```bash
curl -X POST http://<scrape-host>:8000/api/v1/runs \
  -H 'Content-Type: application/json' \
  -d '{"source":"autoplius","config":{"pages":3,"force_full":false}}'
```

Listings API:

```bash
curl 'http://<scrape-host>:8000/api/v1/listings?source=autoplius&status=active&limit=50'
```

## One-shot data migration

1. Copy `autoplius.db` onto the scrape VM (e.g. `/tmp/autoplius.db`).
2. Apply schema: `alembic upgrade head` (includes `0002_autoplius_parity`).
3. Import:

```bash
# from scrape-platform app container / venv with DATABASE_URL set
python scripts/migrate_sqlite.py /tmp/autoplius.db
# optional: --skip-runs  --skip-catalog  --limit 1000
```

Idempotent upserts on `(source, external_id)` and `engine_catalog` unique key. Runs are appended (tagged `trigger=migrated`, `counters.sqlite_run_id`).

4. Disable Autoplius scrape systemd/cron/scheduler on the old host.
5. Point Flask UI at `DATABASE_URL` and verify catalog/admin against Postgres.

## Scrape-platform config (Autoplius)

See `.env.example`:

- `AUTOPLIUS_BASE_URL` (default `https://ru.autoplius.lt`)
- `AUTOPLIUS_INTERVAL_MINUTES`
- `AUTO_CAPTCHA`, `CAPTCHA_2CAPTCHA_API_KEY`
- `TRANSLATE_DESCRIPTIONS`, `TRANSLATE_DELAY_SEC`
- `SEARCH_NEWEST_FIRST`
- Shared scrape/S3 knobs (`SCRAPE_PAGES`, `S3_*`, …)

Seed creates source `autoplius` + default job automatically on API/worker/scheduler start.

## Cutover checklist

- [ ] `alembic upgrade head` on scrape VM
- [ ] Import SQLite with `migrate_sqlite.py`
- [ ] Spot-check `SELECT count(*) FROM listings WHERE source='autoplius'`
- [ ] Manual run from UI (source=autoplius) or API
- [ ] Stop old Autoplius scraper processes
- [ ] Switch UI DSN from `DB_PATH` to `DATABASE_URL`
- [ ] Keep SQLite file as read-only backup for a while
