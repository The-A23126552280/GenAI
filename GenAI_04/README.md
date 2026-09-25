# ANITS Admission Assistant — Conversational AI Agent

**Experiment 4:** Implementation of an LLM-powered conversational agent using prompt
engineering and API integration.

**Case Study:** A college admission chatbot for ANITS (Anil Neerukonda Institute of
Technology and Sciences, Visakhapatnam) that answers student queries about courses,
eligibility, fees, and admission procedures — with a custom web UI and synchronized
text-to-speech read-out.

---

## 1. What this project demonstrates

| Requirement | How it's satisfied |
|---|---|
| **Prompt engineering** | A system prompt defines the bot's persona, tone, and a grounded knowledge base (ANITS courses, eligibility, fees, admission steps) so the LLM answers only from real data instead of hallucinating. |
| **API integration** | Two authenticated server-side calls to Groq's API — one for chat completions (the LLM reply), one for text-to-speech (spoken audio). |
| **User interface** | A custom two-panel HTML webpage (`anits2.html`) with a live dark-themed chat sidebar and synchronized audio playback — no n8n login required to use it. |

---

## 2. Project structure

```
├── README.md              ← you are here
├── anits2.html            ← standalone frontend (chat UI + synced TTS playback)
└── (n8n workflows)        ← built/hosted in your n8n instance, not local files:
      ├── "College Admission Chatbot"   → handles chat replies
      └── "ANITS TTS Proxy"             → handles audio generation
```

> n8n workflows live inside your n8n instance (self-hosted via Docker). If you need
> to hand this project to someone else, export both workflows as JSON from n8n
> (Workflow menu → Download) and include them here.

---

## 3. Architecture overview

```
anits2.html (browser)
   │
   ├── POST /webhook/chat  ──▶  Webhook
   │                              → Edit Fields   (builds systemPrompt + reads $json.body.text)
   │                              → HTTP Request  (Groq chat completions API)
   │                              → Edit Fields1  (extracts reply → "output")
   │                              ◀── returns [{ "output": "<reply text>" }]
   │
   └── POST /webhook/tts   ──▶  Webhook
                                  → HTTP Request  (Groq text-to-speech API)
                                  → Respond to Webhook (binary .wav)
                                  ◀── returns raw audio bytes
```

- **LLM used:** `groq/compound-mini` (Groq's agentic chat model) via
  `https://api.groq.com/openai/v1/chat/completions`
- **TTS model used:** `canopylabs/orpheus-v1-english` via
  `https://api.groq.com/openai/v1/audio/speech`
- **Why two separate n8n workflows:** keeps chat and audio generation independently
  testable, and keeps the Groq API key inside n8n's credentials only — never exposed
  in browser JavaScript.

---

## 4. How to run this project

### 4.1 Prerequisites
- A running n8n instance (this project used self-hosted n8n via Docker).
- A free [Groq](https://console.groq.com) account and API key (`gsk_...`).
- A modern web browser.

### 4.2 Set up n8n
1. Import or rebuild the two workflows described in `progress.md` section 6 and 9.1:
   - **College Admission Chatbot** — Webhook (`/chat`) → Edit Fields → HTTP Request
     (Groq chat completions) → Edit Fields1.
   - **ANITS TTS Proxy** — Webhook (`/tts`) → HTTP Request (Groq TTS) → Respond to
     Webhook (binary).
2. Add your Groq API key as a Header Auth credential (`Authorization: Bearer
   gsk_...`) and reuse it across both HTTP Request nodes.
3. In each Webhook node, set **Allowed Origins (CORS)** to the domain you'll serve
   `anits.html` from (use `*` for local testing only — tighten before submission).
4. **Publish** both workflows so their **Production URLs** go live.

### 4.3 Set up the frontend
1. Open `anits2.html`.
2. Confirm the two webhook URLs at the top of the `<script>` block point to your
   n8n instance:
   ```js
   const CHAT_WEBHOOK_URL = 'http://localhost:5678/webhook/chat';
   const TTS_WEBHOOK_URL = 'http://localhost:5678/webhook/tts';
   ```
   (`5678` is n8n's default local Docker port — update the host/port if your
   n8n instance runs elsewhere, or swap in your production domain.)
3. Serve the file with a local server (don't just double-click it):
   ```bash
   python3 -m http.server 5500
   ```
4. Visit `http://localhost:5500/anits2.html` in your browser.

### 4.4 Test it
- Ask something like *"What is the B.Tech fee?"* — you should see a grounded text
  reply appear, revealed word-by-word in sync with spoken audio.

---

## 5. Editing the chatbot's knowledge

All of ANITS's course/fee/eligibility data lives in the **`systemPrompt`** field of
the "Edit Fields" node in the chatbot workflow. To update information (e.g. new fee
structure for a new academic year), edit the text there directly — no code changes
needed elsewhere.

---

## 6. Known limitations

- Fee and admission data is based on publicly available info at the time of
  building this project and may not reflect the latest official ANITS figures —
  intended as an academic demo, not a live production system.
- `groq/compound-mini` is an agentic model with built-in tool-calling (web search,
  code execution). This can occasionally introduce slightly longer response times.
  Swap to `llama-3.3-70b-versatile` in the HTTP Request body for fully
  deterministic, prompt-only behavior if preferred.
- TTS input is truncated under ~180 characters to avoid errors — very long replies
  will be read aloud only up to that point, even though the full text is shown.
- CORS is currently permissive (`*`) for development; restrict to your actual
  hosting domain before any public deployment.

---

## 7. Credits / Stack

- **Workflow engine:** [n8n](https://n8n.io) (self-hosted, Docker)
- **LLM + TTS provider:** [Groq](https://groq.com)
- **Frontend:** Vanilla HTML/CSS/JS (no framework)
- Built as part of **Experiment 4** for the AI/LLM agents coursework.
