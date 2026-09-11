"""Pydantic schemas for SEC document chunks and vector embeddings."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChunkBase(BaseModel):
    """Base attributes for an SEC document chunk."""

    filing_id: UUID = Field(..., description="Foreign key to parent sec_filings.id")
    chunk_index: int = Field(..., ge=0, description="Sequential 0-indexed position within filing")
    section_title: str | None = Field(default=None, max_length=500, description="Section heading")
    content: str = Field(..., min_length=1, description="Raw chunk text content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Structured chunk metadata")
    token_count: int | None = Field(default=None, ge=0, description="Approximate token length")


class ChunkCreate(ChunkBase):
    """Payload for creating and inserting a new document chunk with embedding."""

    embedding: list[float] = Field(
        ...,
        description="Dense 384-dimensional vector embedding from BAAI/bge-small-en-v1.5",
    )

    @field_validator("embedding", mode="before")
    @classmethod
    def parse_pgvector_string(cls, v: Any) -> Any:
        """Parse string/JSON representation of pgvector if provided as a string."""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    return [float(x.strip()) for x in v[1:-1].split(",") if x.strip()]
        return v

    @field_validator("embedding")
    @classmethod
    def validate_embedding_dimension(cls, v: list[float]) -> list[float]:
        """Strictly enforce the 384-dimensional requirement of BAAI/bge-small-en-v1.5."""
        if len(v) != 384:
            raise ValueError(
                f"Embedding dimension mismatch: expected 384 dimensions, got {len(v)}"
            )
        return v


class ChunkInDB(ChunkBase):
    """SEC document chunk stored in Supabase PostgreSQL."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique chunk UUID")
    embedding: list[float] = Field(..., description="384-dimensional vector embedding")
    created_at: datetime = Field(..., description="Chunk creation timestamp")

    @field_validator("embedding", mode="before")
    @classmethod
    def parse_pgvector_string(cls, v: Any) -> Any:
        """Parse string representation of pgvector returned by Supabase PostgREST."""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    return [float(x.strip()) for x in v[1:-1].split(",") if x.strip()]
        return v

    @field_validator("embedding")
    @classmethod
    def validate_embedding_dimension(cls, v: list[float]) -> list[float]:
        """Strictly enforce the 384-dimensional requirement of BAAI/bge-small-en-v1.5."""
        if len(v) != 384:
            raise ValueError(
                f"Embedding dimension mismatch: expected 384 dimensions, got {len(v)}"
            )
        return v


class ChunkResponse(ChunkBase):
    """Public chunk representation (excludes dense vector to preserve bandwidth)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique chunk UUID")
    created_at: datetime = Field(..., description="Chunk creation timestamp")


class ChunkSearchResult(BaseModel):
    """Result model returned by the match_sec_chunks vector similarity search RPC."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Chunk UUID")
    filing_id: UUID = Field(..., description="Parent filing UUID")
    ticker: str = Field(..., description="Company stock ticker")
    company_name: str = Field(..., description="Company name")
    fiscal_year: int = Field(..., description="Fiscal year")
    chunk_index: int = Field(..., description="Sequential chunk index")
    section_title: str | None = Field(default=None, description="Section heading")
    content: str = Field(..., description="Retrieved chunk content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")
    similarity: float = Field(..., ge=-1.0, le=1.0, description="Cosine similarity score")


class ChunkSearchQuery(BaseModel):
    """Input payload for vector similarity search."""

    query_embedding: list[float] = Field(
        ...,
        description="Dense 384-dimensional query vector embedding",
    )
    match_threshold: float = Field(default=0.0, ge=-1.0, le=1.0, description="Minimum similarity cutoff")
    match_count: int = Field(default=10, ge=1, le=100, description="Maximum chunks to retrieve")
    filter_ticker: str | None = Field(default=None, max_length=20, description="Filter by stock ticker")
    filter_fiscal_year: int | None = Field(default=None, ge=1900, le=2100, description="Filter by fiscal year")

    @field_validator("query_embedding")
    @classmethod
    def validate_query_embedding_dimension(cls, v: list[float]) -> list[float]:
        """Strictly enforce the 384-dimensional requirement of BAAI/bge-small-en-v1.5."""
        if len(v) != 384:
            raise ValueError(
                f"Query embedding dimension mismatch: expected 384 dimensions, got {len(v)}"
            )
        return v

    @field_validator("filter_ticker")
    @classmethod
    def normalize_filter_ticker(cls, v: str | None) -> str | None:
        if v is not None:
            return v.strip().upper()
        return None
