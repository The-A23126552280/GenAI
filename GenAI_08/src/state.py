from typing import TypedDict
from pydantic import BaseModel, Field


class PaperState(TypedDict):
    topic: str
    research_data: str
    draft: str
    feedback: str
    revision_count: int
    is_approved: bool


class EditorFeedback(BaseModel):
    score: int = Field(ge=1, le=10, description="Quality score from 1-10")
    feedback: str = Field(description="Detailed feedback for improvement")
