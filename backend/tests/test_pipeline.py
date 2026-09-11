"""Unit tests for the IngestionPipeline coordinator and lifecycle state machine."""
import datetime
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.ingestion.pipeline import IngestionPipeline
from backend.app.ingestion.sec_client import SECFilingInfo
from backend.app.models.chunk import ChunkCreate, ChunkInDB
from backend.app.models.filing import FilingCreate, FilingInDB, IngestionStatus


@pytest.fixture
def mock_filing_info():
    return SECFilingInfo(
        ticker="AAPL",
        company_name="Apple Inc.",
        cik="0000320193",
        form_type="10-K",
        fiscal_year=2023,
        accession_number="0000320193-23-000106",
        filing_date=datetime.date(2023, 11, 3),
        primary_doc_name="aapl-20230930.htm",
        document_url="https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm",
        local_file_path=Path("data/filings/AAPL/0000320193-23-000106/aapl-20230930.htm"),
    )


@pytest.fixture
def mock_filing_db():
    now = datetime.datetime.now(datetime.timezone.utc)
    return FilingInDB(
        id=uuid.uuid4(),
        ticker="AAPL",
        company_name="Apple Inc.",
        form_type="10-K",
        fiscal_year=2023,
        fiscal_period="FY",
        accession_number="0000320193-23-000106",
        filing_date=datetime.date(2023, 11, 3),
        source_url="https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm",
        parse_status=IngestionStatus.PENDING,
        total_chunks=0,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_pipeline_idempotency_skip_existing(mock_filing_info, mock_filing_db):
    """When a filing is already COMPLETE, the pipeline should return existing records without re-processing."""
    completed_filing = mock_filing_db.model_copy(
        update={"parse_status": IngestionStatus.COMPLETE, "total_chunks": 10}
    )

    mock_sec = MagicMock()
    mock_sec.__aenter__.return_value = mock_sec
    mock_sec.__aexit__.return_value = None
    mock_sec.download_filing = AsyncMock(return_value=mock_filing_info)

    mock_filing_repo = MagicMock()
    mock_filing_repo.get_by_accession.return_value = completed_filing

    mock_chunk_repo = MagicMock()
    mock_chunk_repo.get_chunks_by_filing.return_value = ["dummy_chunk"] * 10

    mock_parser = MagicMock()
    mock_chunker = MagicMock()
    mock_embedder = MagicMock()

    with patch.object(Path, "exists", return_value=True):
        pipeline = IngestionPipeline(
            sec_client=mock_sec,
            parser=mock_parser,
            chunker=mock_chunker,
            embedder=mock_embedder,
            filing_repo=mock_filing_repo,
            chunk_repo=mock_chunk_repo,
        )

        filing, chunks = await pipeline.ingest_filing(ticker="AAPL", fiscal_year=2023)

    assert filing.parse_status == IngestionStatus.COMPLETE
    assert len(chunks) == 10
    mock_parser.aparse_file.assert_not_called()
    mock_chunker.chunk_document.assert_not_called()
    mock_embedder.embed_chunks.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_full_execution_flow(mock_filing_info, mock_filing_db):
    """Test standard end-to-end execution of the ingestion pipeline."""
    mock_sec = MagicMock()
    mock_sec.__aenter__.return_value = mock_sec
    mock_sec.__aexit__.return_value = None
    mock_sec.download_filing = AsyncMock(return_value=mock_filing_info)

    status_transitions = []

    mock_filing_repo = MagicMock()
    mock_filing_repo.get_by_accession.return_value = None
    mock_filing_repo.create_filing.return_value = mock_filing_db

    def record_status(filing_id, status, total_chunks=None):
        status_transitions.append(status)
        return mock_filing_db.model_copy(
            update={"parse_status": status, "total_chunks": total_chunks or 0}
        )

    mock_filing_repo.update_status.side_effect = record_status

    mock_parser = MagicMock()
    mock_parser.aparse_file = AsyncMock(return_value="# Item 8\n\n| Sales | 383285 |")

    raw_chunk = ChunkCreate(
        filing_id=mock_filing_db.id,
        chunk_index=0,
        content="| Sales | 383285 |",
    )
    mock_chunker = MagicMock()
    mock_chunker.chunk_document.return_value = [raw_chunk]

    embedded_chunk = raw_chunk.model_copy(update={"embedding": [0.1] * 384})
    mock_embedder = MagicMock()
    mock_embedder.embed_chunks.return_value = [embedded_chunk]

    now = datetime.datetime.now(datetime.timezone.utc)
    chunk_in_db = ChunkInDB(
        id=uuid.uuid4(),
        filing_id=mock_filing_db.id,
        chunk_index=0,
        content="| Sales | 383285 |",
        embedding=[0.1] * 384,
        created_at=now,
    )
    mock_chunk_repo = MagicMock()
    mock_chunk_repo.bulk_insert_chunks.return_value = [chunk_in_db]

    with patch.object(Path, "exists", return_value=True):
        pipeline = IngestionPipeline(
            sec_client=mock_sec,
            parser=mock_parser,
            chunker=mock_chunker,
            embedder=mock_embedder,
            filing_repo=mock_filing_repo,
            chunk_repo=mock_chunk_repo,
        )

        filing, chunks = await pipeline.ingest_filing(ticker="AAPL", fiscal_year=2023)

    assert filing.parse_status == IngestionStatus.COMPLETE
    assert len(chunks) == 1
    assert status_transitions == [
        IngestionStatus.PARSING,
        IngestionStatus.PARSED,
        IngestionStatus.CHUNKED,
        IngestionStatus.EMBEDDED,
        IngestionStatus.COMPLETE,
    ]


@pytest.mark.asyncio
async def test_pipeline_failure_handling(mock_filing_info, mock_filing_db):
    """When a stage raises an error, the filing status must be updated to FAILED."""
    mock_sec = MagicMock()
    mock_sec.__aenter__.return_value = mock_sec
    mock_sec.__aexit__.return_value = None
    mock_sec.download_filing = AsyncMock(return_value=mock_filing_info)

    mock_filing_repo = MagicMock()
    mock_filing_repo.get_by_accession.return_value = None
    mock_filing_repo.create_filing.return_value = mock_filing_db

    mock_parser = MagicMock()
    mock_parser.aparse_file = AsyncMock(side_effect=RuntimeError("LlamaParse timeout"))

    with patch.object(Path, "exists", return_value=True):
        pipeline = IngestionPipeline(
            sec_client=mock_sec,
            parser=mock_parser,
            filing_repo=mock_filing_repo,
        )

        with pytest.raises(RuntimeError, match="LlamaParse timeout"):
            await pipeline.ingest_filing(ticker="AAPL", fiscal_year=2023)

    mock_filing_repo.update_status.assert_called_with(
        mock_filing_db.id, IngestionStatus.FAILED
    )
