Here's the step-by-step workflow for turning this into a `uv`-managed FastAPI service, structured as plain Python modules (no heavy framework conventions):

## 1. Project scaffolding
```
climate-agent/
├── pyproject.toml
├── data/
│   ├── raw/
│   │   ├── NEW-DATA-1.T15.txt
│   │   └── NEW-DATA-2.T15.txt
│   └── processed/
│       └── sml2010.parquet          # cleaned, cached output of step 2
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app + routes
│   ├── config.py                    # paths, thresholds, constants
│   ├── data_loader.py               # parse raw txt -> DataFrame
│   ├── agent.py                     # sense/think/act decision logic
│   ├── simulator.py                 # replay engine (steps through rows)
│   ├── models.py                    # Pydantic schemas for API I/O
│   └── state.py                     # in-memory session/replay state
├── tests/
│   ├── test_data_loader.py
│   ├── test_agent.py
│   └── test_simulator.py
└── README.md
```
Init with `uv init climate-agent && cd climate-agent && uv add "fastapi[standard]" pandas`.

## 2. Data ingestion (`data_loader.py`)
- Parse the two whitespace-delimited `.txt` files (`NEW-DATA-1`, `NEW-DATA-2`) into a single `pandas.DataFrame`, using the header comment line as column names.
- Combine `Date` + `Time` into one `timestamp` column, sort chronologically.
- Keep only the columns the agent needs: `timestamp`, `Temperature_Habitacion_Sensor` (room temp), `Temperature_Exterior_Sensor` (outdoor temp) — rename to plain English (`room_temp`, `outdoor_temp`).
- Cache the cleaned result to `data/processed/sml2010.parquet` so re-parsing the raw txt isn't needed every run.

## 3. Agent logic (`agent.py`)
- Port the exact decision function from our design doc: pure function `decide(temp: float, ac_on: bool, tmin: float, tmax: float) -> Action`.
- No I/O, no state — fully unit-testable in isolation against known temp/threshold combinations.

## 4. Simulator (`simulator.py`)
- A `Simulator` class holding: the loaded DataFrame, current row index, `ac_on` state, comfort thresholds, and a log list.
- `.step()` — advances one row, reads `room_temp` from the **real dataset** (not synthetic physics), calls `agent.decide()`, updates `ac_on`, appends a log entry, returns the new state.
- `.reset()` — back to row 0, `ac_on=False`, log cleared.
- This is the key difference from the HTML prototype: temperature is no longer simulated physics, it's replayed from SML2010 rows.

## 5. API layer (`main.py` + `models.py`)
Minimal REST + polling-friendly endpoints (can upgrade to WebSocket later for live push):
| Method | Path | Purpose |
|---|---|---|
| `POST` | `/session` | Create a replay session with `tmin`, `tmax`, dataset range |
| `POST` | `/session/{id}/step` | Advance one tick, return `{temp, ac_on, action, thought, timestamp}` |
| `GET` | `/session/{id}/state` | Current snapshot |
| `GET` | `/session/{id}/log` | Full decision history so far |
| `POST` | `/session/{id}/reset` | Reset session to start of dataset |

## 6. State management (`state.py`)
- Simple in-memory dict `{session_id: Simulator}` for now — no DB needed for a prototype. Swap for Redis later if it needs to survive restarts or scale beyond one process.

## 7. Config (`config.py`)
- `DATA_DIR`, default `TMIN=22`, `TMAX=25`, dataset file paths — pulled from env vars via `pydantic-settings` so nothing's hardcoded.

## 8. Tests
- `test_data_loader.py`: confirms parsed row count, no NaT timestamps, correct column dtypes.
- `test_agent.py`: table-driven tests hitting every branch of the decision table (hot/cold/idle/hysteresis).
- `test_simulator.py`: run a full replay over a small slice of real data, assert AC toggles happen at the expected timestamps.

## 9. Run it
```
uv run fastapi dev app/main.py
```
Then either hit the endpoints directly, or point the existing `climate-agent.html` artifact at `/session/{id}/step` on an interval instead of its synthetic `tick()` — same visuals, real data underneath.

