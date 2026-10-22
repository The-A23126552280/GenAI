# app.py
import streamlit as st
from engine import diagnose, RULES

st.set_page_config(page_title="AI Medical Assistant", page_icon="🩺", layout="centered")

# Extract all unique symptoms from the rules
ALL_SYMPTOMS = sorted(list({s for rule in RULES for s in rule["symptoms"]}))

# Memory Initialization
if "patient_history" not in st.session_state:
    st.session_state.patient_history = []

st.title("🩺 AI Rule-Based Symptom Checker")

selected_symptoms = st.multiselect("Select symptoms:", options=ALL_SYMPTOMS)

col1, col2 = st.columns([1, 1])

with col1:
    if st.button("Run Diagnostics", type="primary"):
        if not selected_symptoms:
            st.warning("Select at least one symptom.")
        else:
            results = diagnose(set(selected_symptoms))
            st.session_state.patient_history.append({
                "symptoms": selected_symptoms,
                "results": results
            })
            st.rerun()

with col2:
    if st.button("Reset Memory"):
        st.session_state.patient_history = []
        st.rerun()

st.divider()

# Display Results from Memory
if st.session_state.patient_history:
    latest = st.session_state.patient_history[-1]
    st.subheader("Analysis Output")

    if not latest["results"]:
        st.info("No matching condition found.")
    else:
        for item in latest["results"]:
            if item["urgency"] == "CRITICAL":
                st.error(f"**{item['disease']}** (Match: {item['confidence']}%)")
            else:
                st.success(f"**{item['disease']}** (Match: {item['confidence']}%)")
            st.write(f"**Advice:** {item['advice']}")

    # History Expander
    with st.expander(f"Session History ({len(st.session_state.patient_history)} queries)"):
        for i, entry in enumerate(reversed(st.session_state.patient_history)):
            st.write(f"**Query {len(st.session_state.patient_history) - i}:** {', '.join(entry['symptoms'])}")