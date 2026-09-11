"""Repository handling persistence and vector search for the sec_chunks table in Supabase."""
from typing import Optional, Union
from uuid import UUID
from supabase import Client

from backend.app.db.supabase import get_supabase_client
from backend.app.models.chunk import (
    ChunkCreate,
    ChunkInDB,
    ChunkSearchQuery,
    ChunkSearchResult,
)


class ChunkRepository:
    """Repository handling vector storage and similarity search for SEC chunks in Supabase."""

    def __init__(self, client: Optional[Client] = None) -> None:
        self._client = client

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = get_supabase_client()
        return self._client

    def insert_chunk(self, chunk_in: ChunkCreate) -> ChunkInDB:
        """Insert a single document chunk with its 384-dimensional embedding."""
        payload = {
            "filing_id": str(chunk_in.filing_id),
            "chunk_index": chunk_in.chunk_index,
            "section_title": chunk_in.section_title,
            "content": chunk_in.content,
            "metadata": chunk_in.metadata,
            "embedding": chunk_in.embedding,
            "token_count": chunk_in.token_count,
        }
        res = self.client.table("sec_chunks").insert(payload).execute()
        if not res.data:
            raise RuntimeError(
                f"Failed to insert chunk {chunk_in.chunk_index} for filing {chunk_in.filing_id}"
            )
        return ChunkInDB.model_validate(res.data[0])

    def bulk_insert_chunks(
        self, chunks: list[ChunkCreate], batch_size: int = 50
    ) -> list[ChunkInDB]:
        """Insert multiple document chunks in batches to respect PostgREST payload limits."""
        if not chunks:
            return []

        inserted_chunks: list[ChunkInDB] = []

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            payloads = [
                {
                    "filing_id": str(c.filing_id),
                    "chunk_index": c.chunk_index,
                    "section_title": c.section_title,
                    "content": c.content,
                    "metadata": c.metadata,
                    "embedding": c.embedding,
                    "token_count": c.token_count,
                }
                for c in batch
            ]
            res = self.client.table("sec_chunks").insert(payloads).execute()
            if not res.data:
                raise RuntimeError(
                    f"Failed to bulk insert batch of {len(batch)} chunks (starting index {i})"
                )
            inserted_chunks.extend(
                [ChunkInDB.model_validate(row) for row in res.data]
            )

        return inserted_chunks

    def get_chunks_by_filing(
        self, filing_id: Union[UUID, str], limit: int = 1000
    ) -> list[ChunkInDB]:
        """Fetch all chunks for a filing, ordered by sequential chunk index."""
        res = (
            self.client.table("sec_chunks")
            .select("*")
            .eq("filing_id", str(filing_id))
            .order("chunk_index", desc=False)
            .limit(limit)
            .execute()
        )
        if res.data:
            return [ChunkInDB.model_validate(row) for row in res.data]
        return []

    def search_similar_chunks(
        self, search_query: ChunkSearchQuery
    ) -> list[ChunkSearchResult]:
        """Execute vector similarity search via the match_sec_chunks database RPC function.

        Pre-filters by stock ticker and/or fiscal year if specified, then applies
        HNSW cosine vector similarity ordering (<=>).
        """
        rpc_params = {
            "query_embedding": search_query.query_embedding,
            "match_threshold": search_query.match_threshold,
            "match_count": search_query.match_count,
            "filter_ticker": search_query.filter_ticker,
            "filter_fiscal_year": search_query.filter_fiscal_year,
        }

        res = self.client.rpc("match_sec_chunks", rpc_params).execute()

        if res.data:
            return [ChunkSearchResult.model_validate(row) for row in res.data]
        return []

    def delete_chunks_by_filing(self, filing_id: Union[UUID, str]) -> int:
        """Delete all chunks belonging to a filing (e.g. for clean re-ingestion)."""
        res = (
            self.client.table("sec_chunks")
            .delete()
            .eq("filing_id", str(filing_id))
            .execute()
        )
        return len(res.data) if res.data else 0

    def delete_chunk(self, chunk_id: Union[UUID, str]) -> bool:
        """Delete a single chunk by UUID."""
        res = (
            self.client.table("sec_chunks")
            .delete()
            .eq("id", str(chunk_id))
            .execute()
        )
        return bool(res.data)


chunk_repo = ChunkRepository()