---

Want me to start scaffolding this now (pyproject.toml, folder structure, and the data loader first so we can confirm the parsed SML2010 output looks right before building the API on top of it)?

user: i just uv init, created data/ and subdirs now let's do 2. Data ingestion (data_loader.py)

---

Parsing, timestamp merging, deduplication/sort, and the slim `agent_view` all work correctly against the real column layout — confirmed with your sample rows (3 rows in, deduped across both files, correct dtypes, `room_temp`/`outdoor_temp` cleanly extracted).

One thing surfaced: **the sandbox here has no internet**, so I couldn't install `pyarrow` to test the parquet caching line — but the code path is standard pandas and will work fine once you add the dependency on your machine.

## `app/config.py`
```python
"""Central place for paths and constants. No logic lives here."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
PROCESSED_FILE = PROCESSED_DATA_DIR / "sml2010.parquet"

RAW_FILES = [
    RAW_DATA_DIR / "NEW-DATA-1.T15.txt",
    RAW_DATA_DIR / "NEW-DATA-2.T15.txt",
]

DEFAULT_TMIN = 22.0
DEFAULT_TMAX = 25.0
```

## `app/data_loader.py`
```python
"""
Loads the SML2010 dataset (NEW-DATA-1.T15.txt / NEW-DATA-2.T15.txt) into a
clean, chronologically-sorted pandas DataFrame, with a parquet cache so the
raw whitespace-delimited text files only get re-parsed when they change.

Usage:
    from app.data_loader import load_and_cache, agent_view

    df = load_and_cache()          # full dataset, all 24 columns
    slim = agent_view(df)          # just what the agent needs to run
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.config import PROCESSED_FILE, RAW_FILES

# Column order exactly as documented in the dataset's header comment line.
RAW_COLUMNS = [
    "Date",
    "Time",
    "Temperature_Comedor_Sensor",
    "Temperature_Habitacion_Sensor",
    "Weather_Temperature",
    "CO2_Comedor_Sensor",
    "CO2_Habitacion_Sensor",
    "Humedad_Comedor_Sensor",
    "Humedad_Habitacion_Sensor",
    "Lighting_Comedor_Sensor",
    "Lighting_Habitacion_Sensor",
    "Precipitacion",
    "Meteo_Exterior_Crepusculo",
    "Meteo_Exterior_Viento",
    "Meteo_Exterior_Sol_Oest",
    "Meteo_Exterior_Sol_Est",
    "Meteo_Exterior_Sol_Sud",
    "Meteo_Exterior_Piranometro",
    "Exterior_Entalpic_1",
    "Exterior_Entalpic_2",
    "Exterior_Entalpic_turbo",
    "Temperature_Exterior_Sensor",
    "Humedad_Exterior_Sensor",
    "Day_Of_Week",
]


def _parse_raw_file(path: Path) -> pd.DataFrame:
    """Parse a single NEW-DATA-*.T15.txt file into a typed DataFrame."""
    if not path.exists():
        raise FileNotFoundError(f"SML2010 raw file not found: {path}")

    df = pd.read_csv(
        path,
        sep=r"\s+",
        comment="#",
        header=None,
        names=RAW_COLUMNS,
        engine="python",
    )

    df["timestamp"] = pd.to_datetime(
        df["Date"] + " " + df["Time"], format="%d/%m/%Y %H:%M"
    )
    df = df.drop(columns=["Date", "Time"])

    cols = ["timestamp"] + [c for c in df.columns if c != "timestamp"]
    return df[cols]


def load_raw(paths: list[Path] = RAW_FILES) -> pd.DataFrame:
    """Parse and concatenate all raw SML2010 chunks into one sorted DataFrame."""
    frames = [_parse_raw_file(p) for p in paths]
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset="timestamp", keep="first")
    combined = combined.sort_values("timestamp").reset_index(drop=True)
    return combined


def load_and_cache(force_refresh: bool = False) -> pd.DataFrame:
    """
    Return the full parsed dataset, using a parquet cache to skip re-parsing
    the raw text files on every startup. Pass force_refresh=True after the
    raw files change.
    """
    if PROCESSED_FILE.exists() and not force_refresh:
        return pd.read_parquet(PROCESSED_FILE)

    df = load_raw()
    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PROCESSED_FILE, index=False)
    return df


def agent_view(df: pd.DataFrame) -> pd.DataFrame:
    """
    Slim projection with only what the temperature agent needs to run,
    renamed to plain English so agent.py / simulator.py don't touch
    dataset-specific column names.
    """
    return df[
        ["timestamp", "Temperature_Habitacion_Sensor", "Temperature_Exterior_Sensor"]
    ].rename(
        columns={
            "Temperature_Habitacion_Sensor": "room_temp",
            "Temperature_Exterior_Sensor": "outdoor_temp",
        }
    )


if __name__ == "__main__":
    # Quick manual sanity check: python -m app.data_loader
    full = load_and_cache(force_refresh=True)
    print(f"Loaded {len(full)} rows, {full['timestamp'].min()} -> {full['timestamp'].max()}")
    print(full.dtypes)
    print()
    print(agent_view(full).head())
```

