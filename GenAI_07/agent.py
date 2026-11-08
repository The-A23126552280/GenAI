"""Minimal ReAct-style agent: LLM decides -> call tool -> feed result back -> reply."""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from tools import TOOL_REGISTRY, TOOL_SCHEMAS

load_dotenv()

SYSTEM_PROMPT = """You are a helpful financial assistant. You have three tools:
- calculate_emi: compute monthly EMI for a loan
- get_stock_price: fetch latest stock price
- get_company_info: fetch company fundamentals

When the user asks a question, call the appropriate tool(s) and then give a
clear, concise answer in plain English with the key numbers. If a tool returns
an error, explain it to the user and suggest a fix.
"""


def get_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1",
    )


def run_agent(user_message: str, model: str | None = None) -> str:
    """Run a single turn of the agent and return the final assistant reply."""
    model = model or os.getenv("GROQ_MODEL")
    client = get_client()

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    # Allow up to N tool-call rounds to avoid infinite loops
    for _ in range(5):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )
        msg = response.choices[0].message
        messages.append(_msg_to_dict(msg))

        # No tool calls -> final answer
        if not msg.tool_calls:
            return msg.content or ""

        # Execute each requested tool call
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            fn = TOOL_REGISTRY.get(name)
            if fn is None:
                result = {"error": f"Unknown tool: {name}"}
            else:
                try:
                    result = fn(**args)
                except Exception as e:
                    result = {"error": f"Tool {name} raised: {e}"}

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                }
            )

    return "(agent reached max tool-call rounds)"


def _msg_to_dict(msg) -> dict[str, Any]:
    """Convert an OpenAI message object to a JSON-serialisable dict."""
    d: dict[str, Any] = {"role": msg.role, "content": msg.content}
    if msg.tool_calls:
        d["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return d
