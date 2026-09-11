"""Structure-aware chunking engine for SEC 10-K financial filings.

Implements a 3-stage splitting strategy:
1. Stage 1 (Headers): MarkdownHeaderTextSplitter on #, ##, and ### to capture section hierarchy.
2. Stage 2 (Table-Awareness): Strict regex isolation of Markdown pipe-tables (|---|---|),
   treating tables as atomic, indivisible units while applying RecursiveCharacterTextSplitter
   only to prose exceeding 1500 characters.
3. Stage 3 (Metadata & Context Prefixing): Prefixes each chunk with document and section
   context for dense retrieval and packages into ChunkCreate Pydantic models.
"""
import logging
import re
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from backend.app.models.chunk import ChunkCreate

logger = logging.getLogger("sec_chunker")

# Regex to detect complete Markdown pipe-tables (header, delimiter, and rows)
TABLE_REGEX = re.compile(
    r"(?:^[ \t]*\|[^\n]+\|[ \t]*\r?\n)+"
    r"^[ \t]*\|[ \t]*:?[-]+:?[ \t]*(?:\|[ \t]*:?[-]+:?[ \t]*)+\|[ \t]*\r?\n"
    r"(?:^[ \t]*\|[^\n]+\|[ \t]*(?:\r?\n|$))*",
    re.MULTILINE,
)


class FinancialDocumentChunker:
    """Structure-aware chunker designed specifically for parsed SEC 10-K Markdown."""

    def __init__(
        self,
        chunk_size: int = 1500,
        chunk_overlap: int = 200,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Stage 1: Header splitting
        self.headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]
        self.header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self.headers_to_split_on,
            strip_headers=True,
        )

        # Stage 2: Prose splitting
        self.prose_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def _extract_blocks(self, section_text: str) -> list[tuple[bool, str]]:
        """Segment section text into alternating blocks of (is_table: bool, content: str).

        Markdown pipe-tables are extracted atomically; prose between tables is separated.
        """
        blocks: list[tuple[bool, str]] = []
        matches = list(TABLE_REGEX.finditer(section_text))

        if not matches:
            trimmed = section_text.strip()
            if trimmed:
                blocks.append((False, trimmed))
            return blocks

        prev_end = 0
        for m in matches:
            start, end = m.span()
            prose_between = section_text[prev_end:start].strip()
            if prose_between:
                blocks.append((False, prose_between))

            table_block = m.group(0).strip()
            if table_block:
                blocks.append((True, table_block))

            prev_end = end

        trailing_prose = section_text[prev_end:].strip()
        if trailing_prose:
            blocks.append((False, trailing_prose))

        return blocks

    def chunk_document(
        self,
        markdown_text: str,
        ticker: str,
        company_name: str,
        fiscal_year: int,
        filing_id: Optional[UUID] = None,
    ) -> list[ChunkCreate]:
        """Execute the 3-stage chunking pipeline on parsed Markdown content."""
        if not markdown_text.strip():
            logger.warning("Empty markdown text provided to chunk_document.")
            return []

        doc_filing_id = filing_id or uuid4()
        clean_ticker = ticker.strip().upper()

        # Stage 1: Header-based hierarchical splitting
        sections = self.header_splitter.split_text(markdown_text)
        logger.info("Stage 1 complete: Partitioned document into %d header sections.", len(sections))

        chunks: list[ChunkCreate] = []
        chunk_idx = 0

        for section in sections:
            # Build hierarchical section title
            header_parts = [
                section.metadata[h]
                for _, h in self.headers_to_split_on
                if h in section.metadata and section.metadata[h]
            ]
            section_title = " > ".join(header_parts) if header_parts else "General Disclosure"

            # Stage 2: Table-aware block extraction
            raw_blocks = self._extract_blocks(section.page_content)

            for is_table, block_content in raw_blocks:
                if is_table:
                    # ATOMIC TABLE RULE: Never split a table with character text splitters
                    sub_chunks = [block_content]
                else:
                    # Prose text: Split only if exceeding configured chunk_size
                    if len(block_content) > self.chunk_size:
                        sub_chunks = self.prose_splitter.split_text(block_content)
                    else:
                        sub_chunks = [block_content]

                # Stage 3: Metadata enrichment & context prefixing
                for content_piece in sub_chunks:
                    clean_content = content_piece.strip()
                    if not clean_content:
                        continue

                    prefix = (
                        f"[Document: {company_name} 10-K (FY {fiscal_year}) | "
                        f"Section: {section_title}]\n\n"
                    )
                    prefixed_content = f"{prefix}{clean_content}"

                    approx_tokens = len(prefixed_content.split())

                    chunk = ChunkCreate(
                        filing_id=doc_filing_id,
                        chunk_index=chunk_idx,
                        section_title=section_title[:500],
                        content=prefixed_content,
                        metadata={
                            "ticker": clean_ticker,
                            "company_name": company_name,
                            "fiscal_year": fiscal_year,
                            "section_title": section_title,
                            "has_table": is_table,
                            "char_count": len(clean_content),
                            "headers": section.metadata,
                        },
                        token_count=approx_tokens,
                        embedding=[],  # Populated during Phase 2.5 embedding stage
                    )
                    chunks.append(chunk)
                    chunk_idx += 1

        logger.info(
            "Stages 2 & 3 complete: Created %d total chunks (%d contain atomic tables).",
            len(chunks),
            sum(1 for c in chunks if c.metadata.get("has_table")),
        )
        return chunks

    def chunk_file(
        self,
        file_path: Path | str,
        ticker: str,
        company_name: str,
        fiscal_year: int,
        filing_id: Optional[UUID] = None,
    ) -> list[ChunkCreate]:
        """Read a parsed markdown file and execute the chunking pipeline."""
        target = Path(file_path)
        if not target.exists():
            raise FileNotFoundError(f"Markdown file not found: {target}")

        markdown_text = target.read_text(encoding="utf-8")
        return self.chunk_document(
            markdown_text=markdown_text,
            ticker=ticker,
            company_name=company_name,
            fiscal_year=fiscal_year,
            filing_id=filing_id,
        )


chunker = FinancialDocumentChunker()
