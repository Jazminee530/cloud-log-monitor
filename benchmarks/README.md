# Local Load Testing — Cloud Log Monitor

Run repeatable tests against your **own local Docker Compose instance**. This sends synthetic log events to `POST /logs` and queries the Compose PostgreSQL database to count events processed by the background worker. No AWS, paid services, or third-party endpoints are needed.

## Install (Windows PowerShell)

1. Download and extract the add-on ZIP into `C:\Users\jazmi\Documents\cloud-log-monitor-starter`, alongside `compose.yaml`. The add-on adds only new files.
2. Start Docker Desktop and run from the project root:

```powershell
docker compose up -d
curl.exe http://127.0.0.1:8000/health
```

3. Ensure your Python virtual environment has dev dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

4. Start small, then ramp up:

```powershell
.\.venv\Scripts\python.exe benchmarks\load_test.py --sizes 100 --concurrency 10
.\.venv\Scripts\python.exe benchmarks\load_test.py --sizes 1000 --concurrency 10
```

5. **Optional**: If the 1,000-event run finishes correctly and you have sufficient local resources, test 10,000 events (this may take quite a while with one RQ worker):

```powershell
.\.venv\Scripts\python.exe benchmarks\load_test.py --sizes 10000 --concurrency 10 --drain-timeout 1800
```

Do not launch multiple benchmark commands simultaneously. If Docker Desktop is under heavy load, stop at 100 or 1,000 events. You can check worker progress with `docker compose logs --tail 30 worker`.

## Outputs and interpreting the results

Files are written to `benchmarks/results/` (JSON, CSV, and a ready-to-review Markdown report). They're excluded from Git automatically, so you can check them before deciding whether to copy selected results into the main README.

- **API accepted/s:** HTTP 202 responses per second during POST submissions. This is **queue-ingest throughput**, not completed-event throughput.
- **p50/p95/p99 response latency:** API request time in milliseconds, including HTTP response time, **not** the worker processing delay.
- **Persisted events:** Counted from `log_events` in PostgreSQL for that test's unique synthetic `source` value.
- **Alerts:** Counted from `alerts` associated with the same source. One expected alert for each of three simulated patterns out of every four events.
- **End-to-end duration:** Time from starting submissions until all accepted events are persisted (or until the drain timeout).
- **Processed/s:** persisted events / end-to-end duration. This is the **overall pipeline rate for that test**, not instantaneous worker throughput.

**PASS** requires all requests to be accepted and all expected events and alerts to be persisted. The script stops larger tests if the preceding test's queue did not fully drain. Data persists in the local database, and the dashboard only shows the newest 100 events—it isn't a whole-database counter.

A `worker` that spends a long time processing 10,000 events is not necessarily broken: this starter uses RQ and one worker process. Try `docker compose logs worker` to inspect failures. If DB verification fails, check whether the Compose service is still named `db` and whether the database tables remain `log_events` and `alerts`.

## Safety and project notes

- The script rejects nonlocal API URLs. **Do not expose the demo API to the public internet**: it has no authentication or TLS.
- Only synthetic messages are generated. Never use RTX, UT Southwestern, patient, or employer logs.
- Results depend on your machine and worker count; do not claim AWS or production performance.
- A full run writes up to 10,000 records into your existing local database. The script intentionally does **not** delete any data.
- Avoid pushing unreviewed numeric claims to a resume. Once measured, add the test machine, concurrency level, event sizes, and actual results to `README.md`.

## Run unit tests and push the benchmark source

```powershell
.\.venv\Scripts\python.exe -m pytest -v
git add benchmarks tests/test_load_test_helpers.py
git commit -m "Add local load testing and performance reports"
git push origin main
```

These helper tests don't replace the live benchmark. The benchmark must be run against your local Docker Compose application, and its measured metrics should be reported separately from CI unit-test results.
