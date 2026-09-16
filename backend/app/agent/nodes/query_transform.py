from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from backend.app.agent.llm import get_llm
from backend.app.agent.state import AgentState

QUERY_TRANSFORM_SYSTEM_PROMPT = """You are a financial research query optimizer. Your task is to reformulate an analyst's question into an optimized web search query that will find authoritative financial data.

RULES:
- Include the company name and stock ticker (if known).
- Include the specific fiscal year or time period.
- Include specific financial metrics mentioned in the question.
- Target authoritative sources: SEC.gov, company investor relations, Reuters, Bloomberg.
- Keep the query concise (under 20 words).
- Do NOT add explanatory text — return ONLY the search query string."""


async def query_transform_node(state: AgentState) -> dict[str, Any]:
    """Reformulate an analyst's question into an optimized web search query.

    Uses an LLM to inject ticker, fiscal year, and target metrics into a concise,
    authoritative search string when internal SEC document retrieval yields zero relevant chunks.
    """
    question = (state.get("question") or "").strip()
    ticker = state.get("ticker") or "N/A"
    fiscal_year = state.get("fiscal_year") or "N/A"

    user_content = (
        f"Original Question: {question}\n"
        f"Company Ticker: {ticker}\n"
        f"Fiscal Year: {fiscal_year}"
    )

    llm = get_llm(temperature=0.0, max_tokens=100)

    try:
        messages = [
            SystemMessage(content=QUERY_TRANSFORM_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]
        response = await llm.ainvoke(messages)
        search_query = str(response.content).strip().strip('"').strip("'")
    except Exception as exc:
        # Graceful fallback to basic concatenation on LLM error
        clean_ticker = ticker if ticker != "N/A" else ""
        clean_year = str(fiscal_year) if fiscal_year != "N/A" else ""
        search_query = f"{clean_ticker} {clean_year} {question}".strip()

    existing_steps = list(state.get("steps") or [])
    step_log = f"[Query Transform] Reformulated: '{search_query}'"

    return {
        "search_query": search_query,
        "steps": existing_steps + [step_log],
    }
