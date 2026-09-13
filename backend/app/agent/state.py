from typing import Optional, TypedDict


class AgentState(TypedDict):
    """State contract for the Corrective RAG (CRAG) agent graph.

    Represents the complete lifecycle of an analyst query through vector
    retrieval, relevance grading, web fallback search, arithmetic execution,
    and final synthesis.
    """

    # ── Input ──────────────────────────────────────────────
    question: str
    ticker: Optional[str]
    fiscal_year: Optional[int]

    # ── Retrieval ──────────────────────────────────────────
    documents: list[dict]
    filtered_documents: list[dict]

    # ── Grading ────────────────────────────────────────────
    web_search_needed: bool
    grade_explanations: list[dict]

    # ── Web Search ─────────────────────────────────────────
    web_results: Optional[str]
    search_query: Optional[str]

    # ── Math Tool ──────────────────────────────────────────
    math_needed: bool
    math_code: Optional[str]
    math_result: Optional[str]

    # ── Generation ─────────────────────────────────────────
    generation: Optional[str]

    # ── Observability (Thought Inspection Panel) ───────────
    steps: list[str]
