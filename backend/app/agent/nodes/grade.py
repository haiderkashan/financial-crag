import asyncio
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from backend.app.agent.llm import get_llm
from backend.app.agent.state import AgentState

GRADE_SYSTEM_PROMPT = """You are an expert financial research analyst evaluating whether a retrieved SEC 10-K document chunk is relevant to an analytical question.

GRADING CRITERIA:
1. Score 'yes' if the chunk contains ANY relevant financial figures, operational metrics, tables, MD&A commentary, risk factors, or context that can help answer the question, even partially.
2. Score 'no' ONLY if the chunk is completely irrelevant to the subject matter of the question (e.g. standard boilerplate notices, sign-off signature blocks, or unrelated item sections).
3. When in doubt, prefer 'yes'. Preserving context for synthesis is preferred over aggressive filtering.

Provide a binary score ('yes' or 'no') and a concise one-sentence explanation."""


class GradeChunk(BaseModel):
    """Binary relevance assessment for a retrieved document chunk."""

    binary_score: Literal["yes", "no"] = Field(
        description="Relevance score: 'yes' if the chunk contains information relevant to the question, 'no' otherwise."
    )
    explanation: str = Field(
        description="One-sentence rationale explaining the grading decision."
    )


async def _grade_single_chunk(
    grader: Any,
    question: str,
    doc: dict,
    index: int,
) -> tuple[int, dict, GradeChunk]:
    """Grade an individual document chunk asynchronously."""
    content = doc.get("content", "")
    section_title = doc.get("section_title") or "Unknown Section"
    ticker = doc.get("ticker", "UNKNOWN")
    year = doc.get("fiscal_year", "UNKNOWN")

    user_content = (
        f"Analyst Question: {question}\n\n"
        f"Document Metadata: Ticker={ticker}, Fiscal Year={year}, Section={section_title}\n\n"
        f"Document Chunk Content:\n{content}"
    )

    try:
        messages = [
            SystemMessage(content=GRADE_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]
        result: GradeChunk = await grader.ainvoke(messages)
    except Exception as exc:
        # Fallback to permissive grading if LLM call fails
        result = GradeChunk(
            binary_score="yes",
            explanation=f"Grading fallback to 'yes' due to evaluation exception: {exc}",
        )

    return index, doc, result


async def grade_documents_node(state: AgentState) -> dict[str, Any]:
    """Grade the relevance of retrieved document chunks concurrently.

    1. Invokes the LLM with structured output (GradeChunk) across all chunks concurrently.
    2. Sorts evaluation results by original chunk order for deterministic logs.
    3. Retains relevant chunks in filtered_documents and records explanations.
    4. CRITICAL FIX: Sets web_search_needed = True ONLY when len(filtered_documents) == 0.
    """
    question = (state.get("question") or "").strip()
    documents = list(state.get("documents") or [])

    if not documents:
        existing_steps = list(state.get("steps") or [])
        return {
            "filtered_documents": [],
            "web_search_needed": True,
            "grade_explanations": [],
            "steps": existing_steps
            + ["[Grade] No chunks available to grade. Web search triggered."],
        }

    llm = get_llm(temperature=0.0, max_tokens=250)
    grader = llm.with_structured_output(GradeChunk)

    # Concurrently evaluate all chunks
    tasks = [
        _grade_single_chunk(grader, question, doc, idx)
        for idx, doc in enumerate(documents)
    ]
    graded_results = await asyncio.gather(*tasks)

    # Sort by original index to ensure deterministic ordering
    graded_results.sort(key=lambda item: item[0])

    filtered_documents: list[dict] = []
    grade_explanations: list[dict] = []

    for idx, doc, grade in graded_results:
        is_relevant = grade.binary_score.lower().strip() == "yes"
        grade_explanations.append(
            {
                "chunk_index": doc.get("chunk_index", idx),
                "binary_score": grade.binary_score,
                "explanation": grade.explanation,
            }
        )
        if is_relevant:
            filtered_documents.append(doc)

    # CRITICAL ARCHITECTURE FIX:
    # Set web_search_needed = True ONLY if len(filtered_documents) == 0.
    # Do NOT trigger web search if just one chunk is irrelevant.
    web_search_needed = len(filtered_documents) == 0

    discarded_count = len(documents) - len(filtered_documents)
    summary_log = (
        f"[Grade] Evaluated {len(documents)} chunks: "
        f"{len(filtered_documents)} relevant, {discarded_count} discarded. "
        f"Web search {'triggered (0 relevant chunks)' if web_search_needed else 'not needed'}."
    )

    existing_steps = list(state.get("steps") or [])

    return {
        "filtered_documents": filtered_documents,
        "web_search_needed": web_search_needed,
        "grade_explanations": grade_explanations,
        "steps": existing_steps + [summary_log],
    }
