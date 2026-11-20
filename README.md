# Cloud Log Monitor — runnable local starter

Python REST API that receives synthetic logs, puts work on a Redis-backed queue, saves events in PostgreSQL, and raises rule-based alerts for suspicious messages. Built as an **educational local project**, not a production SIEM.

## Stack

- **FastAPI** — REST API and interactive docs
- **PostgreSQL + SQLAlchemy** — event and alert storage
- **Redis + RQ** — asynchronous background jobs, immediate retries
- **Docker Compose** — starts all four services together
- **pytest + GitHub Actions** — unit tests on every push or PR

## Requirements

- Docker Desktop with Docker Compose enabled (Windows, macOS, or Linux)
- Port **8000** free on your computer
- No AWS account required for the local version

## Run it in Windows PowerShell

From the folder containing `compose.yaml`:

```powershell
docker compose up --build -d
docker compose ps
```

Once the `api` and other services are healthy, visit:

- http://localhost:8000/docs — interactive Swagger API UI
- http://localhost:8000/health — database and Redis check
- http://localhost:8000/logs — processed events
- http://localhost:8000/alerts — generated alerts

### Send synthetic logs

```powershell
docker compose exec api python scripts/send_demo_logs.py
```

This submits one ordinary log and three suspicious messages. After the worker processes them, open `http://localhost:8000/alerts` to see rule-based detections. You can also open `/docs`, click **POST /logs**, select **Try it out**, and submit:

```json
{
  "event_id": "my-demo-001",
  "source": "web-server",
  "level": "WARNING",
  "message": "Failed login for user test"
}
```

A successful response is **202 Accepted** with a `job_id`, which means queued (not yet processed). Poll **GET /jobs/{job_id}**; once finished, inspect **GET /alerts**. Repeating the same `event_id` won't make a second database record.

### View logs or stop

```powershell
docker compose logs -f worker
docker compose down
```

Press `Ctrl+C` to exit the log viewer. `docker compose down` stops the containers **without deleting** stored data. To deliberately delete local database and queue data, use `docker compose down -v`.

## Run tests locally (optional Python 3.12 setup)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The tests mock the Redis job queue and do not need Docker. CI is configured in `.github/workflows/tests.yml`.

## GitHub setup

1. Create a repository, e.g. `cloud-log-monitor` (or use a **new branch** of your existing log-analyzer repository).
2. Add the files in this folder, preserving their paths, including `.github/workflows/tests.yml`.
3. Do not commit `.env`, credentials, real hospital/employer logs, patient information, or proprietary data.
4. Commit and push. GitHub Actions runs the unit tests automatically; the API **does not run on GitHub itself**. Start Docker Desktop and run `docker compose up --build -d` locally.

If you have an existing log parser, integrate it with `app/detector.py` or `app/tasks.py` after the starter works; don't replace your working project without a branch or backup.

## Project architecture

```text
POST /logs --> FastAPI --> Redis/RQ queue --> RQ worker
                                             |-- PostgreSQL log_events
                                             `-- rule detector --> PostgreSQL alerts
GET /logs, /alerts, /jobs/{id} --> FastAPI
```

## Known limitations / next steps

- Detection is keyword-based; it is **not** machine learning or a mature security detection engine.
- No dashboard UI beyond Swagger and JSON endpoints.
- No authentication, TLS, retention policy, rate limiting, or production-grade migrations: **do not expose this API to the public internet**.
- Secrets in `.env.example` are illustrative local defaults, not safe production credentials.
- Add integration/load tests, structured logging, metrics, authentication, secure deployment, and infrastructure-as-code *before* claiming a cloud deployment on your resume.
- AWS deployment is **not included** and will require its own infrastructure and cost monitoring.
