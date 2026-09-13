import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.agent.nodes.grade import (
    GradeChunk,
    _grade_single_chunk,
    grade_documents_node,
)
from backend.app.agent.nodes.retrieve import retrieve_node
from backend.app.agent.state import AgentState
from backend.app.models.chunk import ChunkSearchResult


def _create_mock_chunk(
    chunk_index: int,
    content: str,
    section: str = "Item 7",
    similarity: float = 0.85,
) -> ChunkSearchResult:
    """Helper to create a realistic ChunkSearchResult."""
    return ChunkSearchResult(
        id=uuid.uuid4(),
        filing_id=uuid.uuid4(),
        ticker="AAPL",
        company_name="Apple Inc.",
        fiscal_year=2023,
        chunk_index=chunk_index,
        section_title=section,
        content=content,
        metadata={"has_table": False},
        similarity=similarity,
    )


# ─────────────────────────────────────────────────────────────────────────────
# RETRIEVE NODE TESTS
# ─────────────────────────────────────────────────────────────────────────────


def test_retrieve_node_success():
    """Verify retrieve_node embeds query, searches chunk_repo, and updates state."""
    mock_chunks = [
        _create_mock_chunk(0, "Apple revenue was $383B.", similarity=0.88),
        _create_mock_chunk(1, "Operating expenses were $54B.", similarity=0.79),
    ]

    mock_embedding = [0.05] * 384

    with (
        patch(
            "backend.app.agent.nodes.retrieve.embedder.embed_query",
            return_value=mock_embedding,
        ) as mock_embed,
        patch(
            "backend.app.agent.nodes.retrieve.chunk_repo.search_similar_chunks",
            return_value=mock_chunks,
        ) as mock_search,
    ):
        initial_state: AgentState = {
            "question": "What was Apple revenue?",
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
            "steps": ["[Start] Initiated query."],
        }

        result = retrieve_node(initial_state)

        # Verify embedding and search calls
        mock_embed.assert_called_once_with("What was Apple revenue?")
        assert mock_search.call_count == 1
        query_arg = mock_search.call_args[0][0]
        assert query_arg.filter_ticker == "AAPL"
        assert query_arg.filter_fiscal_year == 2023
        assert len(query_arg.query_embedding) == 384

        # Verify output state updates
        assert len(result["documents"]) == 2
        assert result["documents"][0]["content"] == "Apple revenue was $383B."
        assert len(result["steps"]) == 2
        assert "[Retrieve] Found 2 chunks from Supabase" in result["steps"][1]


