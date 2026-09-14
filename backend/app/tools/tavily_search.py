import os
from typing import Optional

from tavily import TavilyClient

from backend.app.core.config import settings


class TavilySearchTool:
    """Tool wrapper for the Tavily Search API.

    Executes structured financial web searches to augment agent context
    when internal SEC 10-K document retrieval yields zero relevant passages.
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key
        self._client: Optional[TavilyClient] = None

    @property
    def api_key(self) -> str:
        return (
            self._api_key
            or settings.TAVILY_API_KEY
            or os.environ.get("TAVILY_API_KEY", "")
        )

    @property
    def client(self) -> TavilyClient:
        if self._client is None:
            key = self.api_key
            if not key:
                raise ValueError(
                    "TAVILY_API_KEY is not configured in settings or environment. "
                    "Please set TAVILY_API_KEY in backend/.env"
                )
            self._client = TavilyClient(api_key=key)
        return self._client

    def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        search_depth: Optional[str] = None,
    ) -> str:
        """Execute web search and return formatted Markdown context.

        Output format:
        - Direct summary prepended if available: **Web Summary:** <answer>
        - Followed by structured snippets: **Source:** <title> (<url>)\n<content>
        - Separated by markdown horizontal rules (---).
        """
        clean_query = query.strip()
        if not clean_query:
            return "No search query provided."

        depth = search_depth or settings.TAVILY_SEARCH_DEPTH
        results_count = max_results or settings.TAVILY_MAX_RESULTS

        try:
            response = self.client.search(
                query=clean_query,
                search_depth=depth,
                max_results=results_count,
                include_answer=True,
                include_raw_content=False,
            )
        except Exception as exc:
            return f"Web search failed: {type(exc).__name__}: {str(exc)}"

        snippets: list[str] = []

        # 1. Direct answer summary from Tavily if provided
        direct_answer = response.get("answer")
        if direct_answer:
            snippets.append(f"**Web Summary:** {direct_answer.strip()}\n")

        # 2. Formatted search result snippets
        results = response.get("results", [])
        for res in results:
            title = res.get("title", "Untitled Source").strip()
            url = res.get("url", "").strip()
            content = res.get("content", "").strip()
            snippets.append(f"**Source:** {title} ({url})\n{content}")

        if not snippets:
            return "No relevant web results found."

        return "\n\n---\n\n".join(snippets)


# Default singleton instance
tavily_tool = TavilySearchTool()
