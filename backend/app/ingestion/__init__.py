"""Data Ingestion Pipeline for SEC 10-K filings."""
from backend.app.ingestion.chunker import FinancialDocumentChunker, chunker
from backend.app.ingestion.embedder import DocumentEmbedder, embedder
from backend.app.ingestion.parser import SECDocumentParser
from backend.app.ingestion.sec_client import SECEdgarClient, SECFilingInfo

__all__ = [
    "SECEdgarClient",
    "SECFilingInfo",
    "SECDocumentParser",
    "FinancialDocumentChunker",
    "chunker",
    "DocumentEmbedder",
    "embedder",
]