## What to do on your machine
```bash
uv add pandas pyarrow
touch app/__init__.py
# drop your two real NEW-DATA-*.T15.txt files into data/raw/
uv run python -m app.data_loader
```
That last command should print the row count, the full date range, dtypes, and a preview of the slim `room_temp`/`outdoor_temp` view — same shape as what I just verified above, just at full dataset scale instead of 3 sample rows.

A couple of design notes worth flagging:
- **`Temperature_Habitacion_Sensor`** (bedroom/room sensor) is what I picked as `room_temp` — `Temperature_Comedor_Sensor` (dining room) is the other candidate. Let me know if you'd rather track the dining room, or even run the agent against both.
- The parquet cache means `data_loader.py` only re-parses the raw `.txt` on first run or when you pass `force_refresh=True` — later runs of the simulator/API will load instantly from `sml2010.parquet`.

Ready for step 3 (`agent.py`) whenever you are.

user: ok Step 2 Done!

---

Nice — on to **Step 3: `agent.py`**.

This is the pure decision logic, ported directly from the design doc's pseudocode, with zero I/O and zero dependency on pandas or the dataset. That's deliberate: it should be trivially unit-testable against plain floats and booleans, independent of where the temperature reading came from.pytest isn't installable here (no network), so let me validate the logic manually with a plain script covering the exact same cases before handing it off — I want to actually confirm the branches work, not just claim they do.Good catch from that test run — one of the reasoning messages is wrong. For `temp=18.0, ac_on=False` (below the comfort band, but the AC's already off so there's nothing to do), the code says *"within [22.0, 25.0]°C"* — which is false, 18 isn't in that range. The **action** logic is correct, but the **thought text** is misleading. Fixing it:Also tightening the test to actually catch this class of bug — asserting the *action* was right wasn't enough, since the thought text was wrong and still passed:All branches pass, including the fix.

## `app/agent.py`
```python
"""
The agent's decision function: sense -> think -> act, expressed as one pure
function. No I/O, no dataset knowledge, no framework imports — this is what
makes it trivially unit-testable and reusable from both the replay simulator
and (later) a live sensor feed.

Decision table (hysteresis prevents rapid ON/OFF flicker at the boundary):

    temp > tmax   and AC is OFF  -> turn AC ON
    temp <= tmin  and AC is ON   -> turn AC OFF
    otherwise                    -> no change
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Action(str, Enum):
    AC_ON = "AC_ON"
    AC_OFF = "AC_OFF"
    NO_CHANGE = "NO_CHANGE"


@dataclass(frozen=True)
class Decision:
    action: Action
    ac_on: bool       # AC state AFTER this decision is applied
    thought: str      # human-readable reasoning, for logs / UI


def decide(temp: float, ac_on: bool, tmin: float, tmax: float) -> Decision:
    """
    Given the current sensed temperature and AC state, decide the next
    action against the comfort band [tmin, tmax].
    """
    if tmin >= tmax:
        raise ValueError(f"tmin ({tmin}) must be less than tmax ({tmax})")

    if temp > tmax and not ac_on:
        return Decision(
            action=Action.AC_ON,
            ac_on=True,
            thought=f"{temp:.1f}°C exceeds max {tmax:.1f}°C → cooling required",
        )

    if temp <= tmin and ac_on:
        return Decision(
            action=Action.AC_OFF,
            ac_on=False,
            thought=f"{temp:.1f}°C reached min {tmin:.1f}°C → goal achieved",
        )

    if ac_on:
        thought = f"{temp:.1f}°C still above {tmin:.1f}°C → keep cooling"
    elif temp < tmin:
        thought = f"{temp:.1f}°C is below min {tmin:.1f}°C, but AC is already off → no action needed"
    else:
        thought = f"{temp:.1f}°C within [{tmin:.1f}, {tmax:.1f}]°C → comfortable"

    return Decision(action=Action.NO_CHANGE, ac_on=ac_on, thought=thought)
```

