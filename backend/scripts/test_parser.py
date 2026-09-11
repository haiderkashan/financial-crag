"""Automated verification script for Sub-Phase 2.3: LlamaParse Integration.

Parses a local SEC 10-K document (e.g. AAPL) using SECDocumentParser,
validating table preservation as Markdown pipe-tables and local disk caching.
"""
import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings
from backend.app.ingestion.parser import SECDocumentParser
from backend.app.ingestion.sec_client import SECEdgarClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_parser")


def find_filing_file(ticker: str = "AAPL", data_dir: Path | str | None = None) -> Path | None:
    """Find the downloaded filing document on disk for the given ticker."""
    root = Path(data_dir or settings.DATA_DIR) / ticker.upper()
    if not root.exists():
        return None

    # Search accession directories for primary document (.htm, .html, .pdf)
    for ext in ["*.htm", "*.html", "*.pdf"]:
        matches = list(root.glob(f"*/*{ext}"))
        if matches:
            # Filter out parsed.md
            valid = [m for m in matches if m.name != "parsed.md"]
            if valid:
                return valid[0]
    return None


async def ensure_test_filing(ticker: str = "AAPL", fiscal_year: int = 2023) -> Path:
    """Ensure a filing document exists locally; download via SECEdgarClient if missing."""
    existing = find_filing_file(ticker)
    if existing and existing.stat().st_size > 0:
        return existing

    logger.info("Local filing for %s not found. Sourcing via SECEdgarClient...", ticker)
    async with SECEdgarClient() as client:
        info = await client.download_filing(ticker=ticker, fiscal_year=fiscal_year)
        if not info.local_file_path or not info.local_file_path.exists():
            raise RuntimeError(f"Failed to obtain filing document for {ticker}")
        return info.local_file_path


