"""Unit and integration tests for SEC EDGAR client."""
from pathlib import Path
import pytest

from backend.app.ingestion.sec_client import SECEdgarClient, SECFilingInfo


@pytest.mark.asyncio
async def test_resolve_ticker_to_cik():
    """Verify that ticker symbols resolve to zero-padded 10-digit CIK codes."""
    async with SECEdgarClient() as client:
        padded_cik, company_name = await client.resolve_ticker_to_cik("AAPL")
        assert padded_cik == "0000320193"
        assert "Apple" in company_name

        # Verify caching works by checking internal dict
        assert "AAPL" in client._ticker_cache


@pytest.mark.asyncio
async def test_invalid_ticker_raises_error():
    """Verify that nonexistent ticker symbols raise ValueError."""
    async with SECEdgarClient() as client:
        with pytest.raises(ValueError, match="not found in SEC EDGAR registry"):
            await client.resolve_ticker_to_cik("NONEXISTENT_XYZ_1234")


@pytest.mark.asyncio
async def test_get_filing_metadata_aapl():
    """Verify metadata extraction for Apple FY 2023 10-K."""
    async with SECEdgarClient() as client:
        filing_info = await client.get_filing_metadata(ticker="AAPL", form_type="10-K", fiscal_year=2023)
        assert isinstance(filing_info, SECFilingInfo)
        assert filing_info.ticker == "AAPL"
        assert filing_info.form_type == "10-K"
        assert filing_info.fiscal_year == 2023
        assert filing_info.accession_number.startswith("0000320193")
        assert filing_info.document_url.startswith("https://www.sec.gov/Archives/edgar/data/")
