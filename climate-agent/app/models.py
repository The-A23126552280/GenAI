"""Pydantic schemas for API request/response bodies."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.config import DEFAULT_TMAX, DEFAULT_TMIN


class SessionCreate(BaseModel):
    tmin: float = Field(default=DEFAULT_TMIN, description="Lower bound of comfort range, °C")
    tmax: float = Field(default=DEFAULT_TMAX, description="Upper bound of comfort range, °C")


class SessionInfo(BaseModel):
    session_id: str
    tmin: float
    tmax: float
    total_rows: int
    dataset_start: datetime
    dataset_end: datetime


class LogEntryResult(BaseModel):
    index: int
    timestamp: datetime
    room_temp: float
    outdoor_temp: float
    ac_on: bool
    action: str
    thought: str


class StepResult(LogEntryResult):
    finished: bool


class SessionState(BaseModel):
    session_id: str
    started: bool
    finished: bool
    current: LogEntryResult | None = None


class LogResponse(BaseModel):
    session_id: str
    count: int
    entries: list[LogEntryResult]
