# NIFTY Options Analytics + BankNifty Data Pipeline

Local prototype for daily BankNifty OHLCV ingestion, CSV options-chain analytics, and a dashboard with PCR, max pain, IV smile, and open-interest distribution.

**Current scope:** input arrives through standardized CSV files. A live market-data provider, public hosting target, and production-scale performance benchmark have not been selected. This project does not place trades or provide investment advice. See [the architecture and data model](docs/architecture.md) for design details and [resume-safe project bullets](docs/resume-bullets.md) for accurate project summaries.

## Requirements

- Python 3.14.x
- Git

## Local setup (PowerShell)

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
Copy-Item .env.example .env
```

The direct application dependency pins are in `pyproject.toml`; `requirements.lock` records the fully resolved runtime environment. For tests and quality tools, install `requirements-dev.lock`, then install the project with `python -m pip install --no-deps -e ".[test,quality]"`. Refresh lock files after deliberate dependency changes and review the resulting diff.

## Configuration and data

Local settings go in `.env`, copied from `.env.example`. Do not commit `.env`, API credentials, or database files. Raw and processed data folders are ignored by Git; retain only synthetic or redistributable fixtures in version control.

## Git workflow

Start work from `main`, create a short-lived branch (`feat/...` or `fix/...`), make focused commits, and merge through a reviewed pull request. Keep generated data and local configuration out of commits.

## Project layout

```text
src/nifty_options/
  ingestion/        Standardized CSV readers
  validation/       Price and option-chain input contracts
  indicators/       Daily SMA and RSI calculations
  analytics/        PCR, max pain, IV smile, OI distribution
  storage/          DuckDB schema and idempotent writes
  reliability/      Bounded HTTPS client for a future data provider
  observability.py  JSON logs, quality summaries, optional failure webhook
  scheduler.py      Optional weekday CSV import thread
  dashboard/        Streamlit dashboard
