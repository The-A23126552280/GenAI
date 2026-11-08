from typing import Literal
import os

from langgraph.graph import StateGraph, END

from src.state import PaperState
from src.agents import research_agent, writer_agent, editor_agent


def route_after_edit(state: PaperState) -> Literal["write", "__end__"]:
    """Decide whether to revise again or finish."""
    max_revisions = int(os.getenv("MAX_REVISIONS", "3"))
    if state.get("is_approved") or state.get("revision_count", 0) >= max_revisions:
        return "__end__"
    return "write"


def build_graph():
    """Compile the multi-agent research → write → edit loop graph."""
    workflow = StateGraph(PaperState)
    workflow.add_node("research", research_agent)
    workflow.add_node("write", writer_agent)
    workflow.add_node("edit", editor_agent)
    workflow.set_entry_point("research")
    workflow.add_edge("research", "write")
    workflow.add_edge("write", "edit")
    workflow.add_conditional_edges(
        "edit",
        route_after_edit,
        {"write": "write", "__end__": END},
    )
    return workflow.compile()
