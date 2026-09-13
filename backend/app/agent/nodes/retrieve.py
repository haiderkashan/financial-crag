from typing import Any

from backend.app.agent.state import AgentState
from backend.app.core.config import settings
from backend.app.db.repositories.chunk_repo import chunk_repo
from backend.app.ingestion.embedder import embedder
from backend.app.models.chunk import ChunkSearchQuery


def retrieve_node(state: AgentState) -> dict[str, Any]:
    """Retrieve relevant SEC 10-K document chunks from Supabase pgvector.

    A pure, deterministic data operation (no LLM):
    1. Encodes question into a 384d BGE query vector.
    2. Executes similarity search via chunk_repo against match_sec_chunks RPC.
    3. Updates documents in state and appends progress log to steps.
    """
    question = (state.get("question") or "").strip()
    ticker = state.get("ticker")
    fiscal_year = state.get("fiscal_year")

    # Generate 384d query vector with BGE asymmetric instruction prefix
    query_embedding = embedder.embed_query(question)

    # Search Supabase vector store with metadata filtering
    search_query = ChunkSearchQuery(
        query_embedding=query_embedding,
        match_threshold=settings.CRAG_SIMILARITY_THRESHOLD,
        match_count=settings.CRAG_RETRIEVAL_TOP_K,
        filter_ticker=ticker,
        filter_fiscal_year=fiscal_year,
    )
    search_results = chunk_repo.search_similar_chunks(search_query)

    # Format documents as serialized dictionaries
    documents = [res.model_dump(mode="json") for res in search_results]

    step_log = (
        f"[Retrieve] Found {len(documents)} chunks from Supabase "
        f"(ticker={ticker or 'ALL'}, year={fiscal_year or 'ALL'})."
    )

    existing_steps = list(state.get("steps") or [])

    return {
        "documents": documents,
        "steps": existing_steps + [step_log],
    }
