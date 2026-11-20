from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LogIn(BaseModel):
    event_id: str | None = Field(
        default=None,
        max_length=80,
        pattern=r"^[A-Za-z0-9._:-]+$",
        description="Optional stable identifier for idempotent retries",
    )
    source: str = Field(min_length=1, max_length=80)
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    message: str = Field(min_length=1, max_length=2048)
    occurred_at: datetime | None = None


class LogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    source: str
    level: str
    message: str
    occurred_at: datetime
    processed_at: datetime


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: str
    rule: str
    severity: str
    explanation: str
    created_at: datetime
