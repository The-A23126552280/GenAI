# Tuning.md — Rate-Limit & Resilience Patch Strategy

This document records the concrete strategies applied to keep the multi-agent research paper generator usable on **Groq free tier** (and similar constrained providers) in late 2026.

---

## 1. Problem Statement

A single paper generation run typically issues **4–8+ LLM calls**:

| Step               | Calls (typical) |
| ------------------ | --------------- |
| Research fallback  | 0–1             |
| Writer (draft)     | 1               |
| Editor             | 1               |
| Writer (revisions) | 0–3             |
| Editor (revisions) | 0–3             |

Groq free-tier limits for the main chat models (`qwen/qwen3.8-27b`, `openai/gpt-oss-20b`, `openai/gpt-oss-120b`) are roughly:

- **30 requests / minute**
- **~8 000 tokens / minute**
- **1 000 requests / day**
- **~200 000 tokens / day**

Limits are **per model, per organization**. Switching models helps only while that model’s own minute budget remains. Once several models are exhausted in the same minute window, 429s appear regardless of which model is selected.

The original code used a fixed ~60 s wait (or a brittle regex parse of the error string). That was insufficient under sustained multi-call load.

---

## 2. Patch Strategy (Ordered by Impact)

### 2.1 Model Selection (Highest leverage, zero code)

Prefer models that still have remaining free-tier quota and that generate fewer tokens for the same quality:

```bash
# .env
LLM_PROVIDER=groq
LLM_MODEL_NAME=openai/gpt-oss-20b          # fastest / cheapest free option
# LLM_MODEL_NAME=openai/gpt-oss-120b      # stronger, still free-tier
# LLM_MODEL_NAME=qwen/qwen3.8-27b         # original default (often rate-limited first)
```

`qwen-2.5-32b` is **deprecated** (shutdown April 2025). Never use it.

### 2.2 Reduce Token Burn

Lower the `max_tokens` arguments so each call stays well under the 8 k TPM ceiling:

| Agent             | Original | Tuned recommendation |
| ----------------- | -------- | -------------------- |
| Writer            | 800      | 400–500              |
| Editor            | 300      | 150–200              |
| Research fallback | 800      | 400–600              |

Location: `src/agents.py` (the three `get_llm_response(..., max_tokens=...)` calls).

### 2.3 Fewer Revision Loops

```bash
# .env
MAX_REVISIONS=1          # or 2
REVIEW_THRESHOLD=7       # slightly easier approval
```

One forced revision cycle cuts roughly half the LLM traffic.

### 2.4 Stronger Rate-Limit Handling (`src/llm.py`)

The production patch replaces the original fixed-wait logic with:

1. **Prefer the `Retry-After` header** when LiteLLM / Groq supplies it.
2. **Exponential backoff + light jitter** when the header is absent:
   ```python
   wait_time = min(90.0, (2 ** attempt) * 10) + (attempt * 1.0)
   ```
3. Up to **5 retries** (was 4).
4. Proper logging instead of bare `print`.

This turns a 5–15 s thrash into a 10 → 20 → 40 → 80 s recovery curve that actually lets the minute token bucket refill.

### 2.5 Optional Inter-Agent Sleep

When even the stronger backoff is insufficient, insert a short deliberate pause at the start of each agent:

```python
import time
time.sleep(3)   # or 5
```

This spreads the calls across the minute window and is especially useful when running the full research → write → edit path in one shot.

### 2.6 Single Graph Invocation

The original Streamlit app called both `graph.stream(...)` **and** `graph.invoke(...)`, doubling every LLM call. The patch removes the second invocation so the pipeline runs exactly once per button click.

### 2.7 Robust Editor JSON Parsing

Editor failures previously forced an extra revision loop (because `is_approved` became `False`). The patch extracts the first JSON object even when the model wraps it in markdown fences or adds surrounding text, reducing spurious re-runs.

---

## 3. Recommended Baseline Configuration (Free Tier)

```bash
# .env
LLM_PROVIDER=groq
LLM_MODEL_NAME=openai/gpt-oss-20b
GROQ_API_KEY=gsk_...
TAVILY_API_KEY=tvly_...          # optional but recommended (avoids research LLM call)

REVIEW_THRESHOLD=7
MAX_REVISIONS=1
```

And in `src/agents.py`:

```python
# writer
max_tokens=500
# editor
max_tokens=200
# research fallback
max_tokens=500
```

With these settings a typical paper generation stays inside free-tier limits for most users.

---

## 4. Escalation Path

| Situation                        | Action                                       |
| -------------------------------- | -------------------------------------------- |
| Still 429 after all of the above | Increase inter-agent sleep to 5–8 s          |
| Multiple concurrent users / tabs | Only one Streamlit session at a time         |
| Need higher throughput           | Upgrade Groq account to **Developer** tier   |
| Want independent quota           | Point LiteLLM at another free provider       |
| Debugging                        | `litellm.turn_on_debug()` or raise log level |

---

## 5. Code Locations of the Patches

| Concern                    | File                | What changed                                         |
| -------------------------- | ------------------- | ---------------------------------------------------- |
| Model default              | `src/llm.py`        | Default → `qwen/qwen3.8-27b` (then override via env) |
| Rate-limit retry logic     | `src/llm.py`        | Retry-After + exponential backoff + logging          |
| Token budgets              | `src/agents.py`     | Lower `max_tokens` values                            |
| Revision count / threshold | `.env` / `graph.py` | `MAX_REVISIONS`, `REVIEW_THRESHOLD`                  |
| Double execution           | `app.py`            | Single `graph.invoke()` only                         |
| Fragile JSON               | `src/agents.py`     | Regex + fence-tolerant extraction                    |
| Env loading                | `app.py`            | `load_dotenv()` at startup                           |

---

## 6. Design Principles Used

1. **Prefer configuration over code** — model, thresholds, and revision limits live in `.env`.
2. **Fail soft, then back off** — never spin tightly on 429s.
3. **Burn fewer tokens first** — reducing `max_tokens` and revision count is cheaper than waiting.
4. **One invocation path** — avoid accidental double work.
5. **Tolerate imperfect model output** — especially for structured JSON from the editor.

These principles keep the system runnable on free tiers while remaining easy to open up when a paid or higher-quota provider is available.
