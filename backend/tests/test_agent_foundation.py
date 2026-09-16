import pytest
from langchain_groq import ChatGroq

from backend.app.agent import AgentState, get_llm


def test_agent_state_annotations():
    """Verify that AgentState TypedDict contains all required keys."""
    annotations = AgentState.__annotations__
    expected_keys = [
        "question",
        "ticker",
        "fiscal_year",
        "documents",
        "filtered_documents",
        "web_search_needed",
        "grade_explanations",
        "web_results",
        "search_query",
        "math_needed",
        "math_code",
        "math_result",
        "generation",
        "steps",
    ]
    for key in expected_keys:
        assert key in annotations, f"Missing key '{key}' in AgentState"
    assert annotations["steps"] == list[str]


def test_get_llm_missing_key_raises_error(monkeypatch):
    """Verify get_llm raises ValueError when no Groq key is provided."""
    monkeypatch.setattr("backend.app.core.config.settings.GROQ_API_KEY", "")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(ValueError, match="GROQ_API_KEY is not configured"):
        get_llm(provider="groq")


def test_get_llm_success_with_key():
    """Verify get_llm successfully instantiates ChatGroq."""
    llm = get_llm(api_key="gsk_mock_test_key", temperature=0.2)
    assert isinstance(llm, ChatGroq)
    assert llm.model_name == "qwen/qwen3.8-27b"
    assert llm.temperature == pytest.approx(0.2)


def test_get_llm_unsupported_provider():
    """Verify get_llm raises ValueError for unsupported provider."""
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        get_llm(provider="anthropic_mock")
