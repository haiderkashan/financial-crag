import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastapi.testclient import TestClient

from backend.app.agent.graph import build_crag_graph, crag_agent
from backend.app.agent.nodes.grade import GradeChunk
from backend.app.agent.nodes.tool_decision import ToolDecision
from backend.app.agent.state import AgentState
from backend.app.api.deps import get_current_user
from backend.app.main import app
from backend.app.models.chunk import ChunkSearchResult
from backend.app.models.user import UserInDB


def _create_mock_chunk(content: str = "Total net sales were $383,285M.") -> ChunkSearchResult:
    return ChunkSearchResult(
        id=uuid.uuid4(),
        filing_id=uuid.uuid4(),
        ticker="AAPL",
        company_name="Apple Inc.",
        fiscal_year=2023,
        chunk_index=0,
        section_title="Item 7. MD&A",
        content=content,
        metadata={"has_table": False},
        similarity=0.88,
    )


def _base_state(question: str = "What was Apple's total revenue in 2023?") -> AgentState:
    return {
        "question": question,
        "ticker": "AAPL",
        "fiscal_year": 2023,
        "documents": [],
        "filtered_documents": [],
        "web_search_needed": False,
        "grade_explanations": [],
        "web_results": None,
        "search_query": None,
        "math_needed": False,
        "math_code": None,
        "math_result": None,
        "generation": None,
        "steps": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# GRAPH COMPILATION & TOPOLOGY
# ─────────────────────────────────────────────────────────────────────────────


def test_crag_graph_structure():
    """Verify that build_crag_graph wires all 7 nodes and compiles successfully."""
    graph = build_crag_graph()
    expected_nodes = {
        "retrieve",
        "grade_documents",
        "query_transform",
        "web_search",
        "tool_decision",
        "math_repl",
        "generate",
    }
    assert expected_nodes.issubset(set(graph.nodes.keys()))


# ─────────────────────────────────────────────────────────────────────────────
# PATH 1: RELEVANT CHUNKS + NO MATH (DIRECT QA)
# Flow: retrieve -> grade -> tool_decision -> generate
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_path_1_relevant_no_math():
    """Verify Path 1: Relevant SEC chunks + No math required -> Direct generation."""
    mock_chunk = _create_mock_chunk()

    # Mock grade decision
    grade_decision = GradeChunk(binary_score="yes", explanation="Chunk contains revenue.")
    # Mock tool decision
    tool_decision = ToolDecision(needs_math=False, reasoning="Direct qualitative lookup.")

    mock_llm = MagicMock()
    # Mock structured output for grade and tool_decision
    mock_llm.with_structured_output.side_effect = [
        MagicMock(ainvoke=AsyncMock(return_value=grade_decision)),  # grade
        MagicMock(ainvoke=AsyncMock(return_value=tool_decision)),   # tool_decision
    ]
    # Mock generate synthesis
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(content="Apple 2023 revenue was $383,285 million.")
    )

    with (
        patch("backend.app.agent.nodes.retrieve.embedder.embed_query", return_value=[0.01] * 384),
        patch("backend.app.agent.nodes.retrieve.chunk_repo.search_similar_chunks", return_value=[mock_chunk]),
        patch("backend.app.agent.nodes.grade.get_llm", return_value=mock_llm),
        patch("backend.app.agent.nodes.tool_decision.get_llm", return_value=mock_llm),
        patch("backend.app.agent.nodes.generate.get_llm", return_value=mock_llm),
    ):
        result = await crag_agent.ainvoke(_base_state())

        # Assert correct terminal outputs
        assert result["generation"] == "Apple 2023 revenue was $383,285 million."
        assert len(result["filtered_documents"]) == 1
        assert result["web_search_needed"] is False
        assert result["web_results"] is None
        assert result["math_needed"] is False
        assert result["math_result"] is None

        # Assert exact node traversal in steps log
        step_text = " -> ".join(result["steps"])
        assert "[Retrieve]" in step_text
        assert "[Grade]" in step_text
        assert "[Tool Decision]" in step_text
        assert "[Generate]" in step_text
        assert "[Query Transform]" not in step_text
        assert "[Web Search]" not in step_text
        assert "[Math REPL]" not in step_text


