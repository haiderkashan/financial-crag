"""Data Ingestion Pipeline for SEC 10-K filings."""
from backend.app.ingestion.sec_client import SECEdgarClient, SECFilingInfo

__all__ = ["SECEdgarClient", "SECFilingInfo"]