def test_retrieve_node_empty_results():
    """Verify retrieve_node gracefully handles empty vector search results."""
    with (
        patch(
            "backend.app.agent.nodes.retrieve.embedder.embed_query",
            return_value=[0.01] * 384,
        ),
        patch(
            "backend.app.agent.nodes.retrieve.chunk_repo.search_similar_chunks",
            return_value=[],
        ),
    ):
        state: AgentState = {
            "question": "Nonexistent topic",
            "ticker": None,
            "fiscal_year": None,
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

        result = retrieve_node(state)
        assert result["documents"] == []
        assert "[Retrieve] Found 0 chunks" in result["steps"][0]


# ─────────────────────────────────────────────────────────────────────────────
# GRADE NODE TESTS
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_grade_documents_node_all_relevant():
    """Verify grade_documents_node retains all chunks and sets web_search_needed=False."""
    docs = [
        {"chunk_index": 0, "content": "Net revenue $383B", "ticker": "AAPL", "fiscal_year": 2023},
        {"chunk_index": 1, "content": "Gross margin 44%", "ticker": "AAPL", "fiscal_year": 2023},
    ]

    mock_grader = MagicMock()
    mock_grader.ainvoke = AsyncMock(
        side_effect=[
            GradeChunk(binary_score="yes", explanation="Contains net revenue."),
            GradeChunk(binary_score="yes", explanation="Contains gross margin."),
        ]
    )

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_grader

    with patch("backend.app.agent.nodes.grade.get_llm", return_value=mock_llm):
        state: AgentState = {
            "question": "What is revenue and margin?",
            "ticker": "AAPL",
            "fiscal_year": 2023,
            "documents": docs,
            "filtered_documents": [],
            "web_search_needed": False,
            "grade_explanations": [],
            "web_results": None,
            "search_query": None,
            "math_needed": False,
            "math_code": None,
            "math_result": None,
            "generation": None,
            "steps": ["[Retrieve] Done"],
        }

        result = await grade_documents_node(state)

        assert len(result["filtered_documents"]) == 2
        assert result["web_search_needed"] is False
        assert len(result["grade_explanations"]) == 2
        assert "not needed" in result["steps"][-1]


@pytest.mark.asyncio
async def test_grade_documents_node_partial_relevant_no_web_search():
    """CRITICAL FIX: web_search_needed must remain False if AT LEAST ONE chunk is relevant."""
    docs = [
        {"chunk_index": 0, "content": "Net revenue $383B", "ticker": "AAPL", "fiscal_year": 2023},
        {"chunk_index": 1, "content": "Legal boilerplate text", "ticker": "AAPL", "fiscal_year": 2023},
    ]

    mock_grader = MagicMock()
    mock_grader.ainvoke = AsyncMock(
        side_effect=[
            GradeChunk(binary_score="yes", explanation="Revenue numbers present."),
            GradeChunk(binary_score="no", explanation="Boilerplate disclaimer."),
        ]
    )

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_grader

    with patch("backend.app.agent.nodes.grade.get_llm", return_value=mock_llm):
        state: AgentState = {
            "question": "What is revenue?",
            "ticker": "AAPL",
            "fiscal_year": 2023,
            "documents": docs,
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

        result = await grade_documents_node(state)

        # Only 1 chunk passed relevance
        assert len(result["filtered_documents"]) == 1
        assert result["filtered_documents"][0]["chunk_index"] == 0
        # CRITICAL: web_search_needed is FALSE because we have 1 relevant chunk!
        assert result["web_search_needed"] is False
        assert len(result["grade_explanations"]) == 2
        assert "1 relevant, 1 discarded" in result["steps"][-1]
        assert "not needed" in result["steps"][-1]


@pytest.mark.asyncio
async def test_grade_documents_node_all_irrelevant_triggers_web_search():
    """CRITICAL FIX: web_search_needed must become True ONLY when 0 chunks are relevant."""
    docs = [
        {"chunk_index": 0, "content": "Legal disclaimer", "ticker": "AAPL", "fiscal_year": 2023},
        {"chunk_index": 1, "content": "Signatures of officers", "ticker": "AAPL", "fiscal_year": 2023},
    ]

    mock_grader = MagicMock()
    mock_grader.ainvoke = AsyncMock(
        side_effect=[
            GradeChunk(binary_score="no", explanation="Not relevant to revenue."),
            GradeChunk(binary_score="no", explanation="Signatures are irrelevant."),
        ]
    )

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_grader

    with patch("backend.app.agent.nodes.grade.get_llm", return_value=mock_llm):
        state: AgentState = {
            "question": "What is revenue?",
            "ticker": "AAPL",
            "fiscal_year": 2023,
            "documents": docs,
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

        result = await grade_documents_node(state)

        # 0 chunks passed
        assert len(result["filtered_documents"]) == 0
        # CRITICAL: web_search_needed is TRUE because zero chunks are relevant
        assert result["web_search_needed"] is True
        assert "triggered (0 relevant chunks)" in result["steps"][-1]


@pytest.mark.asyncio
async def test_grade_documents_node_empty_documents():
    """Verify grade_documents_node handles empty documents list and triggers web search."""
    state: AgentState = {
        "question": "What is revenue?",
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

    result = await grade_documents_node(state)
    assert result["filtered_documents"] == []
    assert result["web_search_needed"] is True
    assert "[Grade] No chunks available to grade. Web search triggered." in result["steps"][0]


@pytest.mark.asyncio
async def test_grade_single_chunk_fallback_on_exception():
    """Verify _grade_single_chunk falls back to permissive 'yes' on LLM exception."""
    mock_grader = MagicMock()
    mock_grader.ainvoke = AsyncMock(side_effect=RuntimeError("Groq rate limit exceeded"))

    doc = {"content": "Sample content", "chunk_index": 5}
    idx, returned_doc, grade = await _grade_single_chunk(
        mock_grader, "Test question", doc, 5
    )

    assert idx == 5
    assert grade.binary_score == "yes"
    assert "fallback" in grade.explanation.lower()