# ─────────────────────────────────────────────────────────────────────────────
# PATH 2: RELEVANT CHUNKS + MATH CALCULATION
# Flow: retrieve -> grade -> tool_decision -> math_repl -> generate
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_path_2_relevant_with_math():
    """Verify Path 2: Relevant SEC chunks + Math required -> REPL execution -> generation."""
    mock_chunk = _create_mock_chunk(content="2023 sales: $383,285M. 2022 sales: $394,328M.")

    grade_decision = GradeChunk(binary_score="yes", explanation="Contains both periods.")
    tool_decision = ToolDecision(needs_math=True, reasoning="Requires calculating YoY growth percentage.")

    mock_llm = MagicMock()
    mock_llm.with_structured_output.side_effect = [
        MagicMock(ainvoke=AsyncMock(return_value=grade_decision)),  # grade
        MagicMock(ainvoke=AsyncMock(return_value=tool_decision)),   # tool_decision
    ]

    math_code_response = MagicMock(
        content='```python\nchange = 383285 - 394328\ngrowth = (change / 394328) * 100\nprint(f"Growth: {growth:.2f}%")\n```'
    )
    generate_response = MagicMock(
        content="Apple's revenue declined by 2.80% year-over-year in FY 2023."
    )

    mock_llm.ainvoke = AsyncMock(side_effect=[math_code_response, generate_response])

    with (
        patch("backend.app.agent.nodes.retrieve.embedder.embed_query", return_value=[0.01] * 384),
        patch("backend.app.agent.nodes.retrieve.chunk_repo.search_similar_chunks", return_value=[mock_chunk]),
        patch("backend.app.agent.nodes.grade.get_llm", return_value=mock_llm),
        patch("backend.app.agent.nodes.tool_decision.get_llm", return_value=mock_llm),
        patch("backend.app.agent.nodes.math_repl.get_llm", return_value=mock_llm),
        patch("backend.app.agent.nodes.generate.get_llm", return_value=mock_llm),
    ):
        result = await crag_agent.ainvoke(_base_state("What was the YoY revenue growth rate?"))

        assert "Growth: -2.80%" in result["math_result"]
        assert result["generation"] == "Apple's revenue declined by 2.80% year-over-year in FY 2023."
        assert result["math_needed"] is True
        assert result["web_results"] is None

        step_text = " -> ".join(result["steps"])
        assert "[Retrieve]" in step_text
        assert "[Grade]" in step_text
        assert "[Tool Decision]" in step_text
        assert "[Math REPL]" in step_text
        assert "[Generate]" in step_text
        assert "[Web Search]" not in step_text


# ─────────────────────────────────────────────────────────────────────────────
# PATH 3: IRRELEVANT CHUNKS + WEB SEARCH + NO MATH
# Flow: retrieve -> grade -> query_transform -> web_search -> tool_decision -> generate
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_path_3_irrelevant_web_search_no_math():
    """Verify Path 3: Irrelevant chunks -> Query Transform -> Web Search -> Direct Generation."""
    mock_chunk = _create_mock_chunk(content="Irrelevant legal disclaimers and definitions.")

    # Grade says NO
    grade_decision = GradeChunk(binary_score="no", explanation="Boilerplate disclaimer.")
    tool_decision = ToolDecision(needs_math=False, reasoning="Qualitative query.")

    mock_llm = MagicMock()
    mock_llm.with_structured_output.side_effect = [
        MagicMock(ainvoke=AsyncMock(return_value=grade_decision)),  # grade
        MagicMock(ainvoke=AsyncMock(return_value=tool_decision)),   # tool_decision
    ]

    transform_response = MagicMock(content='"Apple AAPL FY 2023 revenue SEC"')
    generate_response = MagicMock(content="According to public reports, Apple revenue was $383B.")
    mock_llm.ainvoke = AsyncMock(side_effect=[transform_response, generate_response])

    mock_web_content = "**Web Summary:** Apple reported $383.3 billion revenue in 2023."

    with (
        patch("backend.app.agent.nodes.retrieve.embedder.embed_query", return_value=[0.01] * 384),
        patch("backend.app.agent.nodes.retrieve.chunk_repo.search_similar_chunks", return_value=[mock_chunk]),
        patch("backend.app.agent.nodes.grade.get_llm", return_value=mock_llm),
        patch("backend.app.agent.nodes.query_transform.get_llm", return_value=mock_llm),
        patch("backend.app.agent.nodes.web_search.tavily_tool.search", return_value=mock_web_content),
        patch("backend.app.agent.nodes.tool_decision.get_llm", return_value=mock_llm),
        patch("backend.app.agent.nodes.generate.get_llm", return_value=mock_llm),
    ):
        result = await crag_agent.ainvoke(_base_state())

        assert result["web_search_needed"] is True
        assert result["search_query"] == "Apple AAPL FY 2023 revenue SEC"
        assert result["web_results"] == mock_web_content
        assert result["math_needed"] is False
        assert result["math_result"] is None

        step_text = " -> ".join(result["steps"])
        assert "[Retrieve]" in step_text
        assert "[Grade]" in step_text
        assert "[Query Transform]" in step_text
        assert "[Web Search]" in step_text
        assert "[Tool Decision]" in step_text
        assert "[Generate]" in step_text
        assert "[Math REPL]" not in step_text


