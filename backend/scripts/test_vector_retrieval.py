"""Vector retrieval verification script testing Supabase match_sec_chunks RPC.

Executes a semantic similarity query against ingested 10-K chunks using
BAAI/bge-small-en-v1.5 dense query embeddings.

Usage:
    python backend/scripts/test_vector_retrieval.py
"""
import sys

# Ensure proper encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.app.db.repositories.chunk_repo import chunk_repo
from backend.app.ingestion.embedder import embedder
from backend.app.models.chunk import ChunkSearchQuery


def test_retrieval(
    query: str = "What were Apple's total net sales and operating expenses?",
    ticker: str = "AAPL",
    fiscal_year: int = 2023,
    top_k: int = 5,
):
    print("=" * 80)
    print(" FINANCIAL CRAG : VECTOR RETRIEVAL TEST")
    print("=" * 80)
    print(f" Query       : \"{query}\"")
    print(f" Filter      : Ticker={ticker}, Year={fiscal_year}")
    print(f" Top-K       : {top_k}")
    print("-" * 80)

    print("Generating dense query embedding (with BGE asymmetric instruction)...")
    query_vector = embedder.embed_query(query)
    print(f"Query vector dimensions: {len(query_vector)}")

    search_query = ChunkSearchQuery(
        query_embedding=query_vector,
        match_threshold=0.3,
        match_count=top_k,
        filter_ticker=ticker,
        filter_fiscal_year=fiscal_year,
    )

    print("Invoking Supabase match_sec_chunks RPC function...")
    results = chunk_repo.search_similar_chunks(search_query)

    print(f"Retrieved {len(results)} matching chunks:")
    print("=" * 80)

    if not results:
        print("[WARNING] No chunks matched the query above threshold 0.3.")
        return 1

    for idx, r in enumerate(results, 1):
        has_table = r.metadata.get("has_table", False)
        print(f"\n[{idx}] SIMILARITY SCORE: {r.similarity:.4f} | CHUNK INDEX: {r.chunk_index} | HAS_TABLE: {has_table}")
        print(f"    Section : {r.section_title or 'N/A'}")
        print(f"    Company : {r.company_name} ({r.ticker}) FY {r.fiscal_year}")
        print("    " + "-" * 70)

        # Print content preview (first 10 lines)
        lines = r.content.strip().split("\n")
        preview = "\n    ".join(lines[:12])
        print(f"    {preview}")
        if len(lines) > 12:
            print(f"    ... [{len(lines) - 12} more lines omitted] ...")

    print("\n" + "=" * 80)
    print(" [OK] Vector retrieval verification complete.")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    code = test_retrieval()
    sys.exit(code)
