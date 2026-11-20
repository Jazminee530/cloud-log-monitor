"""Background worker functions executed by RQ."""

from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.detector import detect_alert
from app.models import Alert, LogEvent


def process_log(payload: dict) -> dict:
    """Persist an event once and generate an alert if a rule matches."""
    event = LogEvent(
        event_id=payload["event_id"],
        source=payload["source"],
        level=payload["level"],
        message=payload["message"],
        occurred_at=datetime.fromisoformat(payload["occurred_at"]),
    )
    match = detect_alert(event.message)

    with SessionLocal() as session:
        session.add(event)
        if match is not None:
            session.add(Alert(event_id=event.event_id, **match))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            # Primary key enforces idempotency when the caller resends an event_id.
            if session.get(LogEvent, event.event_id) is not None:
                return {"event_id": event.event_id, "status": "already_processed"}
            raise

    return {
        "event_id": event.event_id,
        "status": "processed",
        "alert_created": match is not None,
    }