## `tests/test_agent.py`
```python
import pytest

from app.agent import Action, decide

TMIN, TMAX = 22.0, 25.0


@pytest.mark.parametrize(
    "temp, ac_on, expected_action, expected_ac_on",
    [
        (26.0, False, Action.AC_ON, True),
        (26.0, True, Action.NO_CHANGE, True),
        (22.0, True, Action.AC_OFF, False),
        (18.0, True, Action.AC_OFF, False),
        (18.0, False, Action.NO_CHANGE, False),
        (23.5, False, Action.NO_CHANGE, False),
        (23.5, True, Action.NO_CHANGE, True),
        (25.0, False, Action.NO_CHANGE, False),   # exactly at tmax -> not > tmax yet
        (25.1, False, Action.AC_ON, True),
    ],
)
def test_decide_branches(temp, ac_on, expected_action, expected_ac_on):
    decision = decide(temp, ac_on, TMIN, TMAX)
    assert decision.action == expected_action
    assert decision.ac_on == expected_ac_on
    assert decision.thought


def test_thought_text_matches_actual_temperature_position():
    d = decide(18.0, False, TMIN, TMAX)
    assert "within" not in d.thought
    assert "below min" in d.thought

    d = decide(23.5, False, TMIN, TMAX)
    assert "within" in d.thought


def test_decide_rejects_invalid_range():
    with pytest.raises(ValueError):
        decide(23.0, False, tmin=25.0, tmax=22.0)


def test_hysteresis_prevents_flicker_at_boundary():
    d = decide(23.0, True, TMIN, TMAX)
    assert d.action == Action.NO_CHANGE
    assert d.ac_on is True
```

## What to do on your machine
```bash
uv add --dev pytest
uv run pytest tests/test_agent.py -v
```

**One honest caveat:** the sandbox I work in has no internet access, so I couldn't `pip install pytest` here — I validated all 9 decision-table cases plus the regression test with a plain script instead (output above), not the actual pytest runner. Worth running `uv run pytest` yourself once to confirm it collects and passes cleanly in your environment.

Ready for **Step 4 (`simulator.py`)** — wiring this decision function up to real rows from your SML2010 data — whenever you are.

user: ok 12 Tests passed in 0.2 sec. Step 3 Done!

---

On to **Step 4: `simulator.py`** — this wires the pure `decide()` function to real rows from SML2010, replayed one at a time instead of synthetic physics.Same limitation as before: no internet in my sandbox, so `pytest` isn't installable here — let me validate every case manually before handing it off.All 7 checks pass. Let me also do a quick smoke test against your **actual** SML2010 sample rows end-to-end, just to make sure `data_loader` → `simulator` connects cleanly:End-to-end pipeline confirmed working against your real sample rows — data flows from raw txt → `agent_view` → `Simulator.step()` → correct decisions, timestamps preserved.

