from typing import Any

from backend.app.agent.state import AgentState
from backend.app.tools.tavily_search import tavily_tool


def web_search_node(state: AgentState) -> dict[str, Any]:
    """Execute Tavily web search using the transformed query.

    Retrieves public disclosures, investor relations updates, or financial
    press releases to augment internal context when SEC retrieval yields no matches.
    """
    search_query = state.get("search_query") or state.get("question") or ""
    results = tavily_tool.search(search_query)

    existing_steps = list(state.get("steps") or [])
    step_log = f"[Web Search] Executed web search for: '{search_query}'"

    return {
        "web_results": results,
        "steps": existing_steps + [step_log],
    }


def route_after_grading(state: AgentState) -> str:
    """Conditional edge router following document relevance grading.

    Routes to 'query_transform' if web_search_needed is True (0 relevant chunks).
    Otherwise proceeds directly to 'tool_decision'.
    """
    if state.get("web_search_needed", False):
        return "query_transform"
    return "tool_decision"
