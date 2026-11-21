"""Local-only load test for Cloud Log Monitor.

Uses real POST /logs requests, then counts rows in PostgreSQL through Docker
Compose to distinguish queued acceptance from completed background processing.
Only synthetic data; never send real workplace or patient logs.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
from urllib.parse import urlparse
from uuid import uuid4

import httpx


MESSAGES = (
    ("INFO", "Routine health check passed", False),
    ("WARNING", "Failed login for benchmark test account", True),
    ("ERROR", "Permission denied while reading synthetic test file", True),
    ("ERROR", "Connection refused while contacting synthetic test service", True),
)
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def require_loopback(base_url: str) -> str:
    """Refuse remote hosts: the demo API has no authentication."""
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Only local HTTP URLs (localhost/127.0.0.1/[::1]) are allowed")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ValueError("Use a plain base URL, for example http://127.0.0.1:8000")
    return base_url.rstrip("/")


def event_for(source: str, index: int) -> tuple[dict, bool]:
    level, message, should_alert = MESSAGES[index % len(MESSAGES)]
    return (
        {
            "event_id": f"{source}-{index:06d}",
            "source": source,
            "level": level,
            "message": message,
        },
        should_alert,
    )


def percentile(values: list[float], percent: int) -> float | None:
    """Nearest-rank percentile, expressed in milliseconds."""
    if not values:
        return None
    ranked = sorted(values)
    return round(ranked[max(0, math.ceil(percent / 100 * len(ranked)) - 1)], 2)


def parse_counts(text: str) -> tuple[int, int]:
    # PostgreSQL unaligned row looks like 100|75.
    lines = [line.strip() for line in text.splitlines()]
    for line in reversed(lines):
        match = re.fullmatch(r"(\d+)\|(\d+)", line)
        if match:
            return int(match.group(1)), int(match.group(2))
    raise ValueError(f"Unexpected PostgreSQL count output: {text[:150]!r}")


def db_counts(source: str, timeout_seconds: int = 30) -> tuple[int, int]:
    """Query only this test run; handles existing demo records safely."""
    if not re.fullmatch(r"loadtest-[a-z0-9-]{1,50}", source):
        raise ValueError("Invalid benchmark source identifier")

    sql = (
        "SELECT "
        f"(SELECT count(*) FROM log_events WHERE source = '{source}'), "
        f"(SELECT count(*) FROM alerts a JOIN log_events l ON l.event_id = a.event_id WHERE l.source = '{source}');"
    )
    # POSTGRES_USER / POSTGRES_DB are supplied inside the DB container.
    command = [
        "docker", "compose", "exec", "-T", "db", "sh", "-c",
        'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -c "$1"',
        "sh", sql,
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            timeout=timeout_seconds, check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Docker CLI was not found; start Docker Desktop and run from the project root") from exc
    if result.returncode != 0:
        raise RuntimeError(f"PostgreSQL count command failed: {result.stderr.strip()[:400]}")
    return parse_counts(result.stdout)


async def send_events(base_url: str, source: str, total: int, concurrency: int) -> dict:
    work = asyncio.Queue()
    for i in range(total):
        work.put_nowait(i)

    timings_ms: list[float] = []
    failures: Counter[str] = Counter()
    accepted = 0
    expected_alerts = 0

    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(20.0),
        limits=httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency),
    ) as client:
        async def submitter():
            nonlocal accepted, expected_alerts
            while True:
                try:
                    i = work.get_nowait()
                except asyncio.QueueEmpty:
                    return
                event, should_alert = event_for(source, i)
                began = time.perf_counter()
                try:
                    response = await client.post("/logs", json=event)
                    elapsed_ms = (time.perf_counter() - began) * 1000
                    timings_ms.append(elapsed_ms)
                    if response.status_code == 202:
                        accepted += 1
                        expected_alerts += int(should_alert)
                    else:
                        failures[f"HTTP {response.status_code}"] += 1
                except (httpx.HTTPError, OSError) as exc:
                    failures[type(exc).__name__] += 1
                finally:
                    work.task_done()

        began = time.perf_counter()
        await asyncio.gather(*(submitter() for _ in range(concurrency)))
        elapsed = time.perf_counter() - began

    return {
        "requested": total,
        "accepted": accepted,
        "failed": total - accepted,
        "errors": dict(failures),
        "expected_alerts": expected_alerts,
        "api_elapsed_seconds": round(elapsed, 2),
        "accepted_per_second": round(accepted / elapsed, 2) if elapsed else 0,
        "response_latency_ms_p50": percentile(timings_ms, 50),
        "response_latency_ms_p95": percentile(timings_ms, 95),
        "response_latency_ms_p99": percentile(timings_ms, 99),
    }


async def wait_for_processing(source: str, accepted: int, timeout: int, poll: float) -> dict:
    began = time.perf_counter()
    processed = 0
    alerts = 0
    last_print = 0.0
    while True:
        # subprocess.run() runs in a thread so it doesn't freeze the event loop.
        processed, alerts = await asyncio.to_thread(db_counts, source)
        elapsed = time.perf_counter() - began
        if accepted == processed:
            return {
                "processed": processed,
                "alerts_persisted": alerts,
                "drain_seconds_after_submission": round(elapsed, 2),
                "worker_drained": True,
            }
        if elapsed >= timeout:
            return {
                "processed": processed,
                "alerts_persisted": alerts,
                "drain_seconds_after_submission": round(elapsed, 2),
                "worker_drained": False,
            }
        if elapsed - last_print >= 10:
            print(f"    Processing progress: {processed}/{accepted} saved ({int(elapsed)}s elapsed)", flush=True)
            last_print = elapsed
        await asyncio.sleep(poll)


def write_reports(rows: list[dict], metadata: dict) -> tuple[Path, Path, Path]:
    RESULTS_DIR.mkdir(exist_ok=True, parents=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = RESULTS_DIR / f"load-test-{timestamp}.json"
    csv_path = RESULTS_DIR / f"load-test-{timestamp}.csv"
    md_path = RESULTS_DIR / f"load-test-{timestamp}.md"
    json_path.write_text(json.dumps({"environment": metadata, "runs": rows}, indent=2) + "\n", encoding="utf-8")
    fields = [
        "requested", "accepted", "failed", "processed", "expected_alerts",
        "alerts_persisted", "status", "api_elapsed_seconds", "accepted_per_second",
        "response_latency_ms_p50", "response_latency_ms_p95", "response_latency_ms_p99",
        "drain_seconds_after_submission", "end_to_end_seconds", "processed_per_second",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    table = [
        "| Sent | Accepted | Persisted | Alerts | API req/s | p95 API ms | End-to-end s | Result |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |",
    ]
    for row in rows:
        table.append(
            f"| {row['requested']} | {row['accepted']} | {row['processed']} | "
            f"{row['alerts_persisted']}/{row['expected_alerts']} | "
            f"{row['accepted_per_second']} | {row['response_latency_ms_p95']} | "
            f"{row['end_to_end_seconds']} | {row['status']} |"
        )
    md = (
        "# Local Cloud Log Monitor load test\n\n"
        "Synthetic data only, using Docker Compose on the test machine. "
        "API throughput is for accepted POST /logs responses; not persisted events. "
        "p95 measures API response time, not queue/worker completion. "
        "End-to-end time measures submission plus queue drain, using database row counts. "
        "Results are not representative of AWS or production infrastructure.\n\n"
        f"Generated UTC: {metadata['created_at_utc']}  \n"
        f"Python: {metadata['python_version']}  \n"
        f"OS: {metadata['platform']}  \n"
        f"Concurrency: {metadata['concurrency']}  \n"
        "\n" + "\n".join(table) + "\n\n"
        "Note: benchmark records persist in the local PostgreSQL database; "
        "the dashboard only retrieves the most recent 100 records.\n"
    )
    md_path.write_text(md, encoding="utf-8")
    return json_path, csv_path, md_path


async def main() -> int:
    parser = argparse.ArgumentParser(description="Load test the LOCAL Cloud Log Monitor (synthetic logs only)")
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 1000], help="Log counts per run, e.g. 100 1000 10000")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent HTTP clients (default: 10)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--drain-timeout", type=int, default=1200, help="Seconds to wait after submissions for each worker drain")
    parser.add_argument("--poll-interval", type=float, default=3.0, help="Seconds between database checks")
    args = parser.parse_args()
    try:
        base_url = require_loopback(args.base_url)
    except ValueError as exc:
        parser.error(str(exc))
    if not 1 <= args.concurrency <= 100:
        parser.error("--concurrency must be in the range 1..100")
    if not args.sizes or any(size < 1 or size > 10000 for size in args.sizes):
        parser.error("Each size must be 1..10000 to limit accidental overload")
    if args.drain_timeout < 1 or args.poll_interval <= 0:
        parser.error("Timeout and poll interval must be positive")

    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "base_url": base_url,
        "concurrency": args.concurrency,
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{base_url}/health")
            response.raise_for_status()
            if response.json().get("status") != "ok":
                raise ValueError("/health did not return status=ok")
        initial = await asyncio.to_thread(db_counts, "loadtest-healthcheck")
        print(f"Health OK; PostgreSQL accessible via Docker Compose (counts: {initial}).")
    except (OSError, RuntimeError, ValueError, httpx.HTTPError) as exc:
        print(f"Preflight failed: {exc}\nRun 'docker compose up -d' in the project directory first.", file=sys.stderr)
        return 2

    rows = []
    for size in args.sizes:
        source = f"loadtest-{uuid4().hex[:12]}-{size}"
        print(f"\nSending {size:,} synthetic events at concurrency {args.concurrency}...")
        started = time.perf_counter()
        submission = await send_events(base_url, source, size, args.concurrency)
        print(
            f"  API: {submission['accepted']}/{size} accepted; "
            f"{submission['accepted_per_second']} accepted/s; "
            f"p95={submission['response_latency_ms_p95']} ms"
        )
        try:
            processing = await wait_for_processing(
                source, submission["accepted"], args.drain_timeout, args.poll_interval
            )
        except (RuntimeError, ValueError) as exc:
            print(f"  Database verification failed: {exc}", file=sys.stderr)
            processing = {
                "processed": 0,
                "alerts_persisted": 0,
                "drain_seconds_after_submission": 0,
                "worker_drained": False,
                "verification_error": str(exc),
            }
        elapsed = time.perf_counter() - started
        row = {
            "source": source,
            **submission,
            **processing,
            "end_to_end_seconds": round(elapsed, 2),
            "processed_per_second": round(processing["processed"] / elapsed, 2) if elapsed else 0,
        }
        row["status"] = (
            "PASS" if row["accepted"] == size
            and row["processed"] == row["accepted"]
            and row["alerts_persisted"] == row["expected_alerts"]
            and row["worker_drained"] else "INCOMPLETE"
        )
        rows.append(row)
        print(
            f"  Worker: {row['processed']}/{row['accepted']} persisted; "
            f"alerts {row['alerts_persisted']}/{row['expected_alerts']}; "
            f"end-to-end {row['end_to_end_seconds']}s => {row['status']}"
        )
        if not row["worker_drained"]:
            print("Stopping: previous queue has not drained. Check 'docker compose logs worker'.")
            break

    paths = write_reports(rows, metadata)
    print("\nSaved benchmark outputs:")
    for path in paths:
        print(f"  {path}")
    return 0 if len(rows) == len(args.sizes) and all(row["status"] == "PASS" for row in rows) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nInterrupted. Previously queued jobs may still be processing.", file=sys.stderr)
        raise SystemExit(130)
