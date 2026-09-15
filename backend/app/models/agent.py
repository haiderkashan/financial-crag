from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentQueryRequest(BaseModel):
    """Payload for submitting a financial query to the CRAG agent."""

    model_config = ConfigDict(from_attributes=True)

    question: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Analyst question or due-diligence inquiry",
        examples=["What was Apple's total revenue in 2023 and how did it change from 2022?"],
    )
    ticker: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Optional stock ticker symbol for targeted retrieval (e.g., AAPL)",
        examples=["AAPL"],
    )
    fiscal_year: Optional[int] = Field(
        default=None,
        ge=1900,
        le=2100,
        description="Optional fiscal year filter for targeted retrieval",
        examples=[2023],
    )


class AgentStepEvent(BaseModel):
    """Server-Sent Event schema for agent step updates and response streaming."""

    model_config = ConfigDict(from_attributes=True)

    type: Literal["step", "generation", "done", "error"] = Field(
        ...,
        description="SSE event type",
    )
    node: Optional[str] = Field(
        default=None,
        description="Originating graph node name (e.g., retrieve, grade_documents)",
    )
    message: Optional[str] = Field(
        default=None,
        description="Human-readable status string for the Thought Inspection Panel",
    )
    content: Optional[str] = Field(
        default=None,
        description="Markdown content chunk for final answer synthesis",
    )
