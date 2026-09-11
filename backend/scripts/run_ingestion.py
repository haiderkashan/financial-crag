"""CLI runner for ingesting SEC 10-K filings into Financial CRAG vector database.

Usage:
    python backend/scripts/run_ingestion.py --ticker AAPL --year 2023
    python backend/scripts/run_ingestion.py --ticker AAPL --year 2023 --force
"""
import argparse
import asyncio
import logging
import sys
import time

# Ensure proper encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.app.ingestion.pipeline import pipeline


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


async def run(ticker: str, year: int, form: str, force: bool):
    print("=" * 70)
    print(f" FINANCIAL CRAG : SEC {form} INGESTION PIPELINE")
    print("=" * 70)
    print(f" Ticker       : {ticker.upper()}")
    print(f" Fiscal Year  : {year}")
    print(f" Form Type    : {form}")
    print(f" Force Re-run : {force}")
    print("-" * 70)

    start_time = time.perf_counter()
    try:
        filing, chunks = await pipeline.ingest_filing(
            ticker=ticker,
            fiscal_year=year,
            form_type=form,
            force_reingest=force,
        )
        elapsed = time.perf_counter() - start_time

        print("-" * 70)
        print(" [OK] INGESTION SUCCESSFUL")
        print(f" Filing ID         : {filing.id}")
        print(f" Accession Number  : {filing.accession_number}")
        print(f" Company           : {filing.company_name}")
        print(f" Status            : {filing.parse_status.value.upper()}")
        print(f" Chunks Persisted  : {len(chunks)}")
        print(f" Total Elapsed Time: {elapsed:.2f}s")
        print("=" * 70)
        return 0

    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        print("-" * 70, file=sys.stderr)
        print(f" [ERROR] INGESTION FAILED after {elapsed:.2f}s: {exc}", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        return 1


def main():
    setup_logging()
    parser = argparse.ArgumentParser(
        description="Ingest SEC 10-K annual report into Supabase pgvector.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--ticker",
        type=str,
        required=True,
        help="Stock ticker symbol (e.g. AAPL, MSFT, NVDA)",
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="Fiscal year of filing (e.g. 2023)",
    )
    parser.add_argument(
        "--form",
        type=str,
        default="10-K",
        help="SEC Form type (default: 10-K)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force re-parsing and re-embedding, purging prior chunks in DB",
    )

    args = parser.parse_args()
    code = asyncio.run(
        run(
            ticker=args.ticker,
            year=args.year,
            form=args.form,
            force=args.force,
        )
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
