"""LlamaParse integration for vision-aware SEC 10-K document parsing.

Extracts complex multi-page financial filings into structured Markdown,
strictly preserving financial statement tables as pipe-tables and maintaining
section header hierarchy while avoiding redundant API costs via local disk caching.
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional

from backend.app.core.config import settings

logger = logging.getLogger("sec_parser")

DEFAULT_SEC_PARSING_INSTRUCTION = """
You are an expert financial document parser analyzing an official SEC Form 10-K annual report.
Your primary objective is to produce high-fidelity Markdown that faithfully preserves the document's structure and tabular data:
1. FINANCIAL STATEMENTS & TABLES: All numerical financial tables (Consolidated Statements of Operations / Income,
   Consolidated Balance Sheets, Statements of Cash Flows, Statements of Shareholders' Equity, and Footnote Tables)
   MUST be extracted as clean Markdown pipe-tables (| Header 1 | Header 2 | ... |).
   - Ensure every column header and row label is preserved with exact column alignments.
   - Strictly preserve accounting reporting units (e.g. '$ in millions', 'in thousands, except per share data').
   - Retain all exact numeric figures, negative signs, parentheses denoting deficits, and percentage symbols.
   - Do NOT compress, summarize, truncate, or omit financial tables.
2. SECTION HEADINGS & HIERARCHY: Strictly preserve all SEC filing structural parts and item headers as Markdown headings:
   - Use # for Parts (e.g. # PART I, # PART II)
   - Use ## for Items (e.g. ## Item 1. Business, ## Item 1A. Risk Factors, ## Item 7. Management's Discussion and Analysis, ## Item 8. Financial Statements)
   - Use ### for major sub-sections and note titles (e.g. ### Note 1 - Summary of Significant Accounting Policies)
3. TEXT & NARRATIVE: Preserve prose paragraphs cleanly without mid-sentence breaks. Keep footnote disclosures intact and adjacent to their respective statements.
"""


class SECDocumentParser:
    """Vision-aware parser utilizing LlamaParse for high-fidelity SEC 10-K extraction."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        result_type: Optional[str] = None,
        num_workers: Optional[int] = None,
        parsing_instruction: Optional[str] = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.LLAMA_CLOUD_API_KEY
        self.result_type = result_type or settings.LLAMA_PARSE_RESULT_TYPE
        self.num_workers = num_workers or settings.LLAMA_PARSE_NUM_WORKERS
        self.parsing_instruction = parsing_instruction or DEFAULT_SEC_PARSING_INSTRUCTION

        self._parser = None

    def _get_parser(self):
        """Lazy-initialize LlamaParse instance with configured parameters."""
        if self._parser is None:
            if not self.api_key:
                raise ValueError(
                    "LLAMA_CLOUD_API_KEY is not configured. "
                    "Please set LLAMA_CLOUD_API_KEY in backend/.env to parse documents with LlamaParse."
                )

            from llama_parse import LlamaParse

            self._parser = LlamaParse(
                api_key=self.api_key,
                result_type=self.result_type,
                num_workers=self.num_workers,
                parsing_instruction=self.parsing_instruction,
                verbose=True,
            )
        return self._parser

    @staticmethod
    def get_cache_path(file_path: Path | str) -> Path:
        """Derive the local parsed markdown cache path: {filing_dir}/parsed.md."""
        target_path = Path(file_path)
        return target_path.parent / "parsed.md"

    def parse_file(self, file_path: Path | str, overwrite: bool = False) -> str:
        """Synchronously parse a filing document to Markdown, utilizing disk cache if present."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Target document not found at: {path}")

        cache_file = self.get_cache_path(path)

        if cache_file.exists() and not overwrite:
            content = cache_file.read_text(encoding="utf-8")
            if content.strip():
                logger.info(
                    "Retrieved parsed Markdown from local disk cache at %s (%d chars). Skipping LlamaCloud API call.",
                    cache_file,
                    len(content),
                )
                return content

        logger.info(
            "Parsing document with LlamaParse: %s (Workers: %d, Mode: %s) ...",
            path,
            self.num_workers,
            self.result_type,
        )

        parser = self._get_parser()
        documents = parser.load_data(str(path))

        markdown_text = "\n\n".join(doc.text for doc in documents if doc.text)

        if not markdown_text.strip():
            raise RuntimeError(f"LlamaParse produced empty output for document: {path}")

        cache_file.write_text(markdown_text, encoding="utf-8")
        logger.info(
            "Parsed Markdown successfully cached to %s (%d characters).",
            cache_file,
            len(markdown_text),
        )

        return markdown_text

    async def aparse_file(self, file_path: Path | str, overwrite: bool = False) -> str:
        """Asynchronously parse a filing document to Markdown, utilizing disk cache if present."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Target document not found at: {path}")

        cache_file = self.get_cache_path(path)

        if cache_file.exists() and not overwrite:
            content = cache_file.read_text(encoding="utf-8")
            if content.strip():
                logger.info(
                    "Retrieved parsed Markdown from local disk cache at %s (%d chars). Skipping LlamaCloud API call.",
                    cache_file,
                    len(content),
                )
                return content

        logger.info(
            "Asynchronously parsing document with LlamaParse: %s (Workers: %d, Mode: %s) ...",
            path,
            self.num_workers,
            self.result_type,
        )

        parser = self._get_parser()
        
        # aload_data executes asynchronously
        documents = await parser.aload_data(str(path))

        markdown_text = "\n\n".join(doc.text for doc in documents if doc.text)

        if not markdown_text.strip():
            raise RuntimeError(f"LlamaParse produced empty output for document: {path}")

        cache_file.write_text(markdown_text, encoding="utf-8")
        logger.info(
            "Parsed Markdown successfully cached to %s (%d characters).",
            cache_file,
            len(markdown_text),
        )

        return markdown_text
