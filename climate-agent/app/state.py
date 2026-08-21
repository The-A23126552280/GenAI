"""
In-memory session store.

Single-process, single-worker only: sessions live in a plain dict, so they
vanish on restart and aren't shared across multiple uvicorn/gunicorn
workers. Fine for a prototype/demo; swap for Redis or a DB-backed store
before running this behind more than one worker process.
"""
from __future__ import annotations

import uuid

import pandas as pd

from app.simulator import Simulator


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Simulator] = {}

    def create(self, data: pd.DataFrame, tmin: float, tmax: float) -> tuple[str, Simulator]:
        session_id = str(uuid.uuid4())
        sim = Simulator(data, tmin, tmax)
        self._sessions[session_id] = sim
        return session_id, sim

    def get(self, session_id: str) -> Simulator:
        return self._sessions[session_id]

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def __len__(self) -> int:
        return len(self._sessions)
