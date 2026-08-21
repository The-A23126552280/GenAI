"""
FastAPI layer. Loads the SML2010 dataset once at startup, then exposes a
session-based replay API: create a session with a comfort range, step
through real sensor rows one at a time, and read back the agent's decision
log — the same sense/think/act cycle from agent.py, driven by real data
instead of synthetic physics.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # ← add this line

from app.data_loader import agent_view, load_and_cache
from app.models import (
    LogEntryResult,
    LogResponse,
    SessionCreate,
    SessionInfo,
    SessionState,
    StepResult,
)
from app.simulator import LogEntry, Simulator
from app.state import SessionStore

store = SessionStore()


@asynccontextmanager
async def lifespan(app: FastAPI):
    full = load_and_cache()
    app.state.dataset = agent_view(full)
    yield


app = FastAPI(title="Climate Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/ui", StaticFiles(directory="static", html=True), name="ui"
)  # ← add this line


def _to_log_entry(entry: LogEntry) -> LogEntryResult:
    return LogEntryResult(
        index=entry.index,
        timestamp=entry.timestamp,
        room_temp=entry.room_temp,
        outdoor_temp=entry.outdoor_temp,
        ac_on=entry.decision.ac_on,
        action=entry.decision.action.value,
        thought=entry.decision.thought,
    )


def _get_simulator(session_id: str) -> Simulator:
    try:
        return store.get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/sessions", response_model=SessionInfo)
def create_session(payload: SessionCreate):
    try:
        session_id, sim = store.create(app.state.dataset, payload.tmin, payload.tmax)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return SessionInfo(
        session_id=session_id,
        tmin=sim.tmin,
        tmax=sim.tmax,
        total_rows=len(sim.data),
        dataset_start=sim.data.iloc[0].timestamp,
        dataset_end=sim.data.iloc[-1].timestamp,
    )


@app.post("/sessions/{session_id}/step", response_model=StepResult)
def step_session(session_id: str):
    sim = _get_simulator(session_id)
    if sim.finished:
        raise HTTPException(
            status_code=409, detail="Replay finished. Call /reset to start over."
        )
    entry = sim.step()
    return StepResult(**_to_log_entry(entry).model_dump(), finished=sim.finished)


@app.get("/sessions/{session_id}/state", response_model=SessionState)
def get_state(session_id: str):
    sim = _get_simulator(session_id)
    current = sim.current
    return SessionState(
        session_id=session_id,
        started=current is not None,
        finished=sim.finished,
        current=_to_log_entry(current) if current else None,
    )


@app.get("/sessions/{session_id}/log", response_model=LogResponse)
def get_log(session_id: str, limit: int | None = None):
    sim = _get_simulator(session_id)
    entries = sim.log[-limit:] if limit else sim.log
    return LogResponse(
        session_id=session_id,
        count=len(entries),
        entries=[_to_log_entry(e) for e in entries],
    )


@app.post("/sessions/{session_id}/reset", response_model=SessionState)
def reset_session(session_id: str):
    sim = _get_simulator(session_id)
    sim.reset()
    return SessionState(
        session_id=session_id, started=False, finished=False, current=None
    )


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    _get_simulator(session_id)
    store.delete(session_id)
    return {"detail": "Session deleted"}