## `app/simulator.py`
```python
"""
Replays a temperature dataset row by row, running the agent's decide()
function against each real sensor reading. This is the bridge between
data_loader.py (real data in) and agent.py (pure decision logic) — it
holds no decision logic itself, only sequencing and state.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.agent import Decision, decide

REQUIRED_COLUMNS = {"timestamp", "room_temp", "outdoor_temp"}


@dataclass
class LogEntry:
    index: int
    timestamp: pd.Timestamp
    room_temp: float
    outdoor_temp: float
    decision: Decision


class Simulator:
    """
    Steps through a timestamp-sorted DataFrame (as produced by
    data_loader.agent_view) one row at a time, maintaining AC state and a
    running decision log.
    """

    def __init__(self, data: pd.DataFrame, tmin: float, tmax: float):
        missing = REQUIRED_COLUMNS - set(data.columns)
        if missing:
            raise ValueError(f"data is missing required columns: {missing}")
        if tmin >= tmax:
            raise ValueError(f"tmin ({tmin}) must be less than tmax ({tmax})")

        # Rows with a missing room_temp reading can't be sensed — drop them
        # rather than silently feeding NaN into the decision function.
        clean = data.dropna(subset=["room_temp"]).reset_index(drop=True)

        self.data = clean
        self.tmin = tmin
        self.tmax = tmax
        self.index = -1          # -1 = not started yet
        self.ac_on = False
        self.log: list[LogEntry] = []

    @property
    def finished(self) -> bool:
        return self.index >= len(self.data) - 1

    @property
    def current(self) -> LogEntry | None:
        return self.log[-1] if self.log else None

    def reset(self) -> None:
        self.index = -1
        self.ac_on = False
        self.log = []

    def step(self) -> LogEntry:
        """Advance one row and apply the agent's decision. Raises
        StopIteration once the dataset is exhausted."""
        if self.finished:
            raise StopIteration("Reached end of dataset")

        self.index += 1
        row = self.data.iloc[self.index]

        decision = decide(
            temp=float(row.room_temp),
            ac_on=self.ac_on,
            tmin=self.tmin,
            tmax=self.tmax,
        )
        self.ac_on = decision.ac_on

        entry = LogEntry(
            index=self.index,
            timestamp=row.timestamp,
            room_temp=float(row.room_temp),
            outdoor_temp=float(row.outdoor_temp),
            decision=decision,
        )
        self.log.append(entry)
        return entry

    def run_all(self) -> list[LogEntry]:
        """Step through the entire remaining dataset in one call."""
        while not self.finished:
            self.step()
        return self.log
```

## `tests/test_simulator.py`
```python
import pandas as pd
import pytest

from app.agent import Action
from app.simulator import Simulator

TMIN, TMAX = 22.0, 25.0


def make_df(temps, outdoor=None):
    n = len(temps)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2012-03-13 12:00", periods=n, freq="15min"),
            "room_temp": temps,
            "outdoor_temp": outdoor or [temps[i] + 2 for i in range(n)],
        }
    )


def test_step_sequence_matches_expected_ac_transitions():
    temps = [23.0, 26.0, 26.0, 24.0, 22.0, 21.0, 23.0]
    expected = [
        (Action.NO_CHANGE, False),
        (Action.AC_ON, True),
        (Action.NO_CHANGE, True),
        (Action.NO_CHANGE, True),
        (Action.AC_OFF, False),
        (Action.NO_CHANGE, False),
        (Action.NO_CHANGE, False),
    ]
    sim = Simulator(make_df(temps), TMIN, TMAX)
    for temp, (exp_action, exp_ac) in zip(temps, expected):
        entry = sim.step()
        assert entry.room_temp == temp
        assert entry.decision.action == exp_action
        assert entry.decision.ac_on == exp_ac
        assert sim.ac_on == exp_ac


def test_finished_and_stop_iteration():
    sim = Simulator(make_df([23.0, 23.0]), TMIN, TMAX)
    assert not sim.finished
    sim.step()
    assert not sim.finished
    sim.step()
    assert sim.finished
    with pytest.raises(StopIteration):
        sim.step()


def test_reset_clears_state():
    sim = Simulator(make_df([26.0, 26.0]), TMIN, TMAX)
    sim.step()
    sim.step()
    assert sim.ac_on is True
    assert len(sim.log) == 2

    sim.reset()
    assert sim.ac_on is False
    assert sim.log == []
    assert not sim.finished
    assert sim.current is None


def test_nan_room_temp_rows_are_dropped():
    df = make_df([23.0, 24.0, 25.5])
    df.loc[1, "room_temp"] = float("nan")

    sim = Simulator(df, TMIN, TMAX)
    assert len(sim.data) == 2
    results = sim.run_all()
    assert [e.room_temp for e in results] == [23.0, 25.5]


def test_run_all_consumes_entire_dataset():
    sim = Simulator(make_df([23.0, 26.0, 22.0]), TMIN, TMAX)
    results = sim.run_all()
    assert len(results) == 3
    assert sim.finished


def test_rejects_missing_columns():
    df = pd.DataFrame({"timestamp": [1], "room_temp": [23.0]})
    with pytest.raises(ValueError):
        Simulator(df, TMIN, TMAX)


def test_rejects_invalid_comfort_range():
    with pytest.raises(ValueError):
        Simulator(make_df([23.0]), tmin=25.0, tmax=22.0)
```

