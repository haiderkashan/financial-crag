from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from backend.app.agent.llm import get_llm
from backend.app.agent.state import AgentState

TOOL_DECISION_SYSTEM_PROMPT = """You are a financial analysis routing engine. Determine whether the analyst's question requires exact arithmetic computation to answer correctly.

REQUIRES MATH (needs_math = true):
- Year-over-year or period-over-period growth rates (e.g., "How much did revenue grow?", "YoY change in net income")
- Financial ratios (e.g., debt-to-equity, current ratio, operating margin, P/E, EPS change)
- Percentage differences or percentage share calculations
- Compound calculations, aggregations, or multi-step arithmetic

DOES NOT REQUIRE MATH (needs_math = false):
- Qualitative questions (e.g., "What are the primary risk factors?", "Describe the company's business model")
- Direct single data lookups (e.g., "What was total revenue in 2023?")
- Descriptive questions about segments, products, or legal proceedings
- Questions answerable directly by reading a single existing number or table cell

Provide your decision as a boolean (needs_math) and a concise one-sentence reasoning."""


class ToolDecision(BaseModel):
    """Routing decision determining whether exact arithmetic computation is required."""

    needs_math: bool = Field(
        description="True if answering requires calculating percentages, ratios, growth rates, margins, or comparing numerical values across periods."
    )
    reasoning: str = Field(
        description="One-sentence explanation of why math computation is or is not needed."
    )


async def tool_decision_node(state: AgentState) -> dict[str, Any]:
    """Evaluate whether the analyst's question requires the sandboxed Python REPL.

    Uses an LLM with structured output (ToolDecision) to route queries requiring
    deterministic math (margins, growth rates, ratios) to the execution engine.
    """
    question = (state.get("question") or "").strip()

    # Build context preview (first 500 characters)
    context_chunks = state.get("filtered_documents") or state.get("documents") or []
    if context_chunks:
        preview = " ".join([c.get("content", "") for c in context_chunks[:2]])[:500]
    elif state.get("web_results"):
        preview = (state.get("web_results") or "")[:500]
    else:
        preview = "No context available."

    user_content = (
        f"User Question: {question}\n\n"
        f"Available Context (first 500 chars):\n{preview}"
    )

    llm = get_llm(temperature=0.0, max_tokens=250)
    decision_maker = llm.with_structured_output(ToolDecision)

    try:
        messages = [
            SystemMessage(content=TOOL_DECISION_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]
        decision: ToolDecision = await decision_maker.ainvoke(messages)
    except Exception as exc:
        decision = ToolDecision(
            needs_math=False,
            reasoning=f"Fallback to false due to evaluation exception: {exc}",
        )

    existing_steps = list(state.get("steps") or [])
    step_log = (
        f"[Tool Decision] Math {'required' if decision.needs_math else 'not required'} — "
        f"{decision.reasoning}"
    )

    return {
        "math_needed": decision.needs_math,
        "steps": existing_steps + [step_log],
    }
