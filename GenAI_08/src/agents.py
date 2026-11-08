import os
import json
import re
import time

from src.state import PaperState, EditorFeedback
from src.llm import get_llm_response
from src.tools import search_research


def research_agent(state: PaperState) -> dict:
    """Gather research data (Tavily first, LLM fallback)."""
    time.sleep(3)
    research_data = search_research(state["topic"])
    if "placeholder" in research_data.lower() or "error" in research_data.lower():
        prompt = (
            f"You are a research assistant. Provide comprehensive research on: "
            f"{state['topic']}. Include key facts, context, and citations."
        )
        research_data = get_llm_response(
            [{"role": "user", "content": prompt}],
            max_tokens=800,
        )
    return {"research_data": research_data}


def writer_agent(state: PaperState) -> dict:
    """Write or revise the academic draft based on research + editor feedback."""
    time.sleep(3)
    prompt = f"""You are an academic writer. Write a research paper.
TOPIC: {state['topic']}
RESEARCH DATA: {state['research_data']}
EDITOR FEEDBACK: {state.get('feedback', 'No previous feedback. Write the first draft.')}
INSTRUCTIONS: Write a well-structured academic paper (400-600 words). Address all feedback."""
    draft = get_llm_response(
        [{"role": "user", "content": prompt}],
        max_tokens=500,
    )
    return {
        "draft": draft,
        "revision_count": state.get("revision_count", 0) + 1,
    }


def editor_agent(state: PaperState) -> dict:
    """Peer-review the draft and return structured feedback + approval flag."""
    time.sleep(3)
    threshold = int(os.getenv("REVIEW_THRESHOLD", "8"))
    prompt = f"""You are a strict academic peer reviewer. Review this draft on rigor, structure, and clarity.
TOPIC: {state['topic']}
DRAFT: {state['draft']}
RESPOND ONLY IN THIS EXACT JSON FORMAT: {{"score": <integer 1-10>, "feedback": "<detailed feedback string>"}}"""
    response = get_llm_response(
        [{"role": "user", "content": prompt}],
        max_tokens=200,
    )

    try:
        text = response.strip()
        # Tolerate markdown fences
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if fence:
            text = fence.group(1)
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise ValueError("No JSON object found in model response")
        feedback_data = json.loads(match.group(0))
        editor_feedback = EditorFeedback(**feedback_data)
        return {
            "feedback": editor_feedback.feedback,
            "is_approved": editor_feedback.score >= threshold,
        }
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        return {
            "feedback": f"Failed to parse structured feedback ({e}). Raw: {response[:200]}",
            "is_approved": False,
        }