## What to do on your machine
```bash
uv run pytest tests/test_simulator.py -v
```
Should show 7 tests passing.

Two design notes worth flagging:
- **NaN handling**: real sensor data has gaps, so `Simulator` silently drops rows with a missing `room_temp` rather than crashing or feeding `NaN` into `decide()`. Worth deciding later whether that's the right call for your report, versus forward-filling.
- **`from_dataset` convenience constructor**: right now you build a `Simulator` from an already-sliced `agent_view` DataFrame. If that feels clunky once we wire up the API, we can add a classmethod that takes the full raw dataset directly.

Ready for **Step 5 (`main.py` + `models.py`, the FastAPI layer)** whenever you are.

user: 7 passed. Step 4 Done!

---

On to **Step 5: the FastAPI layer** — `models.py`, `state.py`, and `main.py`.No network here either, so I can't install FastAPI/httpx to run this one through a real `TestClient` — I'll write it carefully, sanity-check the underlying logic with plain Python (bypassing the FastAPI decorators), and flag that you should smoke-test the actual HTTP layer yourself once it's on your machine.Now sanity-checking the logic that FastAPI will wrap — session creation, stepping, resetting, and the 409/404 error paths — without going through the actual HTTP layer, since I can't install FastAPI here:All the logic each endpoint depends on (session creation, stepping, exhaustion, reset, missing-session and invalid-range errors) checks out.

## `app/models.py`
```python
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
```

## `app/state.py`
```python
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
```

## `app/main.py`
```python
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
    return SessionState(session_id=session_id, started=False, finished=False, current=None)


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    _get_simulator(session_id)
    store.delete(session_id)
    return {"detail": "Session deleted"}
```

## What to do on your machine
```bash
uv add "fastapi[standard]"
# drop your real NEW-DATA-*.T15.txt into data/raw/ if you haven't already
uv run fastapi dev app/main.py
```
Then open **http://127.0.0.1:8000/docs** — FastAPI's auto-generated Swagger UI — and try it live:
1. `POST /sessions` with `{"tmin": 22, "tmax": 25}` → grab the returned `session_id`
2. `POST /sessions/{session_id}/step` repeatedly → watch real SML2010 rows drive `AC_ON`/`AC_OFF`
3. `GET /sessions/{session_id}/log` → full history
4. `POST /sessions/{session_id}/reset` → start over

**Honest caveat, same as last time:** I couldn't install `fastapi`/`httpx` here to run this through an actual `TestClient`, so the HTTP routing, request validation, and response serialization are untested by me — only the plain-Python logic underneath each endpoint. Worth doing a real smoke test via `/docs` once it's running for you.

Ready for **Step 6** (tests for this layer, ideally with `TestClient`) whenever you've confirmed it boots — or we could jump straight to wiring the `climate-agent.html` artifact to poll this API instead of its synthetic `tick()`, if you'd rather see it visually first.
