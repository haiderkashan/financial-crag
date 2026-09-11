"""Repository handling persistence operations for the sec_filings table in Supabase."""
from typing import Optional, Union
from uuid import UUID
from supabase import Client

from backend.app.db.supabase import get_supabase_client
from backend.app.models.filing import FilingCreate, FilingInDB, FilingUpdate, IngestionStatus


class FilingRepository:
    """Repository handling persistence operations for the sec_filings registry in Supabase."""

    def __init__(self, client: Optional[Client] = None) -> None:
        self._client = client

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = get_supabase_client()
        return self._client

    def create_filing(self, filing_in: FilingCreate) -> FilingInDB:
        """Insert a new SEC filing record into Supabase."""
        status_val = (
            filing_in.parse_status.value
            if isinstance(filing_in.parse_status, IngestionStatus)
            else str(filing_in.parse_status)
        )
        payload = {
            "ticker": filing_in.ticker,
            "company_name": filing_in.company_name,
            "form_type": filing_in.form_type,
            "fiscal_year": filing_in.fiscal_year,
            "fiscal_period": filing_in.fiscal_period,
            "accession_number": filing_in.accession_number,
            "filing_date": filing_in.filing_date.isoformat() if filing_in.filing_date else None,
            "source_url": filing_in.source_url,
            "parse_status": status_val,
            "total_chunks": filing_in.total_chunks,
        }
        res = self.client.table("sec_filings").insert(payload).execute()
        if not res.data:
            raise RuntimeError(
                f"Failed to create filing record for {filing_in.ticker} ({filing_in.accession_number})"
            )
        return FilingInDB.model_validate(res.data[0])

    def get_by_id(self, filing_id: Union[UUID, str]) -> Optional[FilingInDB]:
        """Fetch a filing record by its primary key UUID."""
        res = (
            self.client.table("sec_filings")
            .select("*")
            .eq("id", str(filing_id))
            .limit(1)
            .execute()
        )
        if res.data and len(res.data) > 0:
            return FilingInDB.model_validate(res.data[0])
        return None

    def get_by_accession(self, accession_number: str) -> Optional[FilingInDB]:
        """Fetch a filing record by its unique SEC accession number."""
        res = (
            self.client.table("sec_filings")
            .select("*")
            .eq("accession_number", accession_number.strip())
            .limit(1)
            .execute()
        )
        if res.data and len(res.data) > 0:
            return FilingInDB.model_validate(res.data[0])
        return None

    def get_by_ticker_and_year(
        self, ticker: str, fiscal_year: int, form_type: str = "10-K"
    ) -> Optional[FilingInDB]:
        """Fetch filing by stock ticker, fiscal year, and form type."""
        res = (
            self.client.table("sec_filings")
            .select("*")
            .eq("ticker", ticker.strip().upper())
            .eq("fiscal_year", fiscal_year)
            .eq("form_type", form_type)
            .limit(1)
            .execute()
        )
        if res.data and len(res.data) > 0:
            return FilingInDB.model_validate(res.data[0])
        return None

    def get_filings_by_ticker(self, ticker: str) -> list[FilingInDB]:
        """Fetch all filings for a specific stock ticker."""
        res = (
            self.client.table("sec_filings")
            .select("*")
            .eq("ticker", ticker.strip().upper())
            .order("fiscal_year", desc=True)
            .execute()
        )
        if res.data:
            return [FilingInDB.model_validate(row) for row in res.data]
        return []

    def update_status(
        self,
        filing_id: Union[UUID, str],
        parse_status: Union[IngestionStatus, str],
        total_chunks: Optional[int] = None,
    ) -> Optional[FilingInDB]:
        """Update the ingestion lifecycle status and optionally total chunk count."""
        status_val = (
            parse_status.value
            if isinstance(parse_status, IngestionStatus)
            else str(parse_status)
        )
        update_data: dict[str, Union[str, int]] = {"parse_status": status_val}
        if total_chunks is not None:
            update_data["total_chunks"] = total_chunks

        res = (
            self.client.table("sec_filings")
            .update(update_data)
            .eq("id", str(filing_id))
            .execute()
        )
        if res.data and len(res.data) > 0:
            return FilingInDB.model_validate(res.data[0])
        return None

    def update_filing(
        self, filing_id: Union[UUID, str], update_in: FilingUpdate
    ) -> Optional[FilingInDB]:
        """Update fields on an existing filing record."""
        payload: dict[str, Union[str, int]] = {}
        if update_in.parse_status is not None:
            payload["parse_status"] = (
                update_in.parse_status.value
                if isinstance(update_in.parse_status, IngestionStatus)
                else str(update_in.parse_status)
            )
        if update_in.total_chunks is not None:
            payload["total_chunks"] = update_in.total_chunks
        if update_in.source_url is not None:
            payload["source_url"] = update_in.source_url
        if update_in.filing_date is not None:
            payload["filing_date"] = update_in.filing_date.isoformat()

        if not payload:
            return self.get_by_id(filing_id)

        res = (
            self.client.table("sec_filings")
            .update(payload)
            .eq("id", str(filing_id))
            .execute()
        )
        if res.data and len(res.data) > 0:
            return FilingInDB.model_validate(res.data[0])
        return None

    def delete_filing(self, filing_id: Union[UUID, str]) -> bool:
        """Delete a filing and cascade delete all associated chunks."""
        res = (
            self.client.table("sec_filings")
            .delete()
            .eq("id", str(filing_id))
            .execute()
        )
        return bool(res.data)


filing_repo = FilingRepository()
