import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.agent.nodes.grade import (
    GradeChunk,
    _grade_single_chunk,
    grade_documents_node,
)
from backend.app.agent.nodes.query_transform import query_transform_node
from backend.app.agent.nodes.retrieve import retrieve_node
from backend.app.agent.nodes.web_search import route_after_grading, web_search_node
from backend.app.agent.state import AgentState
from backend.app.models.chunk import ChunkSearchResult
from backend.app.tools.tavily_search import TavilySearchTool


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


# ─────────────────────────────────────────────────────────────────────────────
# QUERY TRANSFORM NODE TESTS
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_query_transform_node_success():
    """Verify query_transform_node reformulates query and strips quotes."""
    mock_response = MagicMock()
    mock_response.content = '"Apple AAPL FY 2023 total revenue SEC 10-K"'

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("backend.app.agent.nodes.query_transform.get_llm", return_value=mock_llm):
        state: AgentState = {
            "question": "What was Apple's revenue?",
            "ticker": "AAPL",
            "fiscal_year": 2023,
            "documents": [],
            "filtered_documents": [],
            "web_search_needed": True,
            "grade_explanations": [],
            "web_results": None,
            "search_query": None,
            "math_needed": False,
            "math_code": None,
            "math_result": None,
            "generation": None,
            "steps": ["[Grade] Done"],
        }

        result = await query_transform_node(state)

        assert result["search_query"] == "Apple AAPL FY 2023 total revenue SEC 10-K"
        assert len(result["steps"]) == 2
        assert "[Query Transform] Reformulated: 'Apple AAPL FY 2023 total revenue SEC 10-K'" == result["steps"][1]


