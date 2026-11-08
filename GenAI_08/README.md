# Multi-Agent Research Paper Generator

Experiment 8 — a LangGraph multi-agent system that researches a topic, writes an academic draft, and iteratively revises it until an editor agent approves the quality (or a revision limit is hit).

**Updated for late 2026** (Groq model catalog, LiteLLM, LangGraph, rate-limit resilience).

## Features

- **Research agent** — Tavily web search with LLM fallback
- **Writer agent** — produces / revises a 400–600 word academic draft
- **Editor agent** — structured JSON peer review (score 1–10 + feedback)
- Conditional loop with hard revision cap (no infinite loops)
- Robust rate-limit handling for Groq free-tier TPM/RPM limits
- Streamlit UI

## Quick start

```bash
# 1. Clone / unzip and enter the project
cd research-paper-agent

# 2. Create a virtualenv (recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -e .

# 4. Configure environment
cp .env.example .env
# Edit .env and set at least GROQ_API_KEY

# 5. Run the app
streamlit run app.py
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `groq` | LiteLLM provider prefix |
| `LLM_MODEL_NAME` | `qwen/qwen3.8-27b` | Model ID (must exist on the provider) |
| `GROQ_API_KEY` | — | Required for Groq |
| `TAVILY_API_KEY` | — | Optional; enables real web search |
| `REVIEW_THRESHOLD` | `8` | Score ≥ this value → approve |
| `MAX_REVISIONS` | `3` | Max write cycles before forced finish |

### Model notes (Nov 2026)

`qwen-2.5-32b` was deprecated in April 2025. The default is now `qwen/qwen3.8-27b` (still on Groq free tier with the usual per-model rate limits). Other solid free-tier choices:

- `openai/gpt-oss-20b` — faster / cheaper
- `openai/gpt-oss-120b` — stronger reasoning

Set `LLM_MODEL_NAME` accordingly.

## Project layout

```
research-paper-agent/
├── app.py                 # Streamlit entrypoint
├── pyproject.toml
├── .env.example
├── README.md
└── src/
    ├── __init__.py
    ├── state.py           # PaperState + EditorFeedback
    ├── llm.py             # LiteLLM wrapper + rate-limit retries
    ├── tools.py           # Tavily search
    ├── agents.py          # research / writer / editor nodes
    └── graph.py           # LangGraph StateGraph definition
```

## Architecture

```
research → write → edit ⇄ write (while not approved and under max revisions)
                      ↓
                     END
```

Each node returns a partial dict that LangGraph merges into `PaperState`.

## License

MIT
