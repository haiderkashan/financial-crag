"""Integration tests for SEC filings, chunks, and vector similarity search."""
import math
import random
from datetime import date
from uuid import uuid4
import pytest

from backend.app.db.repositories.chunk_repo import chunk_repo
from backend.app.db.repositories.filing_repo import filing_repo
from backend.app.models.chunk import (
    ChunkCreate,
    ChunkInDB,
    ChunkSearchQuery,
    ChunkSearchResult,
)
from backend.app.models.filing import FilingCreate, FilingInDB, IngestionStatus


def _generate_vector(dim: int = 384, seed: int = 42) -> list[float]:
    """Generate a deterministic normalized vector."""
    rng = random.Random(seed)
    raw = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [round(x / norm, 6) for x in raw]


@pytest.mark.asyncio
async def test_filing_and_vector_chunk_lifecycle():
    """Verify end-to-end filing registration, chunk embedding persistence, and RPC vector search."""
    test_uid = uuid4().hex[:8]
    test_ticker = "PYTEST"
    test_accession = f"0000000000-23-{test_uid}"

    # 1. Create Filing
    filing_in = FilingCreate(
        ticker=test_ticker,
        company_name="PyTest Holding Corp",
        form_type="10-K",
        fiscal_year=2023,
        accession_number=test_accession,
        filing_date=date(2023, 11, 1),
        parse_status=IngestionStatus.PENDING,
    )
    filing = filing_repo.create_filing(filing_in)
    assert isinstance(filing, FilingInDB)
    assert filing.ticker == test_ticker
    assert filing.accession_number == test_accession

    try:
        # 2. Insert Chunks with 384d Vectors
        vec_a = _generate_vector(384, seed=10)
        vec_b = _generate_vector(384, seed=20)

        chunk_a = ChunkCreate(
            filing_id=filing.id,
            chunk_index=0,
            section_title="Financial Statements",
            content="Total revenue was $100M in FY2023.",
            metadata={"table": True},
            embedding=vec_a,
            token_count=10,
        )
        chunk_b = ChunkCreate(
            filing_id=filing.id,
            chunk_index=1,
            section_title="Risk Factors",
            content="Interest rate risks could adversely affect profit margins.",
            metadata={"table": False},
            embedding=vec_b,
            token_count=12,
        )

        inserted = chunk_repo.bulk_insert_chunks([chunk_a, chunk_b])
        assert len(inserted) == 2
        assert all(isinstance(c, ChunkInDB) for c in inserted)

        # 3. Fetch Chunks by Filing
        fetched = chunk_repo.get_chunks_by_filing(filing.id)
        assert len(fetched) == 2
        assert fetched[0].chunk_index == 0
        assert fetched[1].chunk_index == 1

        # 4. Perform Vector Search (RPC match_sec_chunks)
        query = ChunkSearchQuery(
            query_embedding=vec_a,
            match_threshold=0.0,
            match_count=5,
            filter_ticker=test_ticker,
            filter_fiscal_year=2023,
        )
        results = chunk_repo.search_similar_chunks(query)
        assert len(results) >= 1
        assert isinstance(results[0], ChunkSearchResult)
        assert results[0].chunk_index == 0
        assert results[0].ticker == test_ticker
        assert results[0].similarity >= 0.99

        # 5. Filter for Nonexistent Ticker
        empty_query = ChunkSearchQuery(
            query_embedding=vec_a,
            match_threshold=0.0,
            match_count=5,
            filter_ticker="NONEXISTENT",
        )
        empty_results = chunk_repo.search_similar_chunks(empty_query)
        assert len(empty_results) == 0

        # 6. Update Status
        updated = filing_repo.update_status(filing.id, IngestionStatus.COMPLETE, total_chunks=2)
        assert updated.parse_status == IngestionStatus.COMPLETE
        assert updated.total_chunks == 2

    finally:
        # Cleanup
        filing_repo.delete_filing(filing.id)
        remaining = chunk_repo.get_chunks_by_filing(filing.id)
        assert len(remaining) == 0
