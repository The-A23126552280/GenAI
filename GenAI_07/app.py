"""Streamlit chat UI for the financial assistant agent."""

import streamlit as st

from agent import run_agent

st.set_page_config(page_title="Financial Assistant", page_icon="💰")
st.title("💰 Financial Assistant")
st.caption("Ask about loan EMIs, stock prices, or company fundamentals.")

# Sidebar: model override
with st.sidebar:
    st.header("Settings")
    model = st.text_input("Groq model", value="openai/gpt-oss-120b")
    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()

# Initialise chat history
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hi! I can calculate EMIs, fetch stock prices, and look up company info. What would you like to know?",
        }
    ]

# Render history
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# User input
if prompt := st.chat_input("e.g. What's my EMI for a ₹10L loan at 8.5% for 5 years?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            reply = run_agent(prompt, model=model)
        st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})
