"""Tests for the agent loop with a mocked LLM."""

import json
from unittest.mock import MagicMock, patch

import pytest

from agent import run_agent


def _fake_message(content=None, tool_calls=None):
    msg = MagicMock()
    msg.role = "assistant"
    msg.content = content
    msg.tool_calls = tool_calls
    return msg


def _fake_tool_call(id_: str, name: str, args: dict):
    tc = MagicMock()
    tc.id = id_
    tc.function.name = name
    tc.function.arguments = json.dumps(args)
    return tc


@patch("agent.get_client")
def test_agent_calls_tool_then_replies(mock_get_client):
    # First LLM call: asks to call calculate_emi
    tc = _fake_tool_call(
        "call_1",
        "calculate_emi",
        {"principal": 100000, "annual_rate_percent": 10, "tenure_years": 2},
    )
    first = _fake_message(content=None, tool_calls=[tc])
    # Second LLM call: final reply after tool result
    second = _fake_message(content="Your EMI is ₹4,614.")

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [
        MagicMock(choices=[MagicMock(message=first)]),
        MagicMock(choices=[MagicMock(message=second)]),
    ]
    mock_get_client.return_value = fake_client

    reply = run_agent("What's my EMI?")
    assert "4,614" in reply
    assert fake_client.chat.completions.create.call_count == 2


@patch("agent.get_client")
def test_agent_handles_unknown_tool(mock_get_client):
    tc = _fake_tool_call("call_1", "bogus_tool", {})
    first = _fake_message(content=None, tool_calls=[tc])
    second = _fake_message(content="Sorry, I don't have that tool.")

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [
        MagicMock(choices=[MagicMock(message=first)]),
        MagicMock(choices=[MagicMock(message=second)]),
    ]
    mock_get_client.return_value = fake_client

    reply = run_agent("do the thing")
    assert isinstance(reply, str)


@patch("agent.get_client")
def test_agent_direct_reply_no_tools(mock_get_client):
    first = _fake_message(content="Hello! How can I help?")
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=first)]
    )
    mock_get_client.return_value = fake_client

    reply = run_agent("hi")
    assert reply == "Hello! How can I help?"
    assert fake_client.chat.completions.create.call_count == 1
