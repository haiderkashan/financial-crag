"""Automated verification script for Sub-Phase 2.2: SEC EDGAR Document Sourcing.

Downloads an official SEC 10-K filing document (e.g. AAPL or NVDA) and saves it to local DATA_DIR.
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
from backend.app.ingestion.sec_client import SECEdgarClient, SECFilingInfo

# Configure terminal logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_sec_download")


async def run_sec_download_test(
    ticker: str = "AAPL",
    fiscal_year: int = 2023,
    overwrite: bool = False,
) -> bool:
    """Execute end-to-end SEC filing download and verification."""
    print("=" * 70)
    print("SUB-PHASE 2.2: SEC EDGAR DOCUMENT SOURCING VERIFICATION")
    print("=" * 70)

    print(f"\n[CONFIG] Target Ticker: {ticker}")
    print(f"[CONFIG] Target Fiscal Year: {fiscal_year}")
    print(f"[CONFIG] User-Agent: {settings.SEC_EDGAR_USER_AGENT}")
    print(f"[CONFIG] Rate Limit: {settings.SEC_EDGAR_RATE_LIMIT_RPS} requests/sec")
    print(f"[CONFIG] Data Directory: {settings.DATA_DIR}")

    # Validate User-Agent format
    ua = settings.SEC_EDGAR_USER_AGENT.strip()
    if not ua or "@" not in ua or len(ua.split()) < 2:
        print("\n[WARN] SEC_EDGAR_USER_AGENT does not match 'AppName ContactEmail' recommendation.")
        print(f"       Current value: '{ua}'")
        print("       Recommended format: 'FinancialCRAG admin@yourdomain.com'")

    start_time = time.time()

    try:
        async with SECEdgarClient() as client:
            # 1. Test Ticker Resolution
            print(f"\n[TEST 1] Resolving Ticker '{ticker}' to SEC CIK...")
            padded_cik, company_name = await client.resolve_ticker_to_cik(ticker)
            print(f"  -> Company: {company_name}")
            print(f"  -> CIK: {padded_cik} (Length: {len(padded_cik)} digits)")
            assert len(padded_cik) == 10, "CIK must be zero-padded to 10 digits"
            print("[PASS] Ticker-to-CIK resolution successful.")

            # 2. Test Submissions Metadata Fetching
            print(f"\n[TEST 2] Fetching 10-K metadata for {ticker} (FY {fiscal_year})...")
            filing_info = await client.get_filing_metadata(
                ticker=ticker,
                form_type="10-K",
                fiscal_year=fiscal_year,
            )
            print(f"  -> Form: {filing_info.form_type}")
            print(f"  -> Accession Number: {filing_info.accession_number}")
            print(f"  -> Filing Date: {filing_info.filing_date}")
            if filing_info.report_date:
                print(f"  -> Report Date: {filing_info.report_date}")
            print(f"  -> Primary Document: {filing_info.primary_doc_name}")
            print(f"  -> Document URL: {filing_info.document_url}")
            assert filing_info.form_type == "10-K"
            assert filing_info.accession_number
            assert filing_info.primary_doc_name
            print("[PASS] Filing metadata retrieval verified.")

            # 3. Test Primary Document Download & Storage
            print(f"\n[TEST 3] Downloading filing document to local disk...")
            downloaded_info = await client.download_filing(
                ticker=ticker,
                form_type="10-K",
                fiscal_year=fiscal_year,
                overwrite=overwrite,
            )
            assert downloaded_info.local_file_path is not None
            assert downloaded_info.local_file_path.exists()
            assert downloaded_info.file_size_bytes is not None and downloaded_info.file_size_bytes > 0

            print(f"  -> Saved Path: {downloaded_info.local_file_path}")
            print(f"  -> File Size: {downloaded_info.file_size_bytes:,} bytes ({downloaded_info.file_size_bytes / 1024 / 1024:.2f} MB)")
            print("[PASS] File successfully persisted to disk.")

            # 4. Content Verification Check
            print("\n[TEST 4] Verifying file content integrity...")
            content_preview = downloaded_info.local_file_path.read_text(encoding="utf-8", errors="ignore")[:500]
            assert len(content_preview) > 50
            is_html = "<html" in content_preview.lower() or "<!doctype" in content_preview.lower() or "<xml" in content_preview.lower()
            print(f"  -> Document Format: {'HTML/XML Document' if is_html else 'Text/Binary'}")
            print("[PASS] Content integrity verified.")

            # 5. Local Cache Verification (Idempotent Fast-Path)
            print("\n[TEST 5] Verifying local cache skip (idempotency)...")
            cache_start = time.time()
            cached_info = await client.download_filing(
                ticker=ticker,
                form_type="10-K",
                fiscal_year=fiscal_year,
                overwrite=False,
            )
            cache_duration = time.time() - cache_start
            assert cached_info.local_file_path == downloaded_info.local_file_path
            print(f"  -> Second call resolved in {cache_duration:.4f}s from local cache.")
            print("[PASS] Local cache fast-path verified.")

    except Exception as e:
        print(f"\n[FAIL] SEC download verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"[ALL PASS] SUB-PHASE 2.2 SEC EDGAR SOURCING VERIFIED! (Total time: {elapsed:.2f}s)")
    print("=" * 70)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify SEC EDGAR 10-K download pipeline.")
    parser.add_argument("--ticker", type=str, default="AAPL", help="Stock ticker symbol (default: AAPL)")
    parser.add_argument("--year", type=int, default=2023, help="Fiscal year (default: 2023)")
    parser.add_argument("--overwrite", action="store_true", help="Force re-download even if cached")

    args = parser.parse_args()
    success = asyncio.run(
        run_sec_download_test(
            ticker=args.ticker,
            fiscal_year=args.year,
            overwrite=args.overwrite,
        )
    )
    sys.exit(0 if success else 1)
