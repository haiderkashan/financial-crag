from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.app.agent.nodes.generate import generate_node
from backend.app.agent.nodes.grade import grade_documents_node
from backend.app.agent.nodes.math_repl import (
    math_repl_node,
    route_after_tool_decision,
)
from backend.app.agent.nodes.query_transform import query_transform_node
from backend.app.agent.nodes.retrieve import retrieve_node
from backend.app.agent.nodes.tool_decision import tool_decision_node
from backend.app.agent.nodes.web_search import (
    route_after_grading,
    web_search_node,
)
from backend.app.agent.state import AgentState


def build_crag_graph() -> CompiledStateGraph:
    """Construct and compile the Corrective RAG (CRAG) state machine.

    Architecture:
    1. retrieve: Supabase pgvector cosine search using 384d BGE embedding.
    2. grade_documents: Concurrent LLM relevance grading.
    3. Conditional Edge: If 0 chunks relevant -> query_transform -> web_search. Else -> tool_decision.
    4. tool_decision: LLM routing decision for deterministic arithmetic.
    5. Conditional Edge: If math needed -> math_repl. Else -> generate.
    6. generate: Multi-source grounded synthesis.
    """
    workflow = StateGraph(AgentState)

    # ── Register Nodes ─────────────────────────────────────
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("grade_documents", grade_documents_node)
    workflow.add_node("query_transform", query_transform_node)
    workflow.add_node("web_search", web_search_node)
    workflow.add_node("tool_decision", tool_decision_node)
    workflow.add_node("math_repl", math_repl_node)
    workflow.add_node("generate", generate_node)

    # ── Wire Sequential & Conditional Edges ────────────────
    workflow.add_edge(START, "retrieve")
    workflow.add_edge("retrieve", "grade_documents")

    # Post-Grading: Route to web search fallback or direct tool decision
    workflow.add_conditional_edges(
        "grade_documents",
        route_after_grading,
        {
            "query_transform": "query_transform",
            "tool_decision": "tool_decision",
        },
    )

    workflow.add_edge("query_transform", "web_search")
    workflow.add_edge("web_search", "tool_decision")

    # Post-Tool-Decision: Route to math REPL sandbox or direct generation
    workflow.add_conditional_edges(
        "tool_decision",
        route_after_tool_decision,
        {
            "math_repl": "math_repl",
            "generate": "generate",
        },
    )

    workflow.add_edge("math_repl", "generate")
    workflow.add_edge("generate", END)

    return workflow.compile()


# Export compiled graph instance
crag_agent = build_crag_graph()
