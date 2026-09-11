"""Asynchronous SEC EDGAR Client for 10-K document sourcing.

Strictly complies with SEC fair-access policies:
- User-Agent header in required format: AppName ContactEmail
- Rate limiting via asyncio.Semaphore (default <= 8 requests/sec)
- Exponential backoff retry logic for 429 and 5xx responses
"""
import asyncio
import logging
import random
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional
import httpx
from pydantic import BaseModel, Field

from backend.app.core.config import settings

logger = logging.getLogger("sec_client")


class SECFilingInfo(BaseModel):
    """Metadata describing a retrieved SEC filing document."""

    ticker: str = Field(..., description="Uppercase stock ticker symbol")
    company_name: str = Field(..., description="Official corporate name reported to SEC")
    cik: str = Field(..., description="Zero-padded 10-digit Central Index Key")
    form_type: str = Field(default="10-K", description="SEC filing form type")
    fiscal_year: int = Field(..., description="Fiscal year reported")
    accession_number: str = Field(..., description="SEC unique accession number")
    filing_date: date = Field(..., description="Filing submission date")
    report_date: Optional[date] = Field(default=None, description="End of fiscal period date")
    primary_doc_name: str = Field(..., description="Filename of primary 10-K document")
    document_url: str = Field(..., description="Full EDGAR archive download URL")
    local_file_path: Optional[Path] = Field(default=None, description="Path on local disk if downloaded")
    file_size_bytes: Optional[int] = Field(default=None, description="Size of downloaded file in bytes")


