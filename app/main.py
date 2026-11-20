"""HTTP API for a local demonstration log monitor."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, status
from redis.exceptions import RedisError
from rq import Retry
from rq.exceptions import NoSuchJobError
from rq.job import Job
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db import get_db, init_db
from app.models import Alert, LogEvent
from app.queue import get_queue, get_redis
from app.schemas import AlertOut, LogIn, LogOut


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Suitable for a demo. Use database migrations in real deployments.
    init_db()
    yield


app = FastAPI(title="Cloud Log Monitor", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        get_redis().ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Dependency unavailable") from exc
    return {"status": "ok"}


@app.post("/logs", status_code=status.HTTP_202_ACCEPTED)
def ingest_log(event: LogIn):
    payload = event.model_dump(mode="json")
    payload["event_id"] = payload["event_id"] or str(uuid4())
    payload["occurred_at"] = payload["occurred_at"] or datetime.now(timezone.utc).isoformat()
    try:
        job = get_queue().enqueue(
            "app.tasks.process_log",
            payload,
            job_timeout=45,
            retry=Retry(max=2),
            result_ttl=3600,
        )
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Queue unavailable") from exc
    return {"event_id": payload["event_id"], "job_id": job.id, "status": "queued"}


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    try:
        job = Job.fetch(job_id, connection=get_redis(), serializer="json")
        state = job.get_status(refresh=True)
        return {"job_id": job_id, "status": state.value if hasattr(state, "value") else str(state)}
    except NoSuchJobError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Queue unavailable") from exc


@app.get("/logs", response_model=list[LogOut])
def list_logs(limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db)):
    return db.scalars(select(LogEvent).order_by(LogEvent.processed_at.desc()).limit(limit)).all()


@app.get("/alerts", response_model=list[AlertOut])
def list_alerts(limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db)):
    return db.scalars(select(Alert).order_by(Alert.id.desc()).limit(limit)).all()

# CLOUD_LOG_MONITOR_DASHBOARD_ROUTE
from pathlib import Path as _DashboardPath
from fastapi.responses import FileResponse as _DashboardFileResponse


@app.get("/dashboard", include_in_schema=False)
def dashboard_page():
    return _DashboardFileResponse(
        _DashboardPath(__file__).resolve().parent / "static" / "dashboard.html",
        media_type="text/html",
    )
