# AI Rule-Based Symptom Checker

A lightweight, deterministic AI medical symptom checker built with pure Python. The application uses a forward-chaining rule-based reasoning engine to analyze patient symptoms, infer potential conditions with confidence scores, and recommend next steps via a Streamlit web interface.

Managed entirely via **`uv`**, eliminating Node/npm dependencies and external API security risks.

---

## Key Features

* **Pure Python Stack:** Zero JavaScript/npm build steps or external network dependencies.
* **Deterministic Inference Engine:** Uses forward-chaining propositional logic over production rules (`IF-THEN`) with confidence scoring.
* **Session State Memory:** Persists query history across user interactions within the active browser session.
* **Modern Package Management:** Fast, reproducible virtual environments powered by `uv`.

---

## How It Works

```
┌────────────────────────┐      ┌───────────────────────────┐
│   Streamlit Web UI     │ ───► │  Inference Engine         │
│   (app.py)             │      │  (engine.py)              │
│                        │      │                           │
│  - User Inputs         │      │  - Evaluates Rules        │
│  - Session State       │ ◄─── │  - Calculates Confidence  │
└────────────────────────┘      └───────────────────────────┘

```

1. **Knowledge Base (`engine.py`):** Defines production rules containing required symptoms, urgency levels, and medical advice.
2. **Inference Engine (`engine.py`):** Evaluates patient symptoms against rule sets, calculates percentage match confidence, and filters relevant diagnoses.
3. **Web Interface (`app.py`):** Renders the user dashboard, passes user inputs into the engine, and tracks analysis history using `st.session_state`.

---

## Project Structure

```text
.
├── app.py              # Streamlit Web UI and session memory logic
├── engine.py           # Medical knowledge base and forward-chaining inference engine
├── pyproject.toml      # Project configuration and dependencies managed by uv
├── uv.lock             # Deterministic dependency lockfile
└── README.md           # Documentation

```

---

## Prerequisites

Ensure you have **`uv`** installed on your system. If not, install it via:

* **Linux / macOS:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

```


* **Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

```


* **via Pip:**
```bash
pip install uv

```



---

## Getting Started

### 1. Clone or Open the Project Directory

Navigate to your project root folder:

```bash
cd medical-symptom-checker

```

### 2. Install Dependencies

Install Streamlit using `uv` (this creates a managed `.venv` and generates `uv.lock` automatically):

```bash
uv add streamlit

```

### 3. Run the Application

Start the Streamlit web interface directly through `uv`:

```bash
uv run streamlit run app.py

```

The application will automatically launch in your browser at `http://localhost:8501`.

---

## Handy `uv` Commands

| Action | Command |
| --- | --- |
| **Run Web App** | `uv run streamlit run app.py` |
| **Add New Package** | `uv add <package-name>` |
| **Remove Package** | `uv remove <package-name>` |
| **Sync Environment** | `uv sync` |
| **Run Python Script** | `uv run python engine.py` |