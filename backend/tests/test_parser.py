"""Unit tests for SECDocumentParser."""
from pathlib import Path
import pytest

from backend.app.ingestion.parser import DEFAULT_SEC_PARSING_INSTRUCTION, SECDocumentParser


def test_get_cache_path(tmp_path: Path):
    """Verify that get_cache_path derives {filing_dir}/parsed.md correctly."""
    filing_doc = tmp_path / "AAPL" / "0000320193-23-000106" / "aapl-20230930.htm"
    cache_path = SECDocumentParser.get_cache_path(filing_doc)
    assert cache_path == filing_doc.parent / "parsed.md"


def test_missing_api_key_raises_value_error(tmp_path: Path):
    """Verify ValueError is raised when parsing without an API key and no cache."""
    dummy_file = tmp_path / "filing.htm"
    dummy_file.write_text("<html>Dummy SEC Report</html>", encoding="utf-8")

    parser = SECDocumentParser(api_key="")
    with pytest.raises(ValueError, match="LLAMA_CLOUD_API_KEY is not configured"):
        parser.parse_file(dummy_file)


def test_cache_read_bypasses_api(tmp_path: Path):
    """Verify that when parsed.md exists, parse_file returns cache without calling API."""
    filing_dir = tmp_path / "filing_dir"
    filing_dir.mkdir()
    doc_file = filing_dir / "filing.htm"
    doc_file.write_text("<html>Original HTML</html>", encoding="utf-8")

    cache_file = filing_dir / "parsed.md"
    cached_markdown = "# Item 8. Financial Statements\n\n| Year | Revenue |\n|---|---|\n| 2023 | $383B |"
    cache_file.write_text(cached_markdown, encoding="utf-8")

    # Parser with no API key should succeed because cache exists
    parser = SECDocumentParser(api_key="")
    result = parser.parse_file(doc_file, overwrite=False)

    assert result == cached_markdown


def test_default_parsing_instruction():
    """Verify default parsing instruction contains critical table and heading directives."""
    instruction = DEFAULT_SEC_PARSING_INSTRUCTION
    assert "pipe-tables" in instruction
    assert "Balance Sheets" in instruction
    assert "Item 8" in instruction