class SECEdgarClient:
    """Async client for querying SEC EDGAR and downloading company 10-K reports."""

    def __init__(
        self,
        user_agent: Optional[str] = None,
        base_url: Optional[str] = None,
        rate_limit_rps: Optional[int] = None,
        data_dir: Optional[Path | str] = None,
        max_retries: int = 3,
    ) -> None:
        self.user_agent = user_agent or settings.SEC_EDGAR_USER_AGENT
        self.base_url = (base_url or settings.SEC_EDGAR_BASE_URL).rstrip("/")
        self.rate_limit_rps = rate_limit_rps or settings.SEC_EDGAR_RATE_LIMIT_RPS
        self.data_dir = Path(data_dir or settings.DATA_DIR)
        self.max_retries = max_retries

        # Rate-limiting primitives
        self._semaphore = asyncio.Semaphore(self.rate_limit_rps)
        self._min_interval = 1.0 / self.rate_limit_rps
        self._last_request_time = 0.0
        self._lock = asyncio.Lock()

        # In-memory cached ticker -> CIK mapping
        self._ticker_cache: dict[str, tuple[str, str]] = {}
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "SECEdgarClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def connect(self) -> None:
        """Initialize the underlying HTTP client session."""
        if self._client is None or self._client.is_closed:
            headers = {
                "User-Agent": self.user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Accept": "application/json, text/html, */*",
            }
            self._client = httpx.AsyncClient(
                headers=headers,
                timeout=httpx.Timeout(45.0, connect=15.0),
                follow_redirects=True,
            )

    async def close(self) -> None:
        """Close the underlying HTTP client session."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            raise RuntimeError("SECEdgarClient is not connected. Use 'async with SECEdgarClient()' or call .connect()")
        return self._client

    async def _rate_limit_throttle(self) -> None:
        """Ensure requests do not exceed fair access rate limits."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                sleep_time = self._min_interval - elapsed
                await asyncio.sleep(sleep_time)
            self._last_request_time = time.monotonic()

    async def _request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Execute an HTTP request with rate-limiting, exponential backoff, and jitter."""
        base_delay = 1.0

        for attempt in range(1, self.max_retries + 1):
            async with self._semaphore:
                await self._rate_limit_throttle()
                try:
                    response = await self.client.request(method, url, **kwargs)
                    
                    if response.status_code == 403:
                        logger.error(
                            "SEC returned 403 Forbidden for URL: %s. "
                            "Ensure SEC_EDGAR_USER_AGENT is set to 'AppName ContactEmail'. Current: '%s'",
                            url,
                            self.user_agent,
                        )
                        response.raise_for_status()

                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt == self.max_retries:
                            response.raise_for_status()
                        backoff = (base_delay * (2 ** (attempt - 1))) + random.uniform(0.1, 0.5)
                        logger.warning(
                            "SEC returned HTTP %d for %s. Retrying attempt %d/%d after %.2fs backoff",
                            response.status_code,
                            url,
                            attempt,
                            self.max_retries,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        continue

                    response.raise_for_status()
                    return response

                except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                    if attempt == self.max_retries:
                        raise
                    backoff = (base_delay * (2 ** (attempt - 1))) + random.uniform(0.1, 0.5)
                    logger.warning(
                        "Network error (%s) contacting %s. Retrying attempt %d/%d after %.2fs",
                        exc.__class__.__name__,
                        url,
                        attempt,
                        self.max_retries,
                        backoff,
                    )
                    await asyncio.sleep(backoff)

        raise RuntimeError(f"Exceeded max retries ({self.max_retries}) for URL: {url}")

    async def resolve_ticker_to_cik(self, ticker: str) -> tuple[str, str]:
        """Map stock ticker symbol to zero-padded 10-digit CIK and company name."""
        ticker_clean = ticker.strip().upper()

        if ticker_clean in self._ticker_cache:
            return self._ticker_cache[ticker_clean]

        logger.info("Fetching SEC company ticker mapping registry...")
        url = "https://www.sec.gov/files/company_tickers.json"
        response = await self._request_with_retry("GET", url)
        data: dict[str, dict[str, Any]] = response.json()

        for entry in data.values():
            entry_ticker = str(entry.get("ticker", "")).strip().upper()
            cik_int = entry.get("cik_str")
            title = str(entry.get("title", ""))
            if entry_ticker and cik_int is not None:
                padded = str(cik_int).zfill(10)
                self._ticker_cache[entry_ticker] = (padded, title)

        if ticker_clean not in self._ticker_cache:
            raise ValueError(f"Ticker symbol '{ticker_clean}' not found in SEC EDGAR registry.")

        return self._ticker_cache[ticker_clean]

    async def get_filing_metadata(
        self,
        ticker: str,
        form_type: str = "10-K",
        fiscal_year: Optional[int] = None,
    ) -> SECFilingInfo:
        """Find the matching 10-K filing metadata for a given company and fiscal year."""
        ticker_clean = ticker.strip().upper()
        padded_cik, company_name = await self.resolve_ticker_to_cik(ticker_clean)

        submissions_url = f"{self.base_url}/submissions/CIK{padded_cik}.json"
        logger.info("Fetching submissions for %s (CIK: %s)...", ticker_clean, padded_cik)
        response = await self._request_with_retry("GET", submissions_url)
        data = response.json()

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        filing_dates = recent.get("filingDate", [])
        report_dates = recent.get("reportDate", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])

        if not forms:
            raise RuntimeError(f"No filings found in SEC submissions for {ticker_clean} (CIK: {padded_cik})")

        matched_index: Optional[int] = None

        for idx, form in enumerate(forms):
            if form != form_type:
                continue

            f_date_str = filing_dates[idx] if idx < len(filing_dates) else ""
            r_date_str = report_dates[idx] if idx < len(report_dates) else ""

            if fiscal_year is not None:
                # Match fiscal_year against report date first (accurate for fiscal year-end), then filing date
                target_year = str(fiscal_year)
                if r_date_str.startswith(target_year) or f_date_str.startswith(target_year):
                    matched_index = idx
                    break
            else:
                # If no fiscal year specified, pick the most recent 10-K
                matched_index = idx
                break

        if matched_index is None:
            year_msg = f" for fiscal year {fiscal_year}" if fiscal_year else ""
            raise ValueError(f"No {form_type} filing found for {ticker_clean}{year_msg}.")

        accession = accessions[matched_index]
        primary_doc = primary_docs[matched_index]
        filing_date_obj = datetime.strptime(filing_dates[matched_index], "%Y-%m-%d").date()
        report_date_obj = (
            datetime.strptime(report_dates[matched_index], "%Y-%m-%d").date()
            if matched_index < len(report_dates) and report_dates[matched_index]
            else None
        )

        resolved_year = fiscal_year or (report_date_obj.year if report_date_obj else filing_date_obj.year)

        # Build EDGAR archive URL
        # URL pattern: https://www.sec.gov/Archives/edgar/data/{cik_no_padding}/{accession_no_hyphens}/{primary_doc}
        cik_unpadded = str(int(padded_cik))
        accession_no_hyphens = accession.replace("-", "")
        document_url = f"https://www.sec.gov/Archives/edgar/data/{cik_unpadded}/{accession_no_hyphens}/{primary_doc}"

        return SECFilingInfo(
            ticker=ticker_clean,
            company_name=company_name,
            cik=padded_cik,
            form_type=form_type,
            fiscal_year=resolved_year,
            accession_number=accession,
            filing_date=filing_date_obj,
            report_date=report_date_obj,
            primary_doc_name=primary_doc,
            document_url=document_url,
        )

    async def download_filing(
        self,
        ticker: str,
        form_type: str = "10-K",
        fiscal_year: Optional[int] = None,
        overwrite: bool = False,
    ) -> SECFilingInfo:
        """Retrieve metadata, download the primary 10-K filing document, and save to DATA_DIR."""
        filing_info = await self.get_filing_metadata(
            ticker=ticker, form_type=form_type, fiscal_year=fiscal_year
        )

        # Local target directory structure: DATA_DIR/{ticker}/{accession_number}/
        target_dir = self.data_dir / filing_info.ticker / filing_info.accession_number
        target_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_dir / filing_info.primary_doc_name

        if target_file.exists() and not overwrite:
            size = target_file.stat().st_size
            if size > 0:
                logger.info(
                    "Filing document already cached locally at %s (%d bytes). Skipping download.",
                    target_file,
                    size,
                )
                filing_info.local_file_path = target_file
                filing_info.file_size_bytes = size
                return filing_info

        logger.info(
            "Downloading %s %s (%d) from %s ...",
            filing_info.ticker,
            filing_info.form_type,
            filing_info.fiscal_year,
            filing_info.document_url,
        )

        response = await self._request_with_retry("GET", filing_info.document_url)
        content_bytes = response.content

        target_file.write_bytes(content_bytes)
        file_size = len(content_bytes)

        logger.info(
            "Successfully downloaded and saved filing to %s (%d bytes).",
            target_file,
            file_size,
        )

        filing_info.local_file_path = target_file
        filing_info.file_size_bytes = file_size
        return filing_info
