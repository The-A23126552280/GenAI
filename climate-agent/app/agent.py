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
