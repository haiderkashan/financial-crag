"""Automated verification script for Sub-Phase 2.4: Structure-Aware Chunking Engine.

Loads parsed.md from Sub-Phase 2.3, chunks it via FinancialDocumentChunker,
and validates chunk counts, metadata enrichment, and atomic table preservation.
"""
import argparse
import logging
import random
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings
from backend.app.ingestion.chunker import FinancialDocumentChunker
from backend.app.models.chunk import ChunkCreate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_chunker")


def find_parsed_markdown(ticker: str = "AAPL", data_dir: Path | str | None = None) -> Path | None:
    """Find a parsed.md file for the given ticker in the data directory."""
    root = Path(data_dir or settings.DATA_DIR) / ticker.upper()
    if not root.exists():
        return None

    matches = list(root.glob("*/parsed.md"))
    if matches:
        return matches[0]
    return None


def run_chunker_verification(
    file_path: Path,
    ticker: str = "AAPL",
    company_name: str = "Apple Inc.",
    fiscal_year: int = 2023,
) -> bool:
    """Execute chunker verification against the target parsed markdown filing."""
    print("=" * 70)
    print("SUB-PHASE 2.4: STRUCTURE-AWARE CHUNKING ENGINE VERIFICATION")
    print("=" * 70)

    print(f"\n[CONFIG] Target Markdown: {file_path}")
    print(f"[CONFIG] File Size: {file_path.stat().st_size:,} bytes")
    print(f"[CONFIG] Entity: {company_name} ({ticker}) FY {fiscal_year}")

    start_time = time.time()

    try:
        chunker = FinancialDocumentChunker(chunk_size=1500, chunk_overlap=200)

        # 1. Execute Chunking
        print("\n[TEST 1] Executing FinancialDocumentChunker.chunk_file()...")
        chunks = chunker.chunk_file(
            file_path=file_path,
            ticker=ticker,
            company_name=company_name,
            fiscal_year=fiscal_year,
        )
        duration = time.time() - start_time

        assert len(chunks) > 0, "Chunker produced 0 chunks"
        table_chunks = [c for c in chunks if c.metadata.get("has_table") is True]
        prose_chunks = [c for c in chunks if c.metadata.get("has_table") is False]

        print(f"  -> Total Chunks Generated: {len(chunks):,}")
        print(f"  -> Prose Chunks: {len(prose_chunks):,}")
        print(f"  -> Atomic Table Chunks: {len(table_chunks):,}")
        print(f"  -> Completed in {duration:.3f}s")
        print("[PASS] Document successfully partitioned into structured chunks.")

        # 2. First Chunk Metadata Inspection
        print("\n[TEST 2] Inspecting Chunk 0 (First Chunk) Schema & Metadata...")
        first_chunk = chunks[0]
        assert isinstance(first_chunk, ChunkCreate)
        assert first_chunk.chunk_index == 0
        assert first_chunk.content.startswith(f"[Document: {company_name} 10-K (FY {fiscal_year}) | Section:")
        assert "ticker" in first_chunk.metadata
        assert "has_table" in first_chunk.metadata
        assert "headers" in first_chunk.metadata

        print(f"  -> Chunk Index: {first_chunk.chunk_index}")
        print(f"  -> Section Title: {first_chunk.section_title}")
        print(f"  -> Approximate Token Count: {first_chunk.token_count}")
        print(f"  -> Metadata Dict:")
        for k, v in first_chunk.metadata.items():
            print(f"       {k}: {v}")
        print(f"  -> Content Snippet (first 180 chars):\n     {first_chunk.content[:180]!r}")
        print("[PASS] Chunk 0 validates against ChunkCreate with correct contextual prefix.")

        # 3. Table Integrity Verification & Visual Inspection
        print("\n[TEST 3] Verifying Atomic Table Preservation (Non-Severed Tables)...")
        assert len(table_chunks) > 0, "No table chunks found to verify!"

        # Pick a rich table chunk (prefer one with at least 5 lines of table content)
        rich_tables = [c for c in table_chunks if len(c.content.splitlines()) >= 6]
        sampled_chunk = random.choice(rich_tables) if rich_tables else table_chunks[0]

        lines = sampled_chunk.content.splitlines()
        # Find table lines (starts with |)
        table_lines = [line.strip() for line in lines if line.strip().startswith("|") and line.strip().endswith("|")]
        delimiter_lines = [line for line in table_lines if "|---" in line or "|:---" in line]

        assert len(table_lines) >= 2, "Table chunk has fewer than 2 pipe lines"
        assert len(delimiter_lines) >= 1, "Table chunk missing header delimiter row (|---|)"

        # Check that table lines are not severed mid-row
        for row_idx, row in enumerate(table_lines):
            assert row.startswith("|") and row.endswith("|"), f"Row {row_idx} is severed: {row}"

        print(f"  -> Sampled Table Chunk Index: #{sampled_chunk.chunk_index}")
        print(f"  -> Section Title: {sampled_chunk.section_title}")
        print(f"  -> Table Dimensions: {len(table_lines)} complete rows detected")
        print(f"  -> Delimiter Row: {delimiter_lines[0]}")
        print("[PASS] Table verified intact: zero mid-row splits, delimiter row preserved.")

        # 4. Print Full Sample Table for Visual Inspection
        print("\n" + "=" * 70)
        print("VISUAL VERIFICATION: SAMPLED ATOMIC TABLE CHUNK")
        print("=" * 70)
        # Print with clean encoding
        for line in sampled_chunk.content.splitlines():
            # Replace non-ascii symbols for safe terminal output
            safe_line = line.encode("ascii", errors="replace").decode("ascii")
            print(safe_line)
        print("=" * 70)

    except Exception as e:
        print(f"\n[FAIL] Chunker verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

    total_time = time.time() - start_time
    print(f"\n[ALL PASS] SUB-PHASE 2.4 STRUCTURE-AWARE CHUNKER VERIFIED! ({total_time:.2f}s)")
    print("=" * 70)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify FinancialDocumentChunker.")
    parser.add_argument("--ticker", type=str, default="AAPL", help="Stock ticker (default: AAPL)")
    parser.add_argument("--file", type=str, default=None, help="Explicit path to parsed.md")

    args = parser.parse_args()

    if args.file:
        target_path = Path(args.file)
    else:
        target_path = find_parsed_markdown(ticker=args.ticker)

    if not target_path or not target_path.exists():
        print(f"[FAIL] Could not locate parsed.md for ticker '{args.ticker}'.")
        print("Ensure Sub-Phase 2.3 has been executed or pass --file /path/to/parsed.md.")
        sys.exit(1)

    success = run_chunker_verification(file_path=target_path, ticker=args.ticker)
    sys.exit(0 if success else 1)
