"""Automated verification script for Sub-Phase 2.1: Vector Store Schema & Repository Layer."""
import math
import os
import random
import sys
from datetime import date
from pathlib import Path
from uuid import uuid4

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings
from backend.app.db.repositories.chunk_repo import chunk_repo
from backend.app.db.repositories.filing_repo import filing_repo
from backend.app.db.supabase import get_supabase_client
from backend.app.models.chunk import (
    ChunkCreate,
    ChunkInDB,
    ChunkSearchQuery,
    ChunkSearchResult,
)
from backend.app.models.filing import (
    FilingCreate,
    FilingInDB,
    IngestionStatus,
)


def generate_normalized_vector(dim: int = 384, seed: int = 42) -> list[float]:
    """Generate a deterministic, L2-normalized vector matching BGE-small dimensions."""
    rng = random.Random(seed)
    raw = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [round(x / norm, 6) for x in raw]


def run_vector_schema_verification() -> bool:
    """Execute end-to-end verification for Sub-Phase 2.1."""
    print("=" * 70)
    print("SUB-PHASE 2.1: VECTOR STORE SCHEMA & REPOSITORY VERIFICATION CHECKPOINT")
    print("=" * 70)

    # 1. Environment & Credentials Check
    url = settings.SUPABASE_URL
    key = settings.effective_supabase_key

    if not url or not key:
        print("[FAIL] Missing Supabase configuration in environment.")
        return False

    print(f"[OK] Supabase URL: {url}")
    print(f"[OK] Supabase Key: {key[:8]}...{key[-4:]}")

    try:
        client = get_supabase_client()
        print("[OK] Supabase client singleton active.")
    except Exception as e:
        print(f"[FAIL] Error obtaining Supabase client: {e}")
        return False

    test_uid = uuid4().hex[:8]
    test_ticker = "TEST"
    test_accession = f"0000000000-23-{test_uid}"
    created_filing: FilingInDB | None = None

    try:
        # 2. Test Filing Creation
        print(f"\n[TEST 1] Creating test filing record: {test_ticker} (Accession: {test_accession})")
        filing_in = FilingCreate(
            ticker=test_ticker,
            company_name="Test Enterprise Corp",
            form_type="10-K",
            fiscal_year=2023,
            fiscal_period="FY",
            accession_number=test_accession,
            filing_date=date(2023, 10, 15),
            source_url="https://www.sec.gov/Archives/edgar/data/test/filing.htm",
            parse_status=IngestionStatus.PENDING,
        )
        created_filing = filing_repo.create_filing(filing_in)
        assert created_filing is not None
        assert created_filing.ticker == test_ticker
        assert created_filing.fiscal_year == 2023
        assert created_filing.parse_status == IngestionStatus.PENDING
        print(f"  -> Filing persisted with ID: {created_filing.id}")
        print("[PASS] Filing creation validated against Pydantic schema FilingInDB.")

        # 3. Test Filing Retrieval
        print(f"\n[TEST 2] Querying filing by accession number: {test_accession}")
        queried = filing_repo.get_by_accession(test_accession)
        assert queried is not None
        assert queried.id == created_filing.id
        print(f"  -> Successfully retrieved filing: {queried.company_name}")
        print("[PASS] Accession lookup successful.")

        print(f"\n[TEST 3] Querying filing by ticker & year: {test_ticker} / 2023")
        queried_by_year = filing_repo.get_by_ticker_and_year(test_ticker, 2023)
        assert queried_by_year is not None
        assert queried_by_year.id == created_filing.id
        print("[PASS] Ticker and fiscal year lookup successful.")

        # 4. Generate 384-dimensional Normalized Vectors
        print("\n[TEST 4] Generating 384d normalized embeddings matching BGE-small specification")
        vec_revenue = generate_normalized_vector(384, seed=100)
        vec_revenue_similar = generate_normalized_vector(384, seed=101)
        vec_risk = generate_normalized_vector(384, seed=999)

        assert len(vec_revenue) == 384
        assert len(vec_risk) == 384
        print("[PASS] 384-dimensional vector constraint satisfied.")

        # 5. Bulk Insert Document Chunks with Embeddings
        print("\n[TEST 5] Bulk inserting 3 test chunks with vector(384) embeddings")
        chunks_in = [
            ChunkCreate(
                filing_id=created_filing.id,
                chunk_index=0,
                section_title="Item 8. Consolidated Statements of Operations",
                content="| In millions | 2023 | 2022 |\n| Total net sales | $383,285 | $394,328 |",
                metadata={"has_table": True, "page": 42},
                embedding=vec_revenue,
                token_count=35,
            ),
            ChunkCreate(
                filing_id=created_filing.id,
                chunk_index=1,
                section_title="Item 8. Balance Sheet Overview",
                content="Total assets as of September 30, 2023 were $352,583 million compared to $352,755 million in 2022.",
                metadata={"has_table": False, "page": 43},
                embedding=vec_revenue_similar,
                token_count=28,
            ),
            ChunkCreate(
                filing_id=created_filing.id,
                chunk_index=2,
                section_title="Item 1A. Risk Factors",
                content="Global macroeconomic volatility, currency exchange fluctuations, and semiconductor supply constraints may impair gross margins.",
                metadata={"has_table": False, "page": 12},
                embedding=vec_risk,
                token_count=25,
            ),
        ]

        inserted_chunks = chunk_repo.bulk_insert_chunks(chunks_in, batch_size=2)
        assert len(inserted_chunks) == 3
        for c in inserted_chunks:
            assert isinstance(c, ChunkInDB)
            assert len(c.embedding) == 384
        print(f"  -> Successfully inserted {len(inserted_chunks)} chunks with embeddings.")
        print("[PASS] Bulk chunk insertion validated against Pydantic schema ChunkInDB.")

        # 6. Query Chunks by Filing ID
        print(f"\n[TEST 6] Fetching chunks for filing ID: {created_filing.id}")
        retrieved_chunks = chunk_repo.get_chunks_by_filing(created_filing.id)
        assert len(retrieved_chunks) == 3
        assert retrieved_chunks[0].chunk_index == 0
        assert retrieved_chunks[1].chunk_index == 1
        assert retrieved_chunks[2].chunk_index == 2
        print("[PASS] Chunk sequence ordering preserved.")

        # 7. Test Vector Similarity Search (match_sec_chunks RPC)
        print("\n[TEST 7] Executing vector similarity search via match_sec_chunks RPC")
        search_query = ChunkSearchQuery(
            query_embedding=vec_revenue,
            match_threshold=0.0,
            match_count=5,
            filter_ticker=test_ticker,
            filter_fiscal_year=2023,
        )
        search_results = chunk_repo.search_similar_chunks(search_query)
        assert len(search_results) >= 1
        print(f"  -> Search retrieved {len(search_results)} relevant chunks.")

        top_match = search_results[0]
        assert isinstance(top_match, ChunkSearchResult)
        assert top_match.ticker == test_ticker
        assert top_match.fiscal_year == 2023
        assert top_match.chunk_index == 0
        print(f"  -> Top Match: [{top_match.section_title}] (Similarity: {top_match.similarity:.4f})")
        assert top_match.similarity >= 0.99, "Identical vector query should yield similarity ~1.0"
        print("[PASS] HNSW vector similarity search returned exact top candidate.")

        # 8. Test Metadata Pre-Filtering Pruning
        print("\n[TEST 8] Testing metadata pre-filtering (Unmatched Ticker Filter)")
        unmatched_query = ChunkSearchQuery(
            query_embedding=vec_revenue,
            match_threshold=0.0,
            match_count=5,
            filter_ticker="NONEXISTENT_TICKER",
            filter_fiscal_year=2023,
        )
        unmatched_results = chunk_repo.search_similar_chunks(unmatched_query)
        assert len(unmatched_results) == 0, "Filter for nonexistent ticker must return 0 results."
        print("[PASS] Metadata pre-filtering successfully pruned search space before vector ranking.")

        # 9. Test Ingestion Status Transition
        print(f"\n[TEST 9] Updating filing status to COMPLETE (total_chunks=3)")
        updated_filing = filing_repo.update_status(
            filing_id=created_filing.id,
            parse_status=IngestionStatus.COMPLETE,
            total_chunks=3,
        )
        assert updated_filing is not None
        assert updated_filing.parse_status == IngestionStatus.COMPLETE
        assert updated_filing.total_chunks == 3
        print(f"  -> Status updated: {updated_filing.parse_status} (chunks: {updated_filing.total_chunks})")
        print("[PASS] Filing status transition successfully persisted.")

    except Exception as e:
        print(f"\n[FAIL] Verification encountered an error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 10. Cleanup Test Records
        print("\n[CLEANUP] Cleaning up test filing and cascading chunks...")
        if created_filing:
            deleted = filing_repo.delete_filing(created_filing.id)
            print(f"  -> Deleted test filing: {created_filing.id} (Cascade chunks deleted)")
            remaining_chunks = chunk_repo.get_chunks_by_filing(created_filing.id)
            assert len(remaining_chunks) == 0
            print("[PASS] Cleanup verified: Zero orphaned chunks remaining.")

    print("\n" + "=" * 70)
    print("[ALL PASS] SUB-PHASE 2.1 VECTOR SCHEMA & REPOSITORY VERIFIED SUCCESSFULLY!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_vector_schema_verification()
    sys.exit(0 if success else 1)
