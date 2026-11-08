import json
import time

import agent
from memory import MemoryStore


def test_parse_extraction_plain_json():
    raw = json.dumps({"preferences": {"level": "Beginner", "learning_style": "analogies"},
                      "topic": "Recursion", "understanding": "confused"})
    out = agent.parse_extraction(raw)
    assert out == {"preferences": {"level": "beginner", "learning_style": "analogies"},
                   "topic": "recursion", "understanding": "confused"}


def test_parse_extraction_handles_code_fences_and_chatter():
    raw = 'Sure! ```json\n{"preferences": {}, "topic": "sql joins", "understanding": "neutral"}\n```'
    assert agent.parse_extraction(raw)["topic"] == "sql joins"


def test_parse_extraction_rejects_garbage_and_bad_values():
    assert agent.parse_extraction("no json here") == {"preferences": {}, "topic": None, "understanding": "neutral"}
    assert agent.parse_extraction("{not valid json}")["preferences"] == {}
    out = agent.parse_extraction(json.dumps({
        "preferences": {"level": "wizard", "favourite_colour": "blue", "explanation_depth": "brief", "tone": ""},
        "topic": 42, "understanding": "sleepy"}))
    assert out["preferences"] == {"explanation_depth": "brief"}  # bad level, unknown key, empty value dropped
    assert out["topic"] is None and out["understanding"] == "neutral"


def test_merge_interests_dedupes_and_accumulates():
    assert agent.merge_interests("cricket, music", "Music, football") == "cricket, music, football"
    assert agent.merge_interests(None, "chess") == "chess"


def test_apply_extraction_reports_only_changes():
    store = MemoryStore(":memory:")
    ext = {"preferences": {"level": "beginner", "interests": "cricket"}, "topic": "t", "understanding": "neutral"}
    assert agent.apply_extraction(store, "ravi", ext) == {"level": "beginner", "interests": "cricket"}
    assert agent.apply_extraction(store, "ravi", ext) == {}  # nothing new the second time
    ext2 = {"preferences": {"interests": "chess"}, "topic": "t", "understanding": "neutral"}
    agent.apply_extraction(store, "ravi", ext2)
    assert store.get_preferences("ravi")["interests"] == "cricket, chess"


def test_build_system_prompt_includes_profile_and_recalled_memory():
    now = time.time()
    prompt = agent.build_system_prompt(
        "Ravi",
        {"level": "beginner", "learning_style": "analogies"},
        [{"ts": now - 3 * 86400, "question": "Explain recursion", "topic": "recursion", "understanding": "confused"}],
        now=now,
    )
    assert "tutoring Ravi" in prompt
    assert "level: beginner" in prompt and "learning style: analogies" in prompt
    assert 'Asked: "Explain recursion"' in prompt and "3 days ago" in prompt and "seemed confused" in prompt


def test_build_system_prompt_cold_start():
    prompt = agent.build_system_prompt("Ravi", {}, [])
    assert "Nothing known yet" in prompt and "None relevant" in prompt


def test_humanize_age():
    now = 1_000_000.0
    assert agent.humanize_age(now - 5, now) == "just now"
    assert agent.humanize_age(now - 300, now) == "5 min ago"
    assert agent.humanize_age(now - 7200, now) == "2 h ago"
    assert agent.humanize_age(now - 86400, now) == "1 day ago"


def test_extract_profile_update_uses_injected_llm_and_never_raises():
    fake = lambda msgs: '{"preferences": {"level": "beginner"}, "topic": "loops", "understanding": "neutral"}'
    assert agent.extract_profile_update(fake, "I'm a beginner. What is a loop?", "A loop repeats...")["preferences"] == {"level": "beginner"}

    def boom(msgs):
        raise RuntimeError("network down")
    assert agent.extract_profile_update(boom, "hi", "hello") == {"preferences": {}, "topic": None, "understanding": "neutral"}


def test_end_to_end_memory_makes_the_second_session_personalised():
    """Session 1 teaches the agent; a brand-new 'session' (new prompt build) uses what it learned."""
    store = MemoryStore(":memory:")
    ext = agent.parse_extraction('{"preferences": {"level": "beginner", "learning_style": "real-life analogies"},'
                                 ' "topic": "recursion", "understanding": "confused"}')
    agent.apply_extraction(store, "ravi", ext)
    store.add_interaction("ravi", "I'm a beginner, explain recursion with analogies", "Think of mirrors...", "recursion", "confused")

    memories = store.search("ravi", "still confused about recursion")
    prompt = agent.build_system_prompt("Ravi", store.get_preferences("ravi"), memories)
    assert "level: beginner" in prompt and "real-life analogies" in prompt
    assert "recursion" in prompt and "seemed confused" in prompt
