"""Orchestrator pipeline executing the end-to-end SEC 10-K ingestion workflow:
Sourcing -> LlamaParse -> Structure-Aware Chunking -> Dense Embedding -> Supabase Vector Upsertion.
"""
import logging
from typing import Optional

from backend.app.db.repositories.chunk_repo import ChunkRepository, chunk_repo as default_chunk_repo
from backend.app.db.repositories.filing_repo import FilingRepository, filing_repo as default_filing_repo
from backend.app.ingestion.chunker import FinancialDocumentChunker, chunker as default_chunker
from backend.app.ingestion.embedder import DocumentEmbedder, embedder as default_embedder
from backend.app.ingestion.parser import SECDocumentParser
from backend.app.ingestion.sec_client import SECEdgarClient
from backend.app.models.chunk import ChunkInDB
from backend.app.models.filing import FilingCreate, FilingInDB, IngestionStatus

logger = logging.getLogger("ingestion_pipeline")


class IngestionPipeline:
    """Async coordinator orchestrating the 5-stage SEC 10-K ingestion pipeline."""

    def __init__(
        self,
        sec_client: Optional[SECEdgarClient] = None,
        parser: Optional[SECDocumentParser] = None,
        chunker: Optional[FinancialDocumentChunker] = None,
        embedder: Optional[DocumentEmbedder] = None,
        filing_repo: Optional[FilingRepository] = None,
        chunk_repo: Optional[ChunkRepository] = None,
    ) -> None:
        self.sec_client = sec_client or SECEdgarClient()
        self.parser = parser or SECDocumentParser()
        self.chunker = chunker or default_chunker
        self.embedder = embedder or default_embedder
        self.filing_repo = filing_repo or default_filing_repo
        self.chunk_repo = chunk_repo or default_chunk_repo

    async def ingest_filing(
        self,
        ticker: str,
        fiscal_year: int,
        form_type: str = "10-K",
        force_reingest: bool = False,
    ) -> tuple[FilingInDB, list[ChunkInDB]]:
        """Execute end-to-end ingestion with lifecycle state tracking and accession idempotency."""
        clean_ticker = ticker.strip().upper()
        logger.info(
            "Starting ingestion pipeline for %s (FY %d, Form: %s, force=%s)...",
            clean_ticker,
            fiscal_year,
            form_type,
            force_reingest,
        )

        # Stage 1: Sourcing & Metadata Discovery via SEC EDGAR
        async with self.sec_client as client:
            filing_info = await client.download_filing(
                ticker=clean_ticker,
                form_type=form_type,
                fiscal_year=fiscal_year,
                overwrite=force_reingest,
            )

        if not filing_info.local_file_path or not filing_info.local_file_path.exists():
            raise FileNotFoundError(
                f"Failed to locate downloaded filing document for {clean_ticker} ({filing_info.accession_number})"
            )

        # Stage 2: Idempotency Check
        existing_filing = self.filing_repo.get_by_accession(filing_info.accession_number)
        filing: FilingInDB

        if existing_filing:
            if existing_filing.parse_status == IngestionStatus.COMPLETE and not force_reingest:
                logger.info(
                    "Filing %s (%s, FY %d) is already complete with %d chunks. Returning existing records.",
                    filing_info.accession_number,
                    clean_ticker,
                    fiscal_year,
                    existing_filing.total_chunks,
                )
                existing_chunks = self.chunk_repo.get_chunks_by_filing(existing_filing.id)
                return existing_filing, existing_chunks

            logger.info(
                "Resetting existing filing record %s for re-ingestion.",
                existing_filing.id,
            )
            # Purge previous chunks
            self.chunk_repo.delete_chunks_by_filing(existing_filing.id)
            updated = self.filing_repo.update_status(
                existing_filing.id, IngestionStatus.PENDING, total_chunks=0
            )
            filing = updated or existing_filing
        else:
            logger.info("Registering new SEC filing in Supabase: %s", filing_info.accession_number)
            filing = self.filing_repo.create_filing(
                FilingCreate(
                    ticker=clean_ticker,
                    company_name=filing_info.company_name,
                    form_type=form_type,
                    fiscal_year=fiscal_year,
                    fiscal_period="FY",
                    accession_number=filing_info.accession_number,
                    filing_date=filing_info.filing_date,
                    source_url=filing_info.document_url,
                    parse_status=IngestionStatus.PENDING,
                    total_chunks=0,
                )
            )

        try:
            # Stage 3: Vision-Aware PDF/HTML Parsing with LlamaParse
            logger.info("Transitioning status to PARSING for filing %s...", filing.id)
            self.filing_repo.update_status(filing.id, IngestionStatus.PARSING)

            markdown_text = await self.parser.aparse_file(
                filing_info.local_file_path, overwrite=force_reingest
            )

            logger.info("Transitioning status to PARSED for filing %s...", filing.id)
            self.filing_repo.update_status(filing.id, IngestionStatus.PARSED)

            # Stage 4: Structure-Aware 3-Stage Chunking
            logger.info("Transitioning status to CHUNKED for filing %s...", filing.id)
            self.filing_repo.update_status(filing.id, IngestionStatus.CHUNKED)

            chunks = self.chunker.chunk_document(
                markdown_text=markdown_text,
                ticker=clean_ticker,
                company_name=filing_info.company_name,
                fiscal_year=fiscal_year,
                filing_id=filing.id,
            )

            if not chunks:
                raise RuntimeError(f"Chunker returned 0 chunks for filing {filing.id}")

            # Stage 5: Dense Vector Embedding (BGE-small-en-v1.5)
            logger.info("Transitioning status to EMBEDDED for filing %s...", filing.id)
            self.filing_repo.update_status(filing.id, IngestionStatus.EMBEDDED)

            embedded_chunks = self.embedder.embed_chunks(chunks)

            # Stage 6: Supabase Bulk Vector Upsertion
            logger.info(
                "Persisting %d embedded chunks into Supabase sec_chunks...",
                len(embedded_chunks),
            )
            inserted_chunks = self.chunk_repo.bulk_insert_chunks(
                embedded_chunks, batch_size=50
            )

            # Stage 7: Finalize Ingestion
            logger.info(
                "Ingestion completed successfully for %s (%d chunks). Transitioning to COMPLETE.",
                clean_ticker,
                len(inserted_chunks),
            )
            final_filing = self.filing_repo.update_status(
                filing.id,
                IngestionStatus.COMPLETE,
                total_chunks=len(inserted_chunks),
            )
            return final_filing or filing, inserted_chunks

        except Exception as exc:
            logger.error(
                "Ingestion pipeline failed for filing %s (%s, %d): %s",
                filing.id,
                clean_ticker,
                fiscal_year,
                exc,
                exc_info=True,
            )
            self.filing_repo.update_status(filing.id, IngestionStatus.FAILED)
            raise


pipeline = IngestionPipeline()
