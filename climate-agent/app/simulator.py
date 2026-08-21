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
