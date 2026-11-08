import streamlit as st
from dotenv import load_dotenv

from src.graph import build_graph
from src.state import PaperState

# Load .env so GROQ_API_KEY / TAVILY_API_KEY / etc. are available
load_dotenv()

st.set_page_config(page_title="Multi-Agent Research Generator", layout="wide")
st.title("📄 Agentic Research Paper Generator")

topic = st.text_input(
    "Enter your research topic:",
    "The impact of quantum-resistant cryptography on legacy banking systems",
)

if st.button("Generate Paper", type="primary"):
    if not topic.strip():
        st.error("Please enter a research topic")
    else:
        initial_state: PaperState = {
            "topic": topic.strip(),
            "research_data": "",
            "draft": "",
            "feedback": "",
            "revision_count": 0,
            "is_approved": False,
        }
        graph = build_graph()

        with st.spinner("Agents are collaborating..."):
            status_placeholder = st.empty()
            # Single invoke — avoids double execution cost/rate-limit hits
            final_state = graph.invoke(initial_state)

            # Simple status based on final state
            if final_state.get("is_approved"):
                status_placeholder.success("✅ Editor Agent approved the draft")
            else:
                status_placeholder.warning(
                    f"🧐 Reached max revisions. Last feedback: "
                    f"{final_state.get('feedback', '')[:150]}..."
                )

        st.success(
            f"✅ Paper finalized after {final_state['revision_count']} revision(s)!"
        )
        st.markdown("### Final Draft")
        st.markdown(final_state["draft"])

        with st.expander("Research data used"):
            st.markdown(final_state.get("research_data", "_none_"))
        with st.expander("Last editor feedback"):
            st.write(final_state.get("feedback", "_none_"))
