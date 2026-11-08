"""Experiment 6 - Personalized learning assistant with persistent memory.

Run:  uv run streamlit run app.py
"""
from __future__ import annotations

import os
from functools import partial

import streamlit as st
from dotenv import load_dotenv

import agent
import llm
from memory import MemoryStore, normalize_student

load_dotenv()
st.set_page_config(page_title="Personalized Learning Assistant", page_icon="🎓", layout="wide")

MAX_HISTORY_MESSAGES = 8  # short-term memory: last N chat messages sent to the model
LEVEL_OPTIONS = ["(not set)", "beginner", "intermediate", "advanced"]
DEPTH_OPTIONS = ["(not set)", "brief", "detailed"]


@st.cache_resource
def get_store() -> MemoryStore:
    return MemoryStore()


store = get_store()


def pretty(key: str) -> str:
    return key.replace("_", " ").title()


def render_trace(trace: dict) -> None:
    """Show exactly which memories shaped an answer (transparency for the demo)."""
    with st.expander("🧠 Memory used for this answer"):
        if trace["prefs"]:
            st.markdown("**Profile applied:** " + "; ".join(f"{pretty(k)} = {v}" for k, v in trace["prefs"].items()))
        else:
            st.markdown("**Profile applied:** none yet")
        if trace["recalled"]:
            st.markdown("**Recalled from past questions:**")
            for m in trace["recalled"]:
                st.markdown(f"- “{m['question']}” · {m['age']} · topic *{m['topic'] or 'n/a'}* · match {m['score']}")
        else:
            st.markdown("**Recalled from past questions:** nothing relevant")
        if trace["learned"]:
            st.markdown("**Newly learned:** " + "; ".join(f"{pretty(k)} = {v}" for k, v in trace["learned"].items()))
        st.caption(f"Detected topic: {trace['topic'] or 'n/a'} · understanding: {trace['understanding']}")


# ---------------------------------------------------------------- sidebar: identity
with st.sidebar:
    st.header("🎓 Student")
    name = st.text_input("Your name", placeholder="e.g. Ravi", help="Your name is your memory key: same name, same profile.")
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        api_key = st.text_input("Groq API key", type="password")
    model = st.text_input("Model", value=os.getenv("GROQ_MODEL", llm.DEFAULT_MODEL))

st.title("🎓 Personalized Learning Assistant")
st.caption("Remembers how you like to learn and what you have already asked, then adapts its explanations.")

if not name.strip():
    st.info("👈 Enter your name in the sidebar to load (or start) your learning profile.")
    st.stop()

sid = normalize_student(name)
if st.session_state.get("active_student") != sid:  # switching student starts a clean chat
    st.session_state.active_student = sid
    st.session_state.chat = []

# ---------------------------------------------------------------- sidebar: memory panel
prefs = store.get_preferences(sid)
with st.sidebar:
    st.divider()
    st.subheader("🧠 What I remember")
    if prefs:
        for key, value in prefs.items():
            st.markdown(f"**{pretty(key)}:** {value}")
    else:
        st.caption("Nothing yet. Tell me how you like to learn, or just start asking.")
    total = store.count_interactions(sid)
    st.caption(f"{total} past question{'s' if total != 1 else ''} stored")
    topics = store.top_topics(sid)
    if topics:
        st.caption("Top topics: " + ", ".join(f"{t} ({c})" for t, c in topics))

    with st.expander("✏️ Edit my profile"):
        with st.form("profile_form"):
            level = st.selectbox(
                "Level", LEVEL_OPTIONS, index=LEVEL_OPTIONS.index(prefs["level"]) if prefs.get("level") in LEVEL_OPTIONS else 0
            )
            depth = st.selectbox(
                "Explanation depth",
                DEPTH_OPTIONS,
                index=DEPTH_OPTIONS.index(prefs["explanation_depth"]) if prefs.get("explanation_depth") in DEPTH_OPTIONS else 0,
            )
            style = st.text_input("Learning style", value=prefs.get("learning_style", ""), placeholder="analogies, visual...")
            interests = st.text_input("Interests", value=prefs.get("interests", ""), placeholder="cricket, music...")
            if st.form_submit_button("Save profile"):
                for key, value in {
                    "level": level,
                    "explanation_depth": depth,
                    "learning_style": style.strip(),
                    "interests": interests.strip(),
                }.items():
                    if value and value != "(not set)":
                        store.set_preference(sid, key, value)
                    else:
                        store.delete_preference(sid, key)
                st.rerun()

    st.divider()
    if st.button("🆕 New chat (memory is kept)"):
        st.session_state.chat = []
        st.rerun()
    with st.expander("⚠️ Forget me"):
        confirm = st.checkbox("Delete my profile and every stored question")
        if st.button("Forget everything", disabled=not confirm):
            store.forget(sid)
            st.session_state.chat = []
            st.rerun()

# ---------------------------------------------------------------- main: chat
if not st.session_state.chat:
    recent = store.recent_interactions(sid, 3)
    if recent:
        covered = ", ".join(dict.fromkeys(r["topic"] or r["question"][:40] for r in recent))
        st.info(f"👋 Welcome back, {name.strip()}! Last time we covered: {covered}.")

for msg in st.session_state.chat:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("trace"):
            render_trace(msg["trace"])

if prompt := st.chat_input("What would you like to learn today?"):
    if not api_key:
        st.error("Add your Groq API key in the sidebar (or in a .env file).")
        st.stop()

    with st.chat_message("user"):
        st.markdown(prompt)

    # 1) RETRIEVE: profile + relevant past questions (searched BEFORE saving this turn)
    current_prefs = store.get_preferences(sid)
    memories = store.search(sid, prompt, k=3)

    # 2) AUGMENT: build the personalised prompt; short-term memory = recent chat turns
    system = agent.build_system_prompt(name.strip(), current_prefs, memories)
    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat[-MAX_HISTORY_MESSAGES:]]
    messages = [{"role": "system", "content": system}, *history, {"role": "user", "content": prompt}]

    # 3) GENERATE
    client = llm.get_client(api_key)
    with st.chat_message("assistant"):
        try:
            answer = st.write_stream(llm.chat_stream(client, model, messages))
        except Exception as exc:  # network, bad key, wrong model id...
            st.error(f"LLM request failed: {exc}")
            st.stop()

        # 4) UPDATE MEMORY: learn preferences/topic/understanding, then store the turn
        with st.spinner("Updating memory..."):
            extraction = agent.extract_profile_update(partial(llm.chat_once, client, model), prompt, answer)
            learned = agent.apply_extraction(store, sid, extraction)
            store.add_interaction(sid, prompt, answer, extraction["topic"], extraction["understanding"])

    trace = {
        "prefs": current_prefs,
        "recalled": [
            {"question": m["question"], "topic": m["topic"], "age": agent.humanize_age(m["ts"]), "score": m["score"]}
            for m in memories
        ],
        "learned": learned,
        "topic": extraction["topic"],
        "understanding": extraction["understanding"],
    }
    st.session_state.chat += [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": answer, "trace": trace},
    ]
    st.rerun()  # refresh the sidebar memory panel with what was just learned
