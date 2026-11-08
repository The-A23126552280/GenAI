import time

from memory import MemoryStore, tokenize

DAY = 86400


def make_store() -> MemoryStore:
    return MemoryStore(":memory:")


def test_tokenize_drops_stopwords_and_punctuation():
    assert tokenize("Explain the recursion, please!") == ["recursion"]


def test_preferences_roundtrip_and_overwrite():
    s = make_store()
    s.set_preference("Ravi", "level", "beginner")
    s.set_preference("ravi ", "level", "intermediate")  # same student, different casing/spacing
    assert s.get_preferences("RAVI") == {"level": "intermediate"}


def test_students_are_isolated():
    s = make_store()
    s.set_preference("ravi", "level", "beginner")
    s.add_interaction("ravi", "What is recursion?", "A function calling itself.", "recursion")
    assert s.get_preferences("anita") == {}
    assert s.search("anita", "recursion") == []
    assert s.count_interactions("anita") == 0


def test_delete_preference():
    s = make_store()
    s.set_preference("ravi", "tone", "casual")
    s.delete_preference("ravi", "tone")
    assert s.get_preferences("ravi") == {}


def test_search_finds_the_relevant_past_question():
    s = make_store()
    s.add_interaction("ravi", "Explain recursion with factorial", "Recursion is when a function calls itself.", "recursion")
    s.add_interaction("ravi", "How does photosynthesis work?", "Plants turn light into chemical energy.", "photosynthesis")
    s.add_interaction("ravi", "What is an SQL join?", "A join combines rows from two tables.", "sql joins")
    hits = s.search("ravi", "I forgot how recursion works")
    assert hits and hits[0]["topic"] == "recursion"
    assert all(h["topic"] != "photosynthesis" for h in hits)


def test_search_returns_nothing_for_unrelated_query():
    s = make_store()
    s.add_interaction("ravi", "Explain recursion", "A function calling itself.", "recursion")
    assert s.search("ravi", "capital of france") == []
    assert s.search("ravi", "") == []


def test_search_respects_k():
    s = make_store()
    for i in range(6):
        s.add_interaction("ravi", f"recursion example number {i}", "answer about recursion", "recursion")
    assert len(s.search("ravi", "recursion", k=2)) == 2


def test_recency_boost_prefers_newer_of_two_equal_matches():
    s = make_store()
    now = time.time()
    s.add_interaction("ravi", "explain recursion", "x", "recursion", ts=now - 60 * DAY)
    new_id = s.add_interaction("ravi", "explain recursion", "x", "recursion", ts=now - 1 * DAY)
    hits = s.search("ravi", "recursion", k=2, now=now)
    assert hits[0]["id"] == new_id


def test_top_topics_and_recent():
    s = make_store()
    for topic in ["recursion", "recursion", "sql joins"]:
        s.add_interaction("ravi", f"q about {topic}", "a", topic)
    assert s.top_topics("ravi")[0] == ("recursion", 2)
    assert s.count_interactions("ravi") == 3
    assert s.recent_interactions("ravi", 1)[0]["topic"] == "sql joins"


def test_forget_wipes_everything_for_that_student_only():
    s = make_store()
    for who in ("ravi", "anita"):
        s.set_preference(who, "level", "beginner")
        s.add_interaction(who, "q", "a", "t")
    s.forget("Ravi")
    assert s.get_preferences("ravi") == {} and s.count_interactions("ravi") == 0
    assert s.get_preferences("anita") == {"level": "beginner"} and s.count_interactions("anita") == 1


def test_memory_persists_across_store_instances(tmp_path):
    path = tmp_path / "mem.db"
    first = MemoryStore(path)
    first.set_preference("ravi", "learning_style", "analogies")
    first.add_interaction("ravi", "Explain recursion", "answer", "recursion")
    second = MemoryStore(path)  # simulates restarting the app
    assert second.get_preferences("ravi") == {"learning_style": "analogies"}
    assert second.search("ravi", "recursion")[0]["topic"] == "recursion"