# ─────────────────────────────────────────────────────────────────────────────
# PATH 4: IRRELEVANT CHUNKS + WEB SEARCH + MATH CALCULATION
# Flow: retrieve -> grade -> query_transform -> web_search -> tool_decision -> math_repl -> generate
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_path_4_irrelevant_web_search_with_math():
    """Verify Path 4: Irrelevant chunks -> Web Search -> Math REPL -> Generation."""
    mock_chunk = _create_mock_chunk(content="Unrelated text.")

    grade_decision = GradeChunk(binary_score="no", explanation="No metrics.")
    tool_decision = ToolDecision(needs_math=True, reasoning="Requires calculating percentage from web data.")

    mock_llm = MagicMock()
    mock_llm.with_structured_output.side_effect = [
        MagicMock(ainvoke=AsyncMock(return_value=grade_decision)),  # grade
        MagicMock(ainvoke=AsyncMock(return_value=tool_decision)),   # tool_decision
    ]

    transform_response = MagicMock(content='"Apple FY 2023 2022 revenue"')
    math_code_response = MagicMock(content='```python\nprint(f"Computed: {383285 - 394328}")\n```')
    generate_response = MagicMock(content="Apple revenue dropped by $11,043M according to web findings.")

    mock_llm.ainvoke = AsyncMock(
        side_effect=[transform_response, math_code_response, generate_response]
    )

    mock_web_content = "**Web Summary:** Revenue: 2023: $383,285M, 2022: $394,328M."

    with (
        patch("backend.app.agent.nodes.retrieve.embedder.embed_query", return_value=[0.01] * 384),
        patch("backend.app.agent.nodes.retrieve.chunk_repo.search_similar_chunks", return_value=[mock_chunk]),
        patch("backend.app.agent.nodes.grade.get_llm", return_value=mock_llm),
        patch("backend.app.agent.nodes.query_transform.get_llm", return_value=mock_llm),
        patch("backend.app.agent.nodes.web_search.tavily_tool.search", return_value=mock_web_content),
        patch("backend.app.agent.nodes.tool_decision.get_llm", return_value=mock_llm),
        patch("backend.app.agent.nodes.math_repl.get_llm", return_value=mock_llm),
        patch("backend.app.agent.nodes.generate.get_llm", return_value=mock_llm),
    ):
        result = await crag_agent.ainvoke(_base_state("Calculate revenue decrease from web data"))

        assert result["web_search_needed"] is True
        assert result["web_results"] == mock_web_content
        assert result["math_needed"] is True
        assert "Computed: -11043" in result["math_result"]
        assert "Apple revenue dropped" in result["generation"]

        # All 7 nodes traversed in exact sequence
        step_text = " -> ".join(result["steps"])
        assert "[Retrieve]" in step_text
        assert "[Grade]" in step_text
        assert "[Query Transform]" in step_text
        assert "[Web Search]" in step_text
        assert "[Tool Decision]" in step_text
        assert "[Math REPL]" in step_text
        assert "[Generate]" in step_text


# ─────────────────────────────────────────────────────────────────────────────
# API ENDPOINT & SSE STREAMING TESTS
# ─────────────────────────────────────────────────────────────────────────────


def test_agent_query_endpoint_unauthorized():
    """Verify POST /api/v1/agent/query rejects unauthenticated requests with 401."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/agent/query",
        json={"question": "What was Apple's revenue in 2023?"},
    )
    assert response.status_code == 401
    assert "Authentication credentials were not provided" in response.text


def test_agent_query_endpoint_streaming():
    """Verify POST /api/v1/agent/query streams SSE step events, generation, and done."""
    from datetime import datetime

    mock_user = UserInDB(
        id=uuid.uuid4(),
        email="analyst@example.com",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user

    async def mock_astream(initial_state, stream_mode="updates"):
        yield {"retrieve": {"steps": ["[Retrieve] Found 1 chunks from Supabase."]}}
        yield {"generate": {"generation": "Apple 2023 revenue was $383,285M."}}

    with patch("backend.app.api.v1.agent.crag_agent.astream", side_effect=mock_astream):
        client = TestClient(app)
        response = client.post(
            "/api/v1/agent/query",
            json={"question": "What was Apple's total revenue in 2023?", "ticker": "AAPL", "fiscal_year": 2023},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        body = response.text
        # Assert SSE data lines format
        assert "data: " in body
        assert '"type":"step"' in body
        assert "[Retrieve] Found 1 chunks" in body
        assert '"type":"generation"' in body
        assert "Apple 2023 revenue was $383,285M." in body
        assert '"type":"done"' in body

    app.dependency_overrides.clear()
