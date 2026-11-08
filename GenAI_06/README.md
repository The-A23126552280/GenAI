# Experiment 6: Adaptive Learning Assistant with Memory

**Aim:** implement an adaptive agent that stores and retrieves conversation context.
**Case study:** a personalized learning assistant that remembers a student's learning
preferences and previous questions to give customized explanations.

**Stack:** Python managed with [uv](https://docs.astral.sh/uv/), Streamlit UI, Groq LLM
(`openai/gpt-oss-120b`), SQLite for memory (stdlib, no vector DB needed).

---

## 1. How the memory works

| Memory type            | What it holds                                                             | Where                 | Lifetime                      |
| ---------------------- | ------------------------------------------------------------------------- | --------------------- | ----------------------------- |
| **Short-term**         | The last 8 chat messages                                                  | `st.session_state`    | Until "New chat" or tab close |
| **Semantic (profile)** | Level, learning style, depth, interests, tone, language                   | SQLite `preferences`  | Permanent, per student        |
| **Episodic**           | Every past question + answer + topic + how well they seemed to understand | SQLite `interactions` | Permanent, per student        |

Each turn runs a four-step loop (see `app.py`):

```
 student asks ──► 1. RETRIEVE   profile + top-3 relevant past questions (TF-IDF + recency)
                  2. AUGMENT    build a personalised system prompt (agent.build_system_prompt)
                  3. GENERATE   stream the answer from Groq
                  4. UPDATE     a 2nd low-temperature LLM call extracts any stated preference,
                                the topic, and an understanding signal (confused/neutral/confident);
                                the turn is saved to SQLite
```

**What makes it adaptive** (not just a chatbot with history):

- States "I'm a beginner, I like analogies" once, and every later answer, even after an app restart, uses that.
- `interests` accumulate, so examples can be drawn from what the student cares about.
- If a related earlier question was marked `confused`, the prompt tells the tutor to slow down, use smaller steps and end with a check question.
- The student can see (🧠 _Memory used for this answer_), edit (✏️ _Edit my profile_) and delete (⚠️ _Forget me_) everything the agent remembers.

## 2. Run it

```bash
# one-time: install uv  ->  https://docs.astral.sh/uv/getting-started/installation/
uv sync                       # creates .venv and installs from pyproject.toml
cp .env.example .env          # then put your Groq key in it (https://console.groq.com/keys)
uv run streamlit run app.py   # opens http://localhost:8501
uv run pytest                 # 21 unit tests (memory + agent logic, no network needed)
```

No `.env`? Paste the key into the sidebar instead. Model name is also editable there.

## 3. Demo script for evaluation

1. **Cold start.** Name: `Ravi`. Ask: _"I'm a beginner and I learn best with real-life analogies. I love cricket. Explain recursion."_
   Sidebar now shows Level = beginner, Learning style = real-life analogies, Interests = cricket. Expand _Memory used_: "Newly learned" lists them.
2. **Struggle signal.** Ask: _"I still don't get recursion."_ The turn is stored with understanding = `confused`.
3. **Prove persistence.** Stop the server (Ctrl+C), start it again, enter `Ravi`. A _Welcome back_ banner lists past topics.
4. **Prove retrieval + adaptation.** Ask: _"Explain binary trees, they look like recursion."_
   _Memory used_ shows the two recursion questions recalled, and the answer should build on them with cricket analogies in small steps.
5. **Prove isolation.** Enter a different name: empty profile, none of Ravi's data.
6. **Inspect the raw memory:** `sqlite3 memory.db "select * from preferences; select question, topic, understanding from interactions;"`

## 4. Files

| File        | Role                                                                                      |
| ----------- | ----------------------------------------------------------------------------------------- |
| `app.py`    | Streamlit UI and the retrieve → augment → generate → update loop                          |
| `agent.py`  | Prompt builder, preference extractor/validator, memory updater (pure Python, unit-tested) |
| `memory.py` | SQLite store + TF-IDF retrieval with recency boost (pure Python, unit-tested)             |
| `llm.py`    | Groq client (OpenAI-compatible API), streaming + one-shot calls                           |
| `tests/`    | 21 tests, including a simulated "second session" end-to-end check                         |
| `memory.db` | Created on first run; your students' memory (git-ignored)                                 |

## 5. Design decisions (likely viva questions)

- **Why SQLite instead of a vector database?** The corpus is one student's questions (tens to hundreds of rows). TF-IDF cosine over that is accurate enough, has zero dependencies, and is easy to explain. Swapping `MemoryStore.search` for embeddings is a one-function change.
- **Why a second LLM call to update memory?** Separating "teach" from "learn about the student" keeps the answer prompt clean and lets the extractor run at temperature 0 with a strict JSON schema. The output is validated (`parse_extraction`): unknown keys, bad levels and malformed JSON are dropped, so a bad generation can never corrupt the profile.
- **Why search before saving the turn?** Otherwise the question would retrieve itself.
- **Why a similarity threshold?** Unrelated history is worse than none; below `min_score` nothing is injected.
- **Why `openai/gpt-oss-120b`, not `groq/compound-mini`?** Compound adds automatic web-search/code tools, which is unwanted for a tutor that must stay grounded in its memory, and complicates strict-JSON extraction.
- **Model got a 404?** Groq retires models often (`llama-3.3-70b-versatile` shut down on 2026-08-16). List what your key can use with the command in section 8, then set `GROQ_MODEL` in `.env`.
- **Privacy:** memory is stored in plaintext locally, is visible to the student, and can be erased with _Forget me_.

## 6. Limitations

- Identity is just the typed name (no authentication); two people using the same name share a profile.
- Keyword retrieval misses paraphrases that share no words ("recursive function" vs "function calling itself"); embeddings would fix this.
- Preference extraction depends on the LLM; it is conservative by design but can still mis-read sarcasm. The edit form lets the student correct it.
- "Understanding" is a heuristic signal from the student's wording, not a graded assessment.

## 7. Optional: the same agent in n8n

The loop maps onto nodes directly: **Webhook** → **Postgres/Data Table** (load profile + search past questions) → **Edit Fields** (build the system prompt) → **HTTP Request** to Groq → a second **HTTP Request** (extraction) → **Postgres** (save) → **Respond to Webhook**. Alternatively, n8n's **AI Agent** node with a Groq chat model plus a **Postgres Chat Memory** sub-node gives per-session memory out of the box, but not the structured profile, which is the point of this experiment, so the Streamlit version is the primary deliverable.

## 8. Troubleshooting: "model does not exist or you do not have access"

List the models your API key can actually call (the authoritative answer):

```bash
uv run python -c "import os; from dotenv import load_dotenv; load_dotenv(); from llm import get_client; [print(m.id) for m in sorted(get_client(os.environ['GROQ_API_KEY']).models.list().data, key=lambda m: m.id)]"
```

Cross-check on the website: <https://console.groq.com/docs/models> (current models),
<https://console.groq.com/docs/deprecations> (shutdown dates and recommended replacements) and the
model dropdown in the Playground at <https://console.groq.com/playground>.
Then put your choice in `.env` as `GROQ_MODEL=...` (or type it into the sidebar's _Model_ box to test instantly).
