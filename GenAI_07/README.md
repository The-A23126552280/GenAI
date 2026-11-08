# Financial Assistant Agent (Experiment 7)

A Streamlit-based AI agent that uses **external tools** via Groq's
OpenAI-compatible API:

| Tool               | Purpose                                            |
| ------------------ | -------------------------------------------------- |
| `calculate_emi`    | Compute monthly EMI, total interest, total payment |
| `get_stock_price`  | Fetch latest quote via `yfinance`                  |
| `get_company_info` | Fetch sector, market cap, P/E, summary             |

## Setup

```bash
uv sync
cp .env.example .env        # then fill in GROQ_API_KEY
uv run streamlit run app.py
```

## Run tests

```bash
uv run pytest -v
```

## How the agent works

1. User sends a message.
2. LLM receives the message + tool schemas.
3. If it emits a `tool_calls` block, the agent executes the function and
   appends the result as a `tool` message.
4. The LLM is called again with the tool result, and may call more tools
   (up to 5 rounds) or produce a final text reply.

This is a minimal ReAct-style loop using only the OpenAI SDK — no LangChain,
no LlamaIndex.