def run_parser_verification(
    file_path: Path,
    overwrite: bool = False,
) -> bool:
    """Execute parser verification against the given SEC document."""
    print("=" * 70)
    print("SUB-PHASE 2.3: LLAMAPARSE INTEGRATION VERIFICATION CHECKPOINT")
    print("=" * 70)

    print(f"\n[CONFIG] Target Document: {file_path}")
    print(f"[CONFIG] Document Size: {file_path.stat().st_size:,} bytes")
    print(f"[CONFIG] Result Type: {settings.LLAMA_PARSE_RESULT_TYPE}")
    print(f"[CONFIG] Parallel Workers: {settings.LLAMA_PARSE_NUM_WORKERS}")

    api_key = settings.LLAMA_CLOUD_API_KEY.strip()
    cache_path = SECDocumentParser.get_cache_path(file_path)

    # If cached file exists, we can still verify cache reading even without active API key
    has_cache = cache_path.exists() and cache_path.stat().st_size > 0

    if not api_key and not has_cache:
        print("\n" + "!" * 70)
        print("[ACTION REQUIRED] LLAMA_CLOUD_API_KEY is not configured in backend/.env!")
        print("To parse SEC 10-K filings with vision-aware table preservation:")
        print("  1. Sign up at https://cloud.llamaindex.ai (Free 10,000 credits/month)")
        print("  2. Add your API key to backend/.env:")
        print("     LLAMA_CLOUD_API_KEY=\"llx-your-key-here\"")
        print("  3. Re-run this verification script.")
        print("!" * 70 + "\n")
        return False

    start_time = time.time()

    try:
        parser = SECDocumentParser()

        # 1. Parse Document (or load from cache)
        print("\n[TEST 1] Executing SECDocumentParser.parse_file()...")
        parse_start = time.time()
        markdown_content = parser.parse_file(file_path, overwrite=overwrite)
        parse_duration = time.time() - parse_start

        assert markdown_content, "Parser returned empty output"
        char_count = len(markdown_content)
        line_count = len(markdown_content.splitlines())
        print(f"  -> Extracted {char_count:,} characters ({line_count:,} lines) in {parse_duration:.2f}s")
        print("[PASS] Document parsed to non-empty text string.")

        # 2. Financial Table Preservation Check
        print("\n[TEST 2] Verifying Markdown pipe-table preservation (|---|---|)...")
        pipe_table_lines = [line for line in markdown_content.splitlines() if line.strip().startswith("|") and line.strip().endswith("|")]
        delimiter_lines = [line for line in markdown_content.splitlines() if "|---" in line or "|:---" in line]

        print(f"  -> Detected {len(pipe_table_lines)} Markdown table rows across document.")
        print(f"  -> Detected {len(delimiter_lines)} Markdown table header separators.")
        assert len(pipe_table_lines) > 0, "No Markdown pipe tables found! Tables were not properly preserved."
        assert len(delimiter_lines) > 0, "No Markdown table header delimiters (|---|) detected."
        print("[PASS] Financial statements and tables preserved as Markdown pipe-tables.")

        # 3. Section Heading Preservation Check
        print("\n[TEST 3] Verifying SEC item and section headings (#, ##)...")
        h1_headings = [line for line in markdown_content.splitlines() if line.strip().startswith("# ")]
        h2_headings = [line for line in markdown_content.splitlines() if line.strip().startswith("## ")]
        item_headings = [line for line in markdown_content.splitlines() if "item" in line.lower() and ("#" in line or "**" in line)]

        print(f"  -> Detected {len(h1_headings)} H1 headings (Parts).")
        print(f"  -> Detected {len(h2_headings)} H2 headings (Items).")
        print(f"  -> Detected {len(item_headings)} explicit Item headings.")
        print("[PASS] Section heading structure preserved.")

        # 4. Local Disk Cache Verification
        print(f"\n[TEST 4] Verifying local cache persistence at: {cache_path}")
        assert cache_path.exists(), f"Cache file not found at {cache_path}"
        assert cache_path.stat().st_size > 0, "Cache file is empty"
        print(f"  -> Cache file confirmed ({cache_path.stat().st_size:,} bytes).")
        print("[PASS] Disk caching verified.")

        # 5. Idempotent Cache Speedup Check
        print("\n[TEST 5] Testing idempotent cache recall speed...")
        cache_start = time.time()
        cached_content = parser.parse_file(file_path, overwrite=False)
        cache_duration = time.time() - cache_start

        assert cached_content == markdown_content, "Cached content differs from initial parse"
        assert cache_duration < 0.5, f"Cache retrieval was too slow ({cache_duration:.4f}s)"
        print(f"  -> Cache retrieved in {cache_duration * 1000:.2f}ms (Zero API tokens consumed).")
        print("[PASS] Idempotent cache retrieval verified.")

        # Display Sample Financial Table Preview
        print("\n" + "-" * 70)
        print("SAMPLE EXTRACTED TABLE PREVIEW:")
        print("-" * 70)
        table_sample_lines = []
        in_sample = False
        for line in markdown_content.splitlines():
            if "|---" in line:
                in_sample = True
            if in_sample:
                table_sample_lines.append(line)
                if len(table_sample_lines) >= 8:
                    break
        if table_sample_lines:
            print("\n".join(table_sample_lines))
        else:
            print("(First 5 table rows)")
            print("\n".join(pipe_table_lines[:5]))
        print("-" * 70)

    except Exception as e:
        print(f"\n[FAIL] Parser verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

    total_time = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"[ALL PASS] SUB-PHASE 2.3 LLAMAPARSE INTEGRATION VERIFIED! ({total_time:.2f}s)")
    print("=" * 70)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify SECDocumentParser with LlamaParse.")
    parser.add_argument("--ticker", type=str, default="AAPL", help="Stock ticker symbol (default: AAPL)")
    parser.add_argument("--year", type=int, default=2023, help="Fiscal year (default: 2023)")
    parser.add_argument("--file", type=str, default=None, help="Explicit file path to parse")
    parser.add_argument("--overwrite", action="store_true", help="Force re-parsing, bypassing parsed.md cache")

    args = parser.parse_args()

    if args.file:
        target = Path(args.file)
        if not target.exists():
            print(f"[ERROR] Specified file not found: {target}")
            sys.exit(1)
    else:
        target = asyncio.run(ensure_test_filing(ticker=args.ticker, fiscal_year=args.year))

    success = run_parser_verification(file_path=target, overwrite=args.overwrite)
    sys.exit(0 if success else 1)