@pytest.mark.asyncio
async def test_query_transform_node_fallback_on_exception():
    """Verify query_transform_node falls back cleanly on LLM exception."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM service unavailable"))

    with patch("backend.app.agent.nodes.query_transform.get_llm", return_value=mock_llm):
        state: AgentState = {
            "question": "What was revenue?",
            "ticker": "AAPL",
            "fiscal_year": 2023,
            "documents": [],
            "filtered_documents": [],
            "web_search_needed": True,
            "grade_explanations": [],
            "web_results": None,
            "search_query": None,
            "math_needed": False,
            "math_code": None,
            "math_result": None,
            "generation": None,
            "steps": [],
        }

        result = await query_transform_node(state)

        assert "AAPL 2023 What was revenue?" in result["search_query"]
        assert len(result["steps"]) == 1


# ─────────────────────────────────────────────────────────────────────────────
# TAVILY SEARCH TOOL TESTS
# ─────────────────────────────────────────────────────────────────────────────


def test_tavily_search_tool_formatting_with_answer():
    """Verify TavilySearchTool properly formats answer and results into markdown."""
    tool = TavilySearchTool(api_key="tvly-mock-key")

    mock_client = MagicMock()
    mock_client.search.return_value = {
        "answer": "Apple reported $383.29 billion in revenue for FY 2023.",
        "results": [
            {
                "title": "Apple Reports Fourth Quarter Results",
                "url": "https://www.apple.com/newsroom/2023/11/apple-reports-fourth-quarter-results/",
                "content": "Cupertino, California — Apple today announced financial results...",
            },
            {
                "title": "SEC EDGAR Form 10-K Apple Inc.",
                "url": "https://www.sec.gov/edgar/data/320193/aapl-202310k.htm",
                "content": "Total net sales were $383,285 million for the year ended...",
            },
        ],
    }
    tool._client = mock_client

    result = tool.search("AAPL FY 2023 revenue")

    assert "**Web Summary:** Apple reported $383.29 billion in revenue for FY 2023." in result
    assert "**Source:** Apple Reports Fourth Quarter Results (https://www.apple.com" in result
    assert "**Source:** SEC EDGAR Form 10-K Apple Inc." in result
    assert "\n\n---\n\n" in result


def test_tavily_search_tool_formatting_no_answer():
    """Verify TavilySearchTool formats properly when answer is absent."""
    tool = TavilySearchTool(api_key="tvly-mock-key")

    mock_client = MagicMock()
    mock_client.search.return_value = {
        "answer": None,
        "results": [
            {
                "title": "Apple IR",
                "url": "https://investor.apple.com",
                "content": "Investor relations homepage.",
            }
        ],
    }
    tool._client = mock_client

    result = tool.search("AAPL investor relations")

    assert "**Web Summary:**" not in result
    assert "**Source:** Apple IR (https://investor.apple.com)" in result


def test_tavily_search_tool_empty_results():
    """Verify TavilySearchTool returns fallback text when zero results are found."""
    tool = TavilySearchTool(api_key="tvly-mock-key")

    mock_client = MagicMock()
    mock_client.search.return_value = {"results": []}
    tool._client = mock_client

    result = tool.search("unknown obscure metric")
    assert result == "No relevant web results found."


def test_tavily_search_tool_empty_query():
    """Verify TavilySearchTool handles empty query."""
    tool = TavilySearchTool(api_key="tvly-mock-key")
    result = tool.search("   ")
    assert result == "No search query provided."


def test_tavily_search_tool_exception_handling():
    """Verify TavilySearchTool handles API errors gracefully."""
    tool = TavilySearchTool(api_key="tvly-mock-key")

    mock_client = MagicMock()
    mock_client.search.side_effect = RuntimeError("Rate limit exceeded")
    tool._client = mock_client

    result = tool.search("AAPL revenue")
    assert "Web search failed: RuntimeError: Rate limit exceeded" in result


def test_tavily_search_tool_missing_key_raises_error(monkeypatch):
    """Verify TavilySearchTool raises ValueError when API key is missing."""
    monkeypatch.setattr("backend.app.core.config.settings.TAVILY_API_KEY", "")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    tool = TavilySearchTool(api_key="")
    with pytest.raises(ValueError, match="TAVILY_API_KEY is not configured"):
        _ = tool.client


# ─────────────────────────────────────────────────────────────────────────────
# WEB SEARCH NODE & ROUTER TESTS
# ─────────────────────────────────────────────────────────────────────────────


def test_web_search_node_success():
    """Verify web_search_node executes search and attaches results to state."""
    mock_formatted_result = (
        "**Web Summary:** Apple FY 2023 revenue was $383.3B.\n\n---\n\n"
        "**Source:** SEC EDGAR (https://sec.gov)\n10-K filing content"
    )

    with patch(
        "backend.app.agent.nodes.web_search.tavily_tool.search",
        return_value=mock_formatted_result,
    ) as mock_search:
        state: AgentState = {
            "question": "What was Apple revenue?",
            "ticker": "AAPL",
            "fiscal_year": 2023,
            "documents": [],
            "filtered_documents": [],
            "web_search_needed": True,
            "grade_explanations": [],
            "web_results": None,
            "search_query": "Apple AAPL FY 2023 revenue",
            "math_needed": False,
            "math_code": None,
            "math_result": None,
            "generation": None,
            "steps": ["[Query Transform] Done"],
        }

        result = web_search_node(state)

        mock_search.assert_called_once_with("Apple AAPL FY 2023 revenue")
        assert result["web_results"] == mock_formatted_result
        assert len(result["steps"]) == 2
        assert "[Web Search] Executed web search for: 'Apple AAPL FY 2023 revenue'" == result["steps"][1]


def test_route_after_grading():
    """Verify route_after_grading returns correct branch based on web_search_needed."""
    # When web search is needed -> route to query_transform
    state_search_needed: AgentState = {
        "question": "test",
        "ticker": None,
        "fiscal_year": None,
        "documents": [],
        "filtered_documents": [],
        "web_search_needed": True,
        "grade_explanations": [],
        "web_results": None,
        "search_query": None,
        "math_needed": False,
        "math_code": None,
        "math_result": None,
        "generation": None,
        "steps": [],
    }
    assert route_after_grading(state_search_needed) == "query_transform"

    # When web search is NOT needed -> route to tool_decision
    state_no_search: AgentState = {
        "question": "test",
        "ticker": None,
        "fiscal_year": None,
        "documents": [],
        "filtered_documents": [{"chunk_index": 0}],
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
    assert route_after_grading(state_no_search) == "tool_decision"
