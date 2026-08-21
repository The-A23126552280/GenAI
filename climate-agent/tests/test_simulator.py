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
