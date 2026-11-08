"""Adaptive-agent logic: turn memory into a personalised prompt, and turn each
conversation turn back into memory.

Everything here is pure Python (no network, no Streamlit) so it can be unit-tested.
The LLM is injected as a plain callable `complete(messages) -> str`.
"""
from __future__ import annotations

import json
import re
import time
from typing import Callable

from memory import MemoryStore

# Preference keys the agent is allowed to learn, with a hint for the extractor.
ALLOWED_PREFS = {
    "level": "beginner | intermediate | advanced",
    "learning_style": "e.g. analogies, visual, step-by-step, examples-first, hands-on",
    "explanation_depth": "brief | detailed",
    "interests": "comma-separated hobbies/domains to draw examples from",
    "tone": "e.g. casual, formal, encouraging",
    "language": "preferred language of explanations",
}
LEVELS = {"beginner", "intermediate", "advanced"}
DEPTHS = {"brief", "detailed"}
UNDERSTANDING = {"confused", "neutral", "confident"}
MAX_INTERESTS = 8

EXTRACT_PROMPT = f"""You maintain a student's learning profile. Read the STUDENT's latest message \
and return ONLY one JSON object, with no prose and no code fences:
{{"preferences": {{}}, "topic": "", "understanding": "neutral"}}

Rules:
- preferences: include a key ONLY if the student explicitly states or clearly implies it in THIS message. \
Never infer from the tutor's reply. Allowed keys: {json.dumps(ALLOWED_PREFS)}. Use {{}} if nothing is stated.
- topic: the 1-3 word subject of the question, lowercase (e.g. "recursion", "sql joins").
- understanding: "confused" if the student says they don't get it or asks to simplify; \
"confident" if they show they've mastered it; otherwise "neutral"."""

DEFAULT_EXTRACTION = {"preferences": {}, "topic": None, "understanding": "neutral"}


def humanize_age(ts: float, now: float | None = None) -> str:
    seconds = max(0, (now or time.time()) - ts)
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    days = int(seconds // 86400)
    return f"{days} day{'s' if days != 1 else ''} ago"


def build_system_prompt(
    name: str,
    prefs: dict[str, str],
    memories: list[dict],
    now: float | None = None,
) -> str:
    """Compose the tutor's system prompt from the student's profile and recalled history."""
    if prefs:
        profile = "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in prefs.items())
    else:
        profile = "- Nothing known yet. Answer clearly at a moderate level, and pay attention to any " \
                  "preferences the student mentions."

    if memories:
        recalled = "\n".join(
            f"{i}. [{humanize_age(m['ts'], now)}] Asked: \"{m['question']}\""
            f" (topic: {m.get('topic') or 'n/a'}; seemed {m.get('understanding') or 'neutral'})"
            for i, m in enumerate(memories, 1)
        )
    else:
        recalled = "None relevant to this question."

    return f"""You are a personalized learning assistant tutoring {name}.

## What you know about this student
{profile}

## Related questions they asked before
{recalled}

## How to adapt
- Match the student's level, learning style, depth and tone from the profile above. Draw examples \
from their interests when it helps.
- If a related earlier question exists, build on it in one short sentence (e.g. "Earlier you asked \
about X, so...") only when it genuinely helps. Never invent memories: only mention what is listed above.
- If they previously seemed confused about this topic, slow down: smaller steps, simpler words, one \
concrete example, and finish with a quick check question.
- If the topic is new to them, end with one short question to check understanding.
- Keep answers focused. Use short paragraphs or a few bullets, not walls of text."""


def parse_extraction(raw: str) -> dict:
    """Parse the extractor's reply defensively; always returns a valid, filtered dict."""
    match = re.search(r"\{.*\}", raw or "", flags=re.DOTALL)
    if not match:
        return dict(DEFAULT_EXTRACTION, preferences={})
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return dict(DEFAULT_EXTRACTION, preferences={})
    if not isinstance(data, dict):
        return dict(DEFAULT_EXTRACTION, preferences={})

    prefs: dict[str, str] = {}
    raw_prefs = data.get("preferences")
    if isinstance(raw_prefs, dict):
        for key, value in raw_prefs.items():
            if key not in ALLOWED_PREFS or not isinstance(value, (str, int, float)):
                continue
            value = str(value).strip().lower()[:100] if key in ("level", "explanation_depth") \
                else str(value).strip()[:100]
            if not value:
                continue
            if key == "level" and value not in LEVELS:
                continue
            if key == "explanation_depth" and value not in DEPTHS:
                continue
            prefs[key] = value

    topic = data.get("topic")
    topic = topic.strip().lower()[:40] if isinstance(topic, str) and topic.strip() else None
    understanding = data.get("understanding")
    if understanding not in UNDERSTANDING:
        understanding = "neutral"
    return {"preferences": prefs, "topic": topic, "understanding": understanding}


def merge_interests(existing: str | None, new: str) -> str:
    """Interests accumulate (deduplicated, capped); every other preference is overwritten."""
    items: list[str] = []
    for part in f"{existing or ''},{new}".split(","):
        part = part.strip()
        if part and part.lower() not in (i.lower() for i in items):
            items.append(part)
    return ", ".join(items[-MAX_INTERESTS:])


def apply_extraction(store: MemoryStore, student: str, extraction: dict) -> dict[str, str]:
    """Write newly learned preferences to memory. Returns only what actually changed."""
    current = store.get_preferences(student)
    learned: dict[str, str] = {}
    for key, value in extraction.get("preferences", {}).items():
        if key == "interests":
            value = merge_interests(current.get("interests"), value)
        if current.get(key) != value:
            store.set_preference(student, key, value)
            learned[key] = value
    return learned


def extract_profile_update(complete: Callable[[list[dict]], str], user_msg: str, answer: str) -> dict:
    """Ask the LLM what this turn reveals about the student. Never raises."""
    messages = [
        {"role": "system", "content": EXTRACT_PROMPT},
        {"role": "user", "content": f"STUDENT message:\n{user_msg}\n\nTutor reply (context only):\n{answer[:600]}"},
    ]
    try:
        return parse_extraction(complete(messages))
    except Exception:
        return dict(DEFAULT_EXTRACTION, preferences={})