data/raw/           Local source files, ignored
data/processed/     Local derived data, ignored
```

## CSV input contract

Options-chain CSV is long form, one row per snapshot, expiry, strike, and option type. Required columns: `snapshot_at`, `underlying`, `expiry`, `strike`, `option_type`, `open_interest`, `iv`, and `underlying_price`. `option_type` accepts `CE`/`CALL` or `PE`/`PUT`. Optional columns: `change_in_oi`, `volume`, `bid`, `ask`, and `last_price`. Column names are case-insensitive; spaces and hyphens are normalized to underscores. `snapshot_date`, `underlying_symbol`, `oi`, `vol`, and `last` are accepted aliases.

Daily prices use columns `trade_date` (or `date`), `symbol`, `open`, `high`, `low`, `close`, and `volume`.

## Reliability and local configuration

The loader rejects missing/invalid columns, duplicate keys, impossible OHLC ranges, non-finite numbers, and files over `MAX_CSV_BYTES` (default 100 MiB). `.env` accepts only validated log levels and bounded numeric settings. Pipeline writes use one DuckDB transaction and roll back together on failure. Logs omit request URLs, query strings, and headers.

## Monitoring, alerts, and data quality

The pipeline and dashboard emit one JSON log object per line to stdout, including a run ID, start/completion/failure event, duration, imported row counts, input date/snapshot coverage, option-side counts, and call/put open-interest totals. Missing price input and snapshots missing either calls or puts are logged as non-fatal data-quality warnings. Invalid schema, duplicate keys, impossible price ranges, and non-finite or out-of-range values reject the import before database writes. For a local run, logs print in the terminal; in Docker, inspect them with `docker compose logs -f dashboard`.

To receive pipeline-failure alerts, set `ALERT_WEBHOOK_URL` to a private HTTPS incoming-webhook endpoint in `.env` or the deployment secret store. Alerts include only the run ID and error type. The URL is never written to logs. Delivery failure is itself logged and does not hide the pipeline error. No webhook is configured by default. The Compose health check reports whether Streamlit is serving; it does not replace log collection or alert delivery.

## Performance and caching

The dashboard reads option analytics metadata for selectors/history, then queries only the selected snapshot's option-chain rows and the selected symbol's latest indicator rows. Streamlit caches these reads for up to five minutes, with DuckDB and WAL file metadata in the cache key so imports invalidate cached results promptly. Cache entries are bounded to 32 per query. The max-pain calculation uses grouped open-interest prefix/suffix sums rather than rescanning every contract for every strike. Price imports recompute indicators only for symbols present in the batch and store results from each symbol's earliest changed date forward; full history for those symbols is still read to preserve the Wilder RSI calculation and correctly update later values after a correction. DuckDB primary keys enforce uniqueness and support the existing idempotent replacement writes; extra indexes are deferred until representative production-sized data exists to measure their trade-off.

`nifty_options.reliability.http.HttpClient` is ready for a future provider adapter. It requires HTTPS, applies a timeout and per-client minimum request interval, caps response size, and retries timeouts/network failures plus HTTP 408, 425, 429, and selected 5xx statuses with exponential backoff. It honors a bounded `Retry-After` header when supplied. Provider-specific authentication and rate-limit limits remain to be set with the chosen data source.

Configurable settings and defaults are listed in `.env.example`.

| Setting | Default | Purpose |
| --- | --- | --- |
| `DATABASE_PATH` | `data/nifty_options.duckdb` | DuckDB database path |
| `LOG_LEVEL` | `INFO` | Minimum application log level |
| `ALERT_WEBHOOK_URL` | unset | Optional HTTPS failure-alert endpoint; keep secret |
| `MAX_CSV_BYTES` | `104857600` | Maximum input CSV size (100 MiB) |
| `HTTP_TIMEOUT_SECONDS` | `15` | Timeout for the future provider HTTP client |
| `HTTP_MAX_ATTEMPTS` | `4` | Maximum provider-client attempts |
| `HTTP_MIN_INTERVAL_SECONDS` | `1` | Minimum interval between requests per client |
| `HTTP_MAX_RESPONSE_BYTES` | `26214400` | Maximum provider response size (25 MiB) |
| `SCHEDULER_ENABLED` | `false` | Enable the in-process weekday CSV importer |
| `SCHEDULER_TIME` | `18:15` | Scheduled time in `Asia/Kolkata` |
| `OPTIONS_CSV` | `data/raw/options.csv` | Scheduler options-chain input path |
| `PRICES_CSV` | `data/raw/prices.csv` | Optional scheduler price input path |

Relative paths resolve from the project root. Keep `.env` out of version control and set webhook values through the host's secret store for deployments.

## Tests

After installing the development environment described above, run `python -m pytest`. `requirements-dev.lock` records the fully resolved test and quality-tool environment; `requirements.lock` remains the runtime-only lock.

## Code quality

Run `python -m ruff check .`, `python -m ruff format --check .`, and `python -m mypy src/nifty_options`. Install the local Git hooks once with `python -m pre_commit install`; the hooks lint/fix and format changed Python files and type-check the source package. Use [docs/review-checklist.md](docs/review-checklist.md) during pull-request review.

## Continuous integration

The GitHub Actions workflow in `.github/workflows/ci.yml` runs on every push and pull request using Python 3.14. It installs the locked development environment, runs lint/format/type checks and tests, then builds a wheel. The workflow requires the repository to be pushed to GitHub before GitHub Actions can execute it.

## Run the MVP pipeline and dashboard

```powershell
# Use the redistributable synthetic option-chain fixture for a first run.
New-Item -ItemType Directory -Force data/raw | Out-Null
Copy-Item tests/fixtures/options_chain.csv data/raw/options.csv
python -m nifty_options.pipeline --options-csv data/raw/options.csv --prices-csv data/raw/prices.csv
streamlit run src/nifty_options/dashboard/app.py
```

The price file is optional; until a market-data provider is selected, the pipeline accepts daily OHLCV through this CSV contract. Omit `--prices-csv` when you do not have a price file. Re-importing the same snapshot or daily instrument/date replaces those rows in DuckDB. The dashboard displays PCR history, max-pain history, the selected snapshot's IV smile and OI by strike, plus the latest stored price indicators when price data has been imported. The fixture contains synthetic options data and should not be represented as live market data.

Run checks locally after installing development dependencies:

```powershell
python -m ruff check .
python -m ruff format --check .
python -m mypy src/nifty_options
python -m pytest
```

## Docker deployment and scheduled imports

The included Docker image runs as an unprivileged user. Docker Compose persists the DuckDB file and CSV inputs in `./data`, keeps the app bound to `127.0.0.1:8501` by default, and includes a health check. For a hosted setup, run this Compose stack on a Linux server and put a TLS reverse proxy in front of the local port; on Linux, make `data/` writable by UID/GID 1000 before starting the container.

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

Open `http://localhost:8501`. To enable the in-process weekday import scheduler, set `SCHEDULER_ENABLED=true` and `SCHEDULER_TIME=18:15` in `.env`, then restart the service. It reads `OPTIONS_CSV` and, when present, `PRICES_CSV`; missing options input is skipped. Paths are relative to the project root (`data/raw/options.csv` and `data/raw/prices.csv` by default). The CSVs must be placed or refreshed by an external source process. The project still has no selected market-data provider, so this schedule imports available files but does not fetch market data itself. Exchange holidays are harmless when no fresh file is supplied, but holiday calendars are not built in.

Scheduling runs as a thread inside the Streamlit process. The dashboard and scheduler therefore access DuckDB from the same process, which matches DuckDB's supported write-concurrency model. Do not run a separate writer container against the same database while the dashboard is open. For a one-off manual import, stop the dashboard first, run the pipeline container, then start the dashboard again:

```powershell
docker compose stop dashboard
docker compose run --rm --no-deps dashboard python -m nifty_options.pipeline --options-csv /app/data/raw/options.csv --prices-csv /app/data/raw/prices.csv
docker compose start dashboard
```

## Vercel deployment

Vercel's Python Functions runtime expects a Python web-handler entrypoint. This Streamlit script starts its own server, so it is not a Python Function entrypoint. For Vercel's container deployment, the repository includes a root-level `Dockerfile.vercel`; it starts Streamlit on `PORT=8501`. Keep Vercel's project **Root Directory** set to the repository root and set the Vercel project environment variable `PORT` to `8501`, then push a commit containing `Dockerfile.vercel` and redeploy. The CI workflow builds this image as well as the local Compose image.

The Vercel image packages `examples/demo_options.csv` and imports it into DuckDB during the image build, so a fresh deployment opens with sample analytics. The dashboard labels this dataset **SYNTHETIC DEMO DATA**; it is illustrative and is not live market data. The bundled database is a demo snapshot, not durable storage for user imports or current market data. For a live deployment, configure a durable external database and a separate data-import process. Do not enable the in-process scheduler on Vercel. See [architecture and data model](docs/architecture.md#technology-choices-and-trade-offs) for the storage trade-offs.

