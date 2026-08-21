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
