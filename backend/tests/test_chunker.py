"""Unit tests for FinancialDocumentChunker."""
import pytest
from backend.app.ingestion.chunker import FinancialDocumentChunker
from backend.app.models.chunk import ChunkCreate


def test_chunk_synthetic_document():
    """Verify 3-stage splitting, atomic table preservation, and context prefixing."""
    chunker = FinancialDocumentChunker(chunk_size=200, chunk_overlap=20)

    synthetic_markdown = """
# PART I

## Item 1. Business

Apple designs, manufactures, and markets smartphones, personal computers, tablets, wearables, and accessories.
The Company offers a range of related services including Apple Music, Apple Pay, and iCloud.
Customers include consumers, small and mid-sized businesses, education, enterprise, and government customers worldwide.
Global distribution channels include retail stores, online stores, direct sales force, third-party wholesalers, and retailers.

### Segment Performance

| Operating Segment | 2023 Revenue | 2022 Revenue |
|:---|---:|---:|
| Americas | $162,560 | $169,658 |
| Europe | $94,294 | $95,158 |
| Greater China | $72,559 | $74,200 |
| Rest of Asia Pacific | $29,615 | $29,378 |

Final narrative summary paragraph following the operating segment table.
"""

    chunks = chunker.chunk_document(
        markdown_text=synthetic_markdown,
        ticker="AAPL",
        company_name="Apple Inc.",
        fiscal_year=2023,
    )

    assert len(chunks) >= 3
    assert all(isinstance(c, ChunkCreate) for c in chunks)

    # 1. Verify contextual prefix on all chunks
    for c in chunks:
        assert c.content.startswith("[Document: Apple Inc. 10-K (FY 2023) | Section:")

    # 2. Verify Table Chunk
    table_chunks = [c for c in chunks if c.metadata.get("has_table") is True]
    assert len(table_chunks) == 1
    tbl = table_chunks[0]
    assert "Operating Segment" in tbl.content
    assert "Americas" in tbl.content
    assert "Rest of Asia Pacific" in tbl.content
    # Table must contain its delimiter row intact
    assert "|:---|---:|---:|" in tbl.content


def test_table_never_split_even_if_large():
    """Verify that a table larger than chunk_size is preserved as a single atomic chunk."""
    chunker = FinancialDocumentChunker(chunk_size=100, chunk_overlap=10)

    # Generate a table that exceeds 100 characters
    large_table = "| Metric | FY21 | FY22 | FY23 | FY24 | FY25 |\n|---|---|---|---|---|---|\n"
    for i in range(10):
        large_table += f"| Financial Line Item #{i:02d} | 100 | 200 | 300 | 400 | 500 |\n"

    markdown = f"## Item 8. Financials\n\n{large_table}\n\nSmall note."

    chunks = chunker.chunk_document(
        markdown_text=markdown,
        ticker="NVDA",
        company_name="NVIDIA Corporation",
        fiscal_year=2024,
    )

    table_chunks = [c for c in chunks if c.metadata.get("has_table") is True]
    assert len(table_chunks) == 1
    # Check all 10 rows are in this single chunk
    for i in range(10):
        assert f"Financial Line Item #{i:02d}" in table_chunks[0].content


def test_prose_split_when_exceeding_chunk_size():
    """Verify that prose exceeding chunk_size is divided into multiple sub-chunks."""
    chunker = FinancialDocumentChunker(chunk_size=100, chunk_overlap=20)

    long_prose = "Sentence number one describing market risks in detailed prose. " * 10
    markdown = f"## Item 1A. Risk Factors\n\n{long_prose}"

    chunks = chunker.chunk_document(
        markdown_text=markdown,
        ticker="AAPL",
        company_name="Apple Inc.",
        fiscal_year=2023,
    )

    prose_chunks = [c for c in chunks if c.metadata.get("has_table") is False]
    assert len(prose_chunks) > 1
