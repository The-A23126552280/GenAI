"""Persistent memory for the learning assistant.

Two kinds of long-term memory live in one SQLite file (stdlib only, no extra deps):

* Semantic memory  -> `preferences`: what we know about the student
                      (level, learning style, interests, ...).
* Episodic memory  -> `interactions`: every question the student asked, the answer
                      given, the topic, and how well they seemed to understand it.

`search()` retrieves the most relevant past interactions for a new question using a
small TF-IDF cosine similarity plus a recency boost.
"""
from __future__ import annotations

import math
import re
import sqlite3
import threading
import time
from collections import Counter
from pathlib import Path

DB_PATH = Path(__file__).parent / "memory.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS preferences (
    student    TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (student, key)
);
CREATE TABLE IF NOT EXISTS interactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student       TEXT NOT NULL,
    ts            REAL NOT NULL,
    question      TEXT NOT NULL,
    answer        TEXT NOT NULL,
    topic         TEXT,
    understanding TEXT
);
CREATE INDEX IF NOT EXISTS idx_interactions_student_ts ON interactions (student, ts);
"""

STOPWORDS = frozenset(
    """a an the is are was were be been am i you he she it we they me my your our
    of in on at to for from with about as by and or but if then so than that this
    these those what which who whom how why when where do does did can could should
    would will shall may might please explain tell show give us again more just also
    not no yes""".split()
)


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens without stopwords or single characters."""
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1 and t not in STOPWORDS]


def normalize_student(name: str) -> str:
    """Student ids are case-insensitive so 'Ravi' and 'ravi ' share one profile."""
    return name.strip().lower()


class MemoryStore:
    def __init__(self, path: str | Path = DB_PATH):
        self._lock = threading.Lock()  # Streamlit serves sessions from several threads
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    # ---- low-level helper -------------------------------------------------
    def _run(self, sql: str, params: tuple = (), *, fetch: bool = False):
        with self._lock:
            cur = self.conn.execute(sql, params)
            rows = cur.fetchall() if fetch else None
            self.conn.commit()
            return rows if fetch else cur.lastrowid

    # ---- semantic memory: the student profile -----------------------------
    def set_preference(self, student: str, key: str, value: str) -> None:
        self._run(
            "INSERT INTO preferences (student, key, value, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(student, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (normalize_student(student), key, value, time.time()),
        )

    def get_preferences(self, student: str) -> dict[str, str]:
        rows = self._run(
            "SELECT key, value FROM preferences WHERE student=? ORDER BY key",
            (normalize_student(student),),
            fetch=True,
        )
        return {r["key"]: r["value"] for r in rows}

    def delete_preference(self, student: str, key: str) -> None:
        self._run("DELETE FROM preferences WHERE student=? AND key=?", (normalize_student(student), key))

    # ---- episodic memory: past questions ----------------------------------
    def add_interaction(
        self,
        student: str,
        question: str,
        answer: str,
        topic: str | None = None,
        understanding: str | None = None,
        ts: float | None = None,
    ) -> int:
        return self._run(
            "INSERT INTO interactions (student, ts, question, answer, topic, understanding) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (normalize_student(student), ts or time.time(), question, answer, topic, understanding),
        )

    def recent_interactions(self, student: str, n: int = 5) -> list[dict]:
        rows = self._run(
            "SELECT id, ts, question, topic, understanding FROM interactions "
            "WHERE student=? ORDER BY ts DESC, id DESC LIMIT ?",
            (normalize_student(student), n),
            fetch=True,
        )
        return [dict(r) for r in rows]

    def count_interactions(self, student: str) -> int:
        rows = self._run(
            "SELECT COUNT(*) AS c FROM interactions WHERE student=?",
            (normalize_student(student),),
            fetch=True,
        )
        return rows[0]["c"]

    def top_topics(self, student: str, n: int = 5) -> list[tuple[str, int]]:
        rows = self._run(
            "SELECT topic, COUNT(*) AS c FROM interactions "
            "WHERE student=? AND topic IS NOT NULL AND topic != '' "
            "GROUP BY topic ORDER BY c DESC, MAX(ts) DESC LIMIT ?",
            (normalize_student(student), n),
            fetch=True,
        )
        return [(r["topic"], r["c"]) for r in rows]

    # ---- retrieval --------------------------------------------------------
    def search(
        self,
        student: str,
        query: str,
        k: int = 3,
        min_score: float = 0.08,
        now: float | None = None,
    ) -> list[dict]:
        """Return up to k past interactions most relevant to `query`.

        Score = TF-IDF cosine similarity (question and topic weighted x2 over the first
        300 chars of the answer) multiplied by a small recency boost that fades over
        ~2 weeks. Results below `min_score` are dropped so unrelated history is never
        injected into the prompt.
        """
        rows = self._run(
            "SELECT id, ts, question, answer, topic, understanding FROM interactions "
            "WHERE student=? ORDER BY ts DESC LIMIT 500",
            (normalize_student(student),),
            fetch=True,
        )
        query_tokens = tokenize(query)
        if not rows or not query_tokens:
            return []

        now = now or time.time()
        docs = [
            Counter(
                tokenize(r["question"]) * 2
                + tokenize(r["topic"] or "") * 2
                + tokenize(r["answer"][:300])
            )
            for r in rows
        ]
        n = len(docs)
        df: Counter = Counter()
        for d in docs:
            df.update(d.keys())
        idf = {t: math.log((n + 1) / (df[t] + 1)) + 1 for t in df}

        # Query terms that never appear in this student's history carry no signal.
        q_vec = {t: c * idf[t] for t, c in Counter(query_tokens).items() if t in idf}
        if not q_vec:
            return []
        q_norm = math.sqrt(sum(w * w for w in q_vec.values()))

        scored = []
        for row, doc in zip(rows, docs):
            d_vec = {t: c * idf[t] for t, c in doc.items()}
            d_norm = math.sqrt(sum(w * w for w in d_vec.values())) or 1.0
            dot = sum(w * d_vec.get(t, 0.0) for t, w in q_vec.items())
            cosine = dot / (q_norm * d_norm)
            age_days = max(0.0, (now - row["ts"]) / 86400)
            score = cosine * (1 + 0.15 * math.exp(-age_days / 14))
            if score >= min_score:
                scored.append({**dict(row), "score": round(score, 3)})

        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:k]

    # ---- privacy ----------------------------------------------------------
    def forget(self, student: str) -> None:
        sid = normalize_student(student)
        self._run("DELETE FROM preferences WHERE student=?", (sid,))
        self._run("DELETE FROM interactions WHERE student=?", (sid,))
