"""Pydantic schemas for SEC Filings registry."""
from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IngestionStatus(str, Enum):
    """Lifecycle statuses for SEC filing ingestion pipeline."""

    PENDING = "pending"
    PARSING = "parsing"
    PARSED = "parsed"
    CHUNKED = "chunked"
    EMBEDDED = "embedded"
    COMPLETE = "complete"
    FAILED = "failed"


class FilingBase(BaseModel):
    """Base attributes for an SEC filing."""

    ticker: str = Field(..., max_length=10, description="Stock ticker symbol (e.g. AAPL)")
    company_name: str = Field(..., max_length=255, description="Legal company name")
    form_type: str = Field(default="10-K", max_length=20, description="SEC filing form type")
    fiscal_year: int = Field(..., ge=1900, le=2100, description="Fiscal year of report")
    fiscal_period: str = Field(default="FY", max_length=10, description="Fiscal period (e.g. FY, Q1)")
    accession_number: str = Field(..., max_length=30, description="SEC unique accession number")
    filing_date: date | None = Field(default=None, description="Filing submission date")
    source_url: str | None = Field(default=None, description="SEC EDGAR document source URL")

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, v: str) -> str:
        """Ensure ticker is uppercase and stripped of whitespace."""
        return v.strip().upper()


class FilingCreate(FilingBase):
    """Payload for creating a new SEC filing registry entry."""

    parse_status: IngestionStatus = Field(
        default=IngestionStatus.PENDING,
        description="Initial status of the ingestion pipeline",
    )
    total_chunks: int = Field(default=0, ge=0, description="Total chunks extracted from filing")


class FilingUpdate(BaseModel):
    """Payload for updating an existing SEC filing entry."""

    parse_status: IngestionStatus | None = None
    total_chunks: int | None = Field(default=None, ge=0)
    source_url: str | None = None
    filing_date: date | None = None


class FilingInDB(FilingBase):
    """SEC filing database model representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique filing UUID")
    parse_status: IngestionStatus = Field(..., description="Current status of ingestion")
    total_chunks: int = Field(..., ge=0, description="Total chunks persisted")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last update timestamp")


class FilingResponse(FilingInDB):
    """Public API response model for SEC filing records."""

    pass
