from datetime import datetime
from unittest.mock import patch
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.api.deps import get_current_user
from backend.app.main import app
from backend.app.models.user import UserInDB


@pytest.fixture
def mock_analyst_user() -> UserInDB:
    return UserInDB(
        id=uuid.uuid4(),
        email="lead.analyst@hedgefund.com",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def test_agent_query_endpoint_unauthorized():
    """Verify POST /api/v1/agent/query rejects unauthenticated requests with 401."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/agent/query",
        json={"question": "What was Apple's revenue in 2023?"},
    )
    assert response.status_code == 401
    assert "Authentication credentials were not provided" in response.text


def test_api_streaming(mock_analyst_user):
    """Verify POST /api/v1/agent/query correctly formats events as Server-Sent Events (SSE)."""
    app.dependency_overrides[get_current_user] = lambda: mock_analyst_user

    async def mock_astream(initial_state, stream_mode="updates"):
        yield {"retrieve": {"steps": ["[Retrieve] Found 3 chunks from Supabase."]}}
        yield {"math_repl": {"steps": ["[Math REPL] Executed arithmetic computation."]}}
        yield {"generate": {"generation": "Apple FY 2023 revenue was $383,285 million."}}

    with patch("backend.app.api.v1.agent.crag_agent.astream", side_effect=mock_astream):
        client = TestClient(app)
        response = client.post(
            "/api/v1/agent/query",
            json={
                "question": "What was Apple's total net sales in 2023 and how did it change?",
                "ticker": "AAPL",
                "fiscal_year": 2023,
            },
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        assert response.headers.get("cache-control") == "no-cache"

        body = response.text

        # Verify exact SSE formatting (data: {...}\n\n)
        assert "data: " in body
        assert "\n\n" in body
        assert '"type":"step"' in body
        assert '"node":"retrieve"' in body
        assert "[Retrieve] Found 3 chunks from Supabase." in body

        assert '"node":"math_repl"' in body
        assert "[Math REPL] Executed arithmetic computation." in body

        assert '"type":"generation"' in body
        assert "Apple FY 2023 revenue was $383,285 million." in body

        assert '"type":"done"' in body

    app.dependency_overrides.clear()


def test_api_streaming_error_handling(mock_analyst_user):
    """Verify exceptions inside the graph yield structured error events instead of 500 crash."""
    app.dependency_overrides[get_current_user] = lambda: mock_analyst_user

    async def mock_error_astream(initial_state, stream_mode="updates"):
        raise RuntimeError("Vector store connection timeout")
        yield  # Make it an async generator

    with patch("backend.app.api.v1.agent.crag_agent.astream", side_effect=mock_error_astream):
        client = TestClient(app)
        response = client.post(
            "/api/v1/agent/query",
            json={"question": "What was Apple revenue?"},
        )

        assert response.status_code == 200
        body = response.text
        assert '"type":"error"' in body
        assert "Vector store connection timeout" in body

    app.dependency_overrides.clear()
