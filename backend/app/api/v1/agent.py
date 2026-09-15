import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.app.agent.graph import crag_agent
from backend.app.agent.state import AgentState
from backend.app.api.deps import get_current_user
from backend.app.models.agent import AgentQueryRequest, AgentStepEvent
from backend.app.models.user import UserInDB

router = APIRouter(prefix="/agent")


@router.post("/query")
async def query_agent(
    request: AgentQueryRequest,
    current_user: UserInDB = Depends(get_current_user),
) -> StreamingResponse:
    """Execute CRAG agent analytical workflow and stream Server-Sent Events (SSE).

    Streams:
    - Step events: discrete state transitions for the Thought Inspection Panel
    - Generation events: final synthesized Markdown answer
    - Done event: completion signal
    """
    initial_state: AgentState = {
        "question": request.question.strip(),
        "ticker": request.ticker.strip().upper() if request.ticker else None,
        "fiscal_year": request.fiscal_year,
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

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for update in crag_agent.astream(initial_state, stream_mode="updates"):
                for node_name, state_update in update.items():
                    # 1. Stream step log for Thought Inspection Panel
                    if "steps" in state_update and state_update["steps"]:
                        step_msg = state_update["steps"][-1]
                        step_payload = AgentStepEvent(
                            type="step",
                            node=node_name,
                            message=step_msg,
                        ).model_dump_json()
                        yield f"data: {step_payload}\n\n"

                    # 2. Stream synthesized answer
                    if "generation" in state_update and state_update["generation"]:
                        gen_payload = AgentStepEvent(
                            type="generation",
                            node=node_name,
                            content=state_update["generation"],
                        ).model_dump_json()
                        yield f"data: {gen_payload}\n\n"

            done_payload = AgentStepEvent(type="done").model_dump_json()
            yield f"data: {done_payload}\n\n"

        except Exception as exc:
            err_payload = AgentStepEvent(
                type="error",
                message=f"Agent execution encountered an error: {type(exc).__name__}: {str(exc)}",
            ).model_dump_json()
            yield f"data: {err_payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
