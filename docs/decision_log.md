# Decision Log

_This file tracks the "Why" behind technical and architectural choices made during development._

---

## [Date: 2026-09-10] Pivot from Streamlit to Next.js/FastAPI/Supabase

**Context:** Initially considered Streamlit for the UI and local ChromaDB for vector storage.
**Decision:** Shifted to Next.js (frontend), FastAPI (backend), and Supabase (pgvector).
**Rationale:** To elevate the project from a "portfolio script" to a "production-grade product," a decoupled architecture is required. Next.js allows for the strict, bespoke typographic design we want, while Supabase provides persistent, scalable vector storage and database functionality.

---

## [Date: 2026-09-10] Architecture Pivot: Dropping Clerk in Favor of Custom SMTP & JWT Authentication

**Context:** The initial architectural draft included Clerk for third-party user authentication.
**Decision:** Dropped Clerk entirely. Transitioned to a custom-engineered authentication system using FastAPI security (JWT access/refresh tokens), asynchronous transactional SMTP for email verification / passwordless magic links, and Supabase PostgreSQL for user state and token lifecycle management.
**Rationale:** Third-party auth providers (like Clerk) abstract away core security and protocol handling. Building authentication from scratch directly demonstrates deep backend engineering, distributed security principles, cryptographic token handling, and transactional email infrastructure—elevating this project into an enterprise-grade showcase without external vendor lock-in.

---

## [Date: 2026-09-11] PostgreSQL DML Privileges vs RLS for Supabase Service Role

**Context:** Running repository CRUD operations using the Supabase `service_role` key produced a PostgreSQL error `42501 (Permission Denied for table users)`.
**Decision:** Added explicit table and sequence grants (`GRANT ALL ON TABLE public.users TO service_role;`, `GRANT ALL ON TABLE public.auth_tokens TO service_role;`, `GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;`) to [`001_auth_schema.sql`](file:///d:/build/Financial%20CRAG/backend/migrations/001_auth_schema.sql).
**Rationale:** In PostgreSQL, Row-Level Security (RLS) and basic Data Manipulation Language (DML) permissions are orthogonal security layers. Even though Supabase's `service_role` is granted `BYPASSRLS`, it still requires table-level `SELECT`, `INSERT`, `UPDATE`, and `DELETE` grants if public schema defaults are restricted. Granting these explicitly guarantees consistent behavior across Supabase managed cloud and local Docker instances.

---

## [Date: 2026-09-11] Audit-Safe Token Lifecycle: Soft Revocation via `consumed_at`

**Context:** When designing magic links and refresh tokens, we evaluated whether to execute a SQL `DELETE` upon token exchange or store a `consumed_at` timestamp.
**Decision:** Implemented an immutable lifecycle where consumed tokens are retained with `consumed_at = NOW()` rather than deleted.
**Rationale:**
1. **Anti-Replay Security:** If a token is deleted, an intercepted token presented again looks like an "Invalid / Nonexistent Token". Retaining the hash allows the system to distinguish between an invalid token and a malicious replay attempt of an already-consumed token.
2. **Financial SEC Compliance & Auditability:** SEC due-diligence tools require rigorous non-repudiation. Every authentication attempt, token issuance, and consumption timestamp must be verifiable for security forensics.

---

## [Date: 2026-09-11] Early Extension Initialization (`pgvector`) in Foundational Migration

**Context:** Preparing the Supabase database schema for Phase 1 (Auth) versus Phase 2 (Data Ingestion & Vector Embeddings).
**Decision:** Initialized `CREATE EXTENSION IF NOT EXISTS "vector";` inside `001_auth_schema.sql`.
**Rationale:** Enabling the vector extension during initial database bootstrapping avoids administrative permissions issues later when deploying embeddings tables, ensuring the PostgreSQL instance is pre-configured for high-dimensional vector search.

---

## [Date: 2026-09-11] RFC 2606 Compliance for Test Email Generation

**Context:** Test suites generating mock emails with `.local` top-level domains triggered validation errors under Pydantic's `email-validator` (RFC 6762 / RFC 2822 compliance).
**Decision:** Standardized all mock analyst emails to RFC 2606 reserved domains (`@example.com`).
**Rationale:** Guarantees deterministic offline testing without triggering DNS lookups or domain-rejection errors during schema parsing.

---

## [Date: 2026-09-11] Asynchronous Non-Blocking SMTP Engine via `aiosmtplib`

**Context:** Delivering transactional verification emails without blocking FastAPI's async request handlers.
**Decision:** Implemented [`backend/app/services/email_service.py`](file:///d:/build/Financial%20CRAG/backend/app/services/email_service.py) using `aiosmtplib` rather than Python's standard blocking `smtplib`.
**Rationale:** Synchronous network operations in an async FastAPI route block the underlying asyncio event loop, causing severe latency spikes across concurrent requests. `aiosmtplib` handles socket I/O, STARTTLS negotiation, and SMTP handshakes asynchronously.

---

## [Date: 2026-09-11] Multi-Part MIME with Brutalist Inline HTML & Plain-Text Fallback

**Context:** Financial analysts frequently use strictly configured corporate email clients (Outlook, Bloomberg Anywhere, secure webmail) that strip external styles and block remote images.
**Decision:** Generated multi-part MIME (`multipart/alternative`) dispatches using Jinja2 with 100% self-contained inline CSS for HTML and an identical ASCII-formatted plain-text fallback.
**Rationale:** Adheres strictly to [`docs/Design.md`](file:///d:/build/Financial%20CRAG/docs/Design.md) (0px border radius, parchment `#F7F7F5`, no icons) while ensuring 100% deliverability across high-security financial enterprise environments without spam-score penalties.

---

## [Date: 2026-09-11] Developmental Fallback Engine (`SMTP_DEV_MODE=True`)

**Context:** Local engineering and test automation must operate reliably without requiring active internet connectivity or valid external mail relay credentials.
**Decision:** Added an automated console logging mode when `SMTP_DEV_MODE=True`.
**Rationale:** Speeds up local development loops and prevents test flakiness while ensuring the exact production payload, links, and token generation paths are fully exercised.

---

## [Date: 2026-09-11] Dual-Transport JWT Authentication (HTTP-Only Cookies + Bearer Header)

**Context:** Supporting both browser-based Next.js clients and programmatic financial terminal scripts (backtesters, automated reporting hooks, Postman/curl).
**Decision:** Configured [`backend/app/api/deps.py`](file:///d:/build/Financial%20CRAG/backend/app/api/deps.py) to resolve authentication credentials by prioritizing the standard `Authorization: Bearer <token>` header, falling back to the `access_token` cookie.
**Rationale:** Browser clients remain protected against Cross-Site Scripting (XSS) via `HttpOnly`, `SameSite=lax`, and `Secure` cookie attributes. Simultaneously, headless analytical workers and automated cron jobs can pass Bearer headers without having to manage cookie storage.

---

## [Date: 2026-09-11] Stateful Token Revocation and Anti-Replay Defense

**Context:** Pure JWT tokens are stateless by design and cannot be revoked before their expiration without maintaining state.
**Decision:** While short-lived access tokens remain stateless (60 min expiry), longer-lived refresh tokens (14 days) and single-use magic links are cryptographically hashed (SHA-256) and tracked in Supabase's `auth_tokens` table. During `/verify-token`, the magic link is immediately marked `consumed_at = NOW()`. During `/logout`, all refresh tokens for the analyst are revoked in the database.
**Rationale:** Balances sub-millisecond stateless verification on high-frequency API calls with absolute administrative control to revoke sessions immediately if an analyst account is compromised.

---

## [Date: 2026-09-11] Edge Middleware Route Protection via Session Cookie Inspection

**Context:** Protecting private financial analytical routes (`/dashboard`, `/workspace`, `/agent`) before React components render or hydrate on the client.
**Decision:** Implemented Next.js edge [`frontend/src/middleware.ts`](file:///d:/build/Financial%20CRAG/frontend/src/middleware.ts) to intercept incoming requests and verify the existence of the `access_token` or `refresh_token` HTTP-only cookie.
**Rationale:** Edge redirection prevents Flash of Unauthenticated Content (FOUC), eliminates client-side hydration delays, and ensures unauthorized requests are redirected to `/login?redirect=...` before any page chunks or sensitive layout data are downloaded.

---

## [Date: 2026-09-11] Phase 2: Asynchronous Pre-Processing Pipeline over Dynamic Runtime PDF Parsing

**Context:** Designing the SEC 10-K data ingestion strategy for the CRAG agent. Two approaches were evaluated:
1. **Dynamic Runtime Parsing**: Parse and embed PDFs on-demand when an analyst submits a query.
2. **Asynchronous Pre-Processing Pipeline**: Batch-process filings offline via a dedicated CLI/admin ingestion pipeline, storing pre-computed chunks and embeddings in Supabase `pgvector`.

**Decision:** Selected Asynchronous Pre-Processing Pipeline with Web Search Fallback (CRAG).

**Rationale:**
1. **Latency:** SEC 10-K filings are 100–300 page documents. LlamaParse extraction alone takes 30–120 seconds per filing. Adding embedding generation (~5–15 seconds for hundreds of chunks) and vector upsertion makes dynamic parsing produce unacceptable query latency (>2 minutes per user request).
2. **Cost Efficiency:** Pre-processing amortizes LlamaParse API credits across all future queries. Dynamic parsing would re-parse the same document for every distinct analyst query, rapidly exhausting the free 10,000 credits/month tier.
3. **Deterministic Retrieval Quality:** Pre-computed embeddings with structure-aware chunking (preserving Markdown tables intact) undergo quality validation once during ingestion. Dynamic parsing introduces non-deterministic chunk boundaries per invocation.
4. **CRAG Fallback Completeness:** If a filing hasn't been ingested or the retriever returns irrelevant chunks, the Corrective RAG grading node triggers Tavily web search as a real-time fallback — covering the gap without needing dynamic PDF parsing.
5. **Portfolio Demonstration Value:** Building a dedicated ETL pipeline (Source → Parse → Chunk → Embed → Store) with rate-limited SEC EDGAR integration, idempotent upsertion, and comprehensive logging demonstrates senior-level data engineering skills that dynamic "fetch-and-pray" approaches do not.

---

## [Date: 2026-09-11] SEC EDGAR API: Mandatory User-Agent Header & Rate Limiting

**Context:** The SEC enforces strict fair-access policies on EDGAR API endpoints.
**Decision:** Implement a compliant `User-Agent` header (format: `"CompanyName AdminContact@domain.com"`) and enforce a maximum of 10 requests/second via `asyncio.Semaphore` with exponential backoff retry on `403`/`429` responses.
**Rationale:** Non-compliant requests receive immediate `403 Forbidden` and repeat offenders get IP-blocked for 10+ minutes. As a portfolio piece handling real SEC data, demonstrating API citizenship and rate-limit engineering is essential.

---

## [Date: 2026-09-11] Embedding Model Selection: `BAAI/bge-small-en-v1.5` (384d, Local CPU)

**Context:** Evaluated embedding models for SEC financial document retrieval: OpenAI `text-embedding-3-small` (1536d, API cost per token), Cohere `embed-english-v3.0` (1024d, API cost), and `BAAI/bge-small-en-v1.5` (384d, local, free).
**Decision:** Selected `BAAI/bge-small-en-v1.5` via `sentence-transformers` with `normalize_embeddings=True`.
**Rationale:**
1. **Zero API Cost:** Runs entirely on local CPU (~133MB model), zero per-token charges. Critical for a portfolio project with no revenue.
2. **Retrieval Quality:** BGE v1.5 achieves state-of-the-art performance on MTEB benchmarks for its parameter class. The 384-dimension output provides excellent recall with minimal storage overhead in `pgvector`.
3. **Query Instruction Protocol:** BGE retrieval quality improves when queries are prepended with `"Represent this sentence for searching relevant passages: "` while document chunks are encoded without any prefix — a detail that distinguishes informed from naive implementations.
4. **Normalized Cosine Similarity:** With `normalize_embeddings=True`, L2-normalized unit vectors allow Cosine distance (`<=>`) to be computed as a simple dot product, enabling HNSW index optimization.

---

## [Date: 2026-09-11] Structure-Aware Chunking: Two-Stage Markdown Header + Table Preservation

**Context:** Standard fixed-size chunking (e.g., 500 characters) severs financial tables mid-row, destroying column-header associations and causing catastrophic retrieval failures for queries like "What were operating expenses in Q3 2023?"
**Decision:** Implement a two-stage chunking strategy:
1. **Stage 1 — Markdown Header Splitting:** Split LlamaParse output along `#`, `##`, `###` headers to preserve complete SEC filing sections (e.g., "Item 7. MD&A", "Item 8. Financial Statements").
2. **Stage 2 — Table-Aware Secondary Splitting:** Within each section, detect Markdown pipe-table blocks and treat them as atomic units. Apply `RecursiveCharacterTextSplitter` only to prose paragraphs exceeding the chunk size limit.
3. **Metadata Enrichment:** Prepend `[Document: {company} 10-K (FY {year}) | Section: {section_title}]` to each chunk before embedding.
**Rationale:** Financial tables are the single most queried artifact in 10-K analysis. Preserving them intact with contextual metadata ensures the LLM receives complete, structurally coherent data rather than fragmented rows stripped of their column definitions.

---

## [Date: 2026-09-11] Pre-Filtering CTE Architecture for `match_sec_chunks` Vector RPC

**Context:** When querying millions of high-dimensional vectors, applying vector similarity search before metadata filtering (or relying on unindexed join filters) results in poor recall or full table scans that degrade query latency.
**Decision:** Structured the `match_sec_chunks` RPC function using a Common Table Expression (CTE) `target_filings` that pre-filters `sec_filings` by `ticker` and/or `fiscal_year` using B-Tree indexes, before joining `sec_chunks` and calculating Cosine distance (`<=>`).
**Rationale:** 
1. Prunes the vector search space down to only the relevant filing's chunks before running HNSW graph traversals.
2. Returns parent filing metadata (`ticker`, `company_name`, `fiscal_year`) directly in the query output, saving a secondary round-trip join in the CRAG agent.
3. Preserves high recall when users query specific companies or years.

---

## [Date: 2026-09-11] Batch Ingestion Sizing for PostgREST Vector Upsertion

**Context:** Document chunks for a single 10-K filing can range from 100 to 500+ items, each containing a 384-float vector array. Transmitting all chunks in a single HTTP JSON payload to Supabase PostgREST risks payload entity size limits (413 Payload Too Large) or HTTP timeout.
**Decision:** Configured `ChunkRepository.bulk_insert_chunks` to partition chunks into batches of 50.
**Rationale:** 50 chunks with 384 floats (~1.5KB per vector + text) produces manageable ~150KB payloads that transmit reliably over standard HTTP connections without latency spikes or connection resets.

---

## [Date: 2026-09-11] Strict 384-Dimensional Pydantic Embedding Validation

**Context:** Vector embeddings generated by different models (e.g. OpenAI `text-embedding-3-small` = 1536d, BGE-small = 384d, BGE-large = 1024d) can easily lead to silent schema failures or database-level dimension mismatch errors if an incorrect model is invoked.
**Decision:** Added explicit Pydantic field validators in `ChunkCreate` and `ChunkSearchQuery` enforcing `len(embedding) == 384`.
**Rationale:** Catches embedding dimension mismatches at the application layer before making network calls to Supabase, producing actionable error messages during pipeline execution.

---

## [Date: 2026-09-11] SEC EDGAR Rate Limiting: Semaphore + Minimum Interval Throttling

**Context:** The SEC caps client traffic at 10 requests per second. A naive `asyncio.Semaphore(8)` permits 8 requests to fire concurrently within milliseconds, triggering burst-detection firewalls and resulting in `429 Too Many Requests` or `403 Forbidden` IP lockouts.
**Decision:** Paired the semaphore with a monotonic timestamp throttle `_min_interval = 1.0 / rate_limit_rps` under an `asyncio.Lock()`.
**Rationale:** Guarantees that requests are evenly spaced across time intervals (minimum 125ms between consecutive dispatches at 8 RPS), preventing burst traffic while fully utilizing permissible throughput.

---

## [Date: 2026-09-11] Idempotent Local Caching for Raw Filings

**Context:** SEC 10-K filings can be large (10MB–50MB for comprehensive reports). Repeated downloads during local development waste bandwidth and trigger redundant SEC traffic.
**Decision:** Checked `target_file.exists()` and `file_size > 0` before making network requests in `SECEdgarClient.download_filing()`, with an explicit `overwrite=True` override option.
**Rationale:** Makes the ingestion pipeline idempotent and resumes instantly without redundant network I/O when iterating on downstream parsing and chunking logic.

---

## [Date: 2026-09-11] PostgREST Vector String Deserialization via Pydantic `mode="before"`

**Context:** Supabase PostgREST returns PostgreSQL `VECTOR` column values as JSON strings (e.g. `"[0.1234, -0.5678, ...]"`) rather than native JSON arrays. In Pydantic v2, a field typed as `list[float]` strictly rejects `str` inputs before standard coercion, failing with `Input should be a valid list [type=list_type]`.
**Decision:** Implemented `@field_validator("embedding", mode="before")` on `ChunkInDB` and `ChunkCreate`. The validator checks if the input is a string, strips whitespace, and parses it via `json.loads` (with a comma-delimited fallback).
**Rationale:** Preserves clean typed models across the codebase without requiring custom repository-level decoding hacks before validation.

---

## [Date: 2026-09-11] Strict LlamaParse System Prompt for Tabular Financial Integrity

**Context:** Default LlamaParse extraction occasionally summarizes dense financial disclosures or flattens multi-period comparative tables into paragraph prose, losing column boundaries.
**Decision:** Authored a comprehensive `DEFAULT_SEC_PARSING_INSTRUCTION` instructing the multimodal vision model that it is reading an official SEC 10-K report. Explicitly instructed it to extract Balance Sheets, Income Statements, and Cash Flows as Markdown pipe-tables (`|---|---|`), retain accounting units (`$ in millions`), preserve negative parenthetical values (`$(1,234)`), and enforce Markdown header hierarchy (`#` for Parts, `##` for Items).
**Rationale:** Eliminates table flattening and guarantees that downstream chunking algorithms encounter standard Markdown tables that can be isolated as atomic chunks.

---

## [Date: 2026-09-11] Transparent Disk Caching (`parsed.md`) for LlamaParse Credit Conservation

**Context:** LlamaParse runs via LlamaCloud credit billing (~$1.25 per 1,000 credits, 1 credit/page). A typical 10-K filing has 100–150 pages. Repeatedly re-parsing the same document during chunking or embedding iteration quickly depletes the 10,000 credits/month free tier.
**Decision:** Automatically persisted extracted Markdown to `DATA_DIR/{ticker}/{accession}/parsed.md`. If `parsed.md` exists and is non-empty, `SECDocumentParser.parse_file()` returns it in <10ms without calling LlamaCloud.
**Rationale:** Enables infinite offline development and test iterations on chunking, embedding, and vector upsertion without consuming a single additional API credit.

---

## [Date: 2026-09-11] 3-Stage Structure-Aware Chunking: Headers, Atomic Tables, Prose Splitting

**Context:** Standard character-count chunkers (such as splitting blindly every 1000 characters) chop financial statement tables in half, severing row labels from their numerical values, and lose the section hierarchy (e.g. knowing whether a paragraph describes risk factors vs management discussion).
**Decision:** Architected a 3-stage pipeline in `FinancialDocumentChunker`:
1. **Stage 1 (Hierarchy)**: `MarkdownHeaderTextSplitter` divides text along `#`, `##`, and `###` headers, capturing section lineage in metadata.
2. **Stage 2 (Atomic Tables)**: Extracted contiguous Markdown pipe-tables (`|---|---|`) using regular expressions and treated them as indivisible atomic units. Only non-table prose exceeding 1,500 characters is split via `RecursiveCharacterTextSplitter`.
3. **Stage 3 (Context Prefixing)**: Prepended `[Document: {company} 10-K (FY {year}) | Section: {section_title}]` to every chunk.
**Rationale:** Preserves financial statements completely intact without losing row or column coherence while ensuring semantic search models retain rich entity and section context for every vector.

---

## [Date: 2026-09-11] Decoupling Chunk Creation from Dense Embedding Generation

**Context:** `ChunkCreate` required a non-empty `embedding: list[float]` with 384 dimensions. However, chunking (Sub-Phase 2.4) occurs prior to running the CPU/GPU embedding model (Sub-Phase 2.5). Requiring dense vectors during chunking would force embedding computation prematurely or require redundant intermediate data models.
**Decision:** Configured `ChunkCreate.embedding` with `default_factory=list` and updated validation to enforce `len(embedding) == 384` only when `embedding` is populated (`if v and len(v) != 384:`).
**Rationale:** Allows the chunker to emit clean `ChunkCreate` Pydantic models with complete metadata, which the downstream `DocumentEmbedder` directly populates in-place before vector database insertion.

---

## [Date: 2026-09-11] BAAI/bge-small-en-v1.5 Asymmetric Instruction Prefix Protocol

**Context:** Dense bi-encoder retrieval models trained with contrastive learning (such as the BAAI BGE family) map queries and document passages into a shared embedding space. Unlike symmetric models, BGE requires asymmetric instruction prefixing to achieve its benchmarked MTEB retrieval performance.
**Decision:** Configured `DocumentEmbedder` to enforce two strict rules:
1. **Document Chunks (Ingestion)**: Ingested raw without any prefix (`normalize_embeddings=True`).
2. **Search Queries (Retrieval)**: Prepended with `"Represent this sentence for searching relevant passages: "` prior to embedding.
**Rationale:** Preserves maximum fidelity for document chunk storage while steering the query vector towards document representation space during cosine similarity computation, boosting retrieval precision on financial questions.

---

## [Date: 2026-09-11] IngestionPipeline Lifecycle State Machine and Accession-Level Idempotency

**Context:** The ingestion pipeline spans multiple expensive or latency-heavy steps: SEC download, LlamaParse extraction, structure-aware chunking, dense vector embedding, and PostgREST bulk vector insertion. If interrupted or re-run, duplicate records or inconsistent states could occur.
**Decision:** Implemented an asynchronous state machine tracked in `sec_filings.parse_status` (`pending` -> `parsing` -> `parsed` -> `chunked` -> `embedded` -> `complete` or `failed`). Furthermore, keyed idempotency on the SEC `accession_number`:
- If an existing filing is already `COMPLETE` and `force_reingest=False`, the pipeline returns the existing records in <50ms without executing any duplicate compute or network calls.
- If `force_reingest=True`, existing chunks are deleted via `delete_chunks_by_filing` before re-inserting.
**Rationale:** Prevents duplicate chunks in the vector store, provides clear observability into pipeline failures, and ensures deterministic, resilient ingestion operations.

---

## [Date: 2026-09-13] Phase 3: LangGraph StateGraph Over Sequential LangChain Chains

**Context:** Phase 3 requires a Corrective RAG (CRAG) agent that self-reflects on retrieval quality and autonomously routes through web search fallback and deterministic math tools. Two orchestration approaches were evaluated:
1. **LangChain Sequential Chains:** Linear `chain1 | chain2 | chain3` composition with ReAct agent loop for tool calls.
2. **LangGraph StateGraph:** Explicit directed graph with typed state, conditional edges, and per-node streaming.

**Decision:** Selected LangGraph `StateGraph` with `TypedDict`-based `AgentState`.

**Rationale:**
1. **Cyclic Self-Correction:** CRAG's core pattern (grade → web search fallback → re-route) requires conditional cycles. Sequential chains are strictly linear and cannot express "if retrieval fails, fallback to web search, then rejoin the main path." LangGraph's `add_conditional_edges` handles this natively.
2. **Explicit State Contract:** `TypedDict` enforces a compile-time contract on what data flows between nodes (`documents`, `web_results`, `math_result`, `steps`). Sequential chains rely on implicit dictionary passing with no type safety.
3. **Per-Node Streaming for Thought Inspection:** The PRD mandates a UI panel showing `[Evaluating Context] → [Irrelevant] → [Web Search] → [Executing Math]`. LangGraph's `astream(state, stream_mode="updates")` yields discrete updates after each node completes — exactly what's needed for SSE streaming to the frontend. Sequential chains only stream the final output.
4. **Future Persistence:** LangGraph supports built-in `MemorySaver` and Postgres checkpointers for conversation persistence and state recovery. This aligns with the Phase 4/5 requirement for persistent chat history.
5. **Deterministic Edge Routing:** Tool routing decisions (math vs. direct QA, web search vs. proceed) are explicit graph edges rather than opaque ReAct reasoning loops, making the agent's decision process fully inspectable and testable.

---

## [Date: 2026-09-13] LLM Provider Factory Pattern (`get_llm`) with Groq Llama-3.3-70B Default

**Context:** Phase 3 requires an LLM for relevance grading, query transformation, math script generation, and synthesis. We needed to balance cost (free tier for portfolio demonstration), inference speed, and future extensibility (swapping to OpenAI GPT-4o-mini or Google Gemini).
**Decision:** Implemented a unified factory `get_llm(temperature=0.0)` returning a LangChain `BaseChatModel`. Defaulted to `ChatGroq` using `llama-3.3-70b-versatile` with lazy provider resolution.
**Rationale:**
1. **Zero Marginal Cost:** Groq offers generous free rate limits on Llama-3.3-70B, enabling extensive agent development and evaluation without recurring token costs.
2. **Ultra-Low Latency:** Groq's LPU architecture achieves ~250–300 tokens/second, which is critical for multi-node CRAG graphs where multiple sequential or concurrent LLM calls (grading + math + synthesis) occur per query.
3. **Decoupled Architecture:** The factory abstracts provider instantiation away from graph nodes. Swapping models or providers across the entire agent only requires changing `LLM_PROVIDER` in `backend/.env`.

---

## [Date: 2026-09-13] CRAG Grading Strategy: Concurrent Execution and Zero-Relevant Fallback Threshold

**Context:** The standard Corrective RAG (CRAG) paper explores different confidence thresholds for triggering external web search when evaluating retrieved context. We evaluated two trigger criteria:
1. **Lenient Fallback (Any Irrelevant):** Trigger web search if *any single chunk* in the retrieved batch is deemed irrelevant.
2. **Strict Fallback (Zero Relevant):** Filter out irrelevant chunks and proceed to tool decision / generation using the subset of relevant chunks; trigger web search *only if zero retrieved chunks* pass relevance grading (`len(filtered_documents) == 0`).

**Decision:** Implemented the **Zero-Relevant Fallback Threshold** (`web_search_needed = (len(filtered_documents) == 0)`), combined with concurrent async grading via `asyncio.gather`.

**Rationale:**
1. **Precision & Efficiency:** In 10-K filings, a top-10 retrieval result often retrieves 3–6 highly relevant sections alongside a few adjacent or introductory chunks. Triggering expensive external web searches when 4 or 5 chunks already directly answer the question causes redundant network calls, increases Tavily credit usage, and introduces external noise into a clean SEC filing answer.
2. **Preservation of Internal Ground Truth:** Official SEC 10-K filings are audited legal documents. Prioritizing internal audited data whenever available avoids polluting analytical answers with third-party web commentary unless internal documentation truly lacks the answer.
3. **Concurrent Async Grading:** Evaluating 10 chunks sequentially with an LLM would take 10+ seconds. Using `asyncio.gather` reduces grading latency to that of a single LLM call (~1–1.5s on Groq), while sorting results by original index preserves deterministic logging for the Thought Inspection Panel.

---

## [Date: 2026-09-14] Sub-Phase 3.3: Tavily Web Fallback & Query Transformation Architecture

**Context:** When internal SEC retrieval fails (zero relevant chunks), the agent requires external ground truth without hallucinating outdated or generic knowledge. Naively passing conversational user queries (e.g., "how much did they make?") directly to search engines yields low-quality promotional or SEO spam.
**Decision:** Implemented a two-step fallback pipeline:
1. **`query_transform_node`:** An LLM acts as a financial search query optimizer, injecting the stock ticker, fiscal year, and target accounting terminology into a concise query (<20 words) focused on authoritative sources (SEC.gov, Bloomberg, investor relations).
2. **`TavilySearchTool`:** Wraps the Tavily API with structured formatting, separating a top-level synthesized summary (`**Web Summary:**`) from source-attributed snippets (`**Source:** {title} ({url})\n{content}`) delimited by Markdown horizontal rules.
**Rationale:**
1. **Query Specificity:** Search engines index filings by ticker and fiscal year. Augmenting the query with entity context prior to searching dramatically elevates result relevancy on corporate disclosures.
2. **Attribution & Transparency:** Financial analysts need traceable source URLs and document titles. Structured markdown snippets preserve clear provenance for subsequent synthesis in the generation node.
3. **Resilience:** If the LLM query transform encounters rate limits or errors, it falls back to a deterministic string concatenation (`f"{ticker} {fiscal_year} {question}"`), ensuring the pipeline never fails catastrophically.

---

## [Date: 2026-09-14] Sub-Phase 3.4: Sandboxed Python REPL & Deterministic Arithmetic Routing

**Context:** LLMs routinely hallucinate financial arithmetic (calculating YoY percentage growth, operating margins, compound rates, or capital structure ratios) even when provided accurate source numbers. Allowing the LLM to guess math undermines analyst trust, while naively invoking `exec()` on LLM-generated code exposes the backend server to remote code execution (RCE) and sandbox escape attacks.
**Decision:** Implemented a two-tier arithmetic engine:
1. **`tool_decision_node`:** Uses structured output (`ToolDecision`) to classify whether a query requires exact arithmetic vs. direct data retrieval, keeping the pipeline lean for qualitative lookups.
2. **`execute_sandboxed_python`:** Enforces strict AST validation prior to execution:
   - Rejects all `ast.Import` and `ast.ImportFrom` nodes.
   - Rejects any `ast.Attribute` access starting with `__` (blocking `__class__`, `__bases__`, `__subclasses__` introspection escapes).
   - Rejects calls to dangerous execution builtins (`eval`, `exec`, `open`, `compile`, `__import__`).
   - Limits globals strictly to safe arithmetic builtins (`abs`, `round`, `sum`, `len`, `float`, `print`, etc.) and the `math` module.
   - Enforces a 10-second timeout via thread execution.
3. **`clean_python_code`:** Strips Markdown fences (` ```python `) and conversational filler from LLM responses before AST validation.
**Rationale:**
1. **Zero Hallucination Arithmetic:** Offloading math to deterministic Python runtime guarantees exact calculation values, formatted percentages, and comma-separated currency values.
2. **Enterprise Defense-in-Depth:** AST inspection occurs *before* compilation or execution, neutralizing malicious injections at parse time with zero attack surface.

---

## [Date: 2026-09-15] Sub-Phase 3.5: StateMachine Graph Assembly & Server-Sent Events (SSE) Streaming

**Context:** The CRAG state machine requires seamless orchestration across 7 distinct nodes (retrieval, grading, query transformation, web search, tool decision, math REPL, generation) with real-time observability into the agent's internal reasoning for the brutalist Thought Inspection Panel.
**Decision:**
1. **`build_crag_graph`:** Compiled a cyclical StateGraph with two explicit conditional edges:
   - `route_after_grading`: Diverts to `query_transform` -> `web_search` iff 0 relevant chunks pass grading.
   - `route_after_tool_decision`: Diverts to `math_repl` iff arithmetic computation is required.
2. **Dual-Channel SSE (`POST /api/v1/agent/query`):** Used FastAPI `StreamingResponse` wrapping `crag_agent.astream(initial_state, stream_mode="updates")` to stream typed JSON events:
   - `type="step"`: Discrete thought updates (`[Retrieve]`, `[Grade]`, `[Web Search]`, `[Math REPL]`, `[Generate]`).
   - `type="generation"`: Final synthesized response content.
   - `type="done"`: Pipeline completion signal.
**Rationale:**
1. **Deterministic State Transitions:** The 4 discrete routing paths (Direct QA, Grounded Math, Web Fallback QA, Web Fallback Math) are fully decoupled, deterministic, and independently verifiable.
2. **Real-time UX Without Blocking:** Rather than waiting 5–15 seconds for a monolithic response, the analyst observes immediate progress in the Thought Inspection Panel as each node finishes its work.

---

## [Date: 2026-09-16] Sub-Phase 3.6: Verification Matrix, Model Migration to Qwen 2.5 27B, and Token Budgeting

**Context:** During end-to-end integration testing of the CRAG agent, Groq returned `404 model_not_found` for `llama-3.3-70b-versatile` due to upstream model deprecations on Groq's active endpoints. Furthermore, when switching models, certain Groq endpoints either lacked function/tool calling support (e.g., `groq/compound`, `openai/gpt-oss-120b`) or enforced strict Output Tokens Per Minute (OTPM = 1,000) limits on free on-demand tiers, causing 429 errors when requests lacked explicit `max_tokens` limits.
**Decision:**
1. **Model Migration:** Standardized on `qwen/qwen3.8-27b` across application config and the `get_llm` factory. Qwen 2.5 27B demonstrated flawless Pydantic tool-calling fidelity for `GradeChunk` and `ToolDecision` structured outputs.
2. **Strict Output Token Budgeting:** Introduced `LLM_MAX_TOKENS: int = 800` in `backend/app/core/config.py` and passed node-appropriate token ceilings (`max_tokens=250` for grading and tool decisions, `max_tokens=100` for query transformations, `max_tokens=600` for math script generation, `max_tokens=800` for final report generation). Updated system prompts to strictly forbid unnecessary conversational preamble in code generation.
3. **Deterministic Verification Matrix:** Implemented full mocked integration tests in `backend/tests/test_agent_graph.py` covering all 4 graph traversal paths (Direct QA, Math Execution, Web Search Fallback QA, Web Search Fallback + Math) and SSE streaming endpoint tests in `backend/tests/test_agent_api.py`. Verified live end-to-end execution against Apple's FY 2023 SEC 10-K in Supabase pgvector and Groq via `backend/scripts/test_e2e_agent.py`.
**Rationale:**
1. **Zero-Latency Deterministic CI:** Mocking LLM, Tavily, and Supabase calls in pytest guarantees the full 70-test test suite executes in <45s without consuming network bandwidth or API quotas.
2. **Production Reliability:** Explicit token budgeting completely eliminates OTPM rate limit rejections on Groq's on-demand tier while ensuring the AST sandboxed Python REPL receives clean, executable Python syntax without conversational truncation.
3. **Complete Observability:** Real-time Thought Inspection logging accurately surfaces state machine transitions (`[Retrieve]`, `[Grade]`, `[Tool Decision]`, `[Math REPL]`, `[Generate]`), providing the backend foundation for Phase 4/5 streaming UI.

---

## [Date: 2026-09-16] Phase 4: Server-Sent Events (SSE) via Custom Fetch Handler Over WebSockets or Polling

**Context:** Phase 4 connects the Next.js 16 frontend to the FastAPI `POST /api/v1/agent/query` streaming endpoint. Three transport mechanisms were evaluated:
1. **Standard Polling:** Client sends a request, waits for a complete JSON response, then displays everything at once.
2. **WebSockets:** Persistent bidirectional TCP connection between client and server.
3. **Server-Sent Events (SSE):** Unidirectional server-to-client stream over a standard HTTP response using `text/event-stream`.

A fourth consideration was the browser-native `EventSource` API vs. a custom `fetch` + `ReadableStream` handler.

**Decision:** Implement SSE consumption via a **custom `fetch` handler** using `response.body.getReader()` and a `TextDecoder` line buffer. Reject `EventSource`, WebSockets, and polling.

**Rationale:**
1. **Unidirectional Semantics Match:** The CRAG agent interaction is strictly request-response: the client sends a single query, and the server streams a sequence of typed events (`step`, `generation`, `done`, `error`). WebSockets' bidirectional channel is architecturally over-engineered for a pattern that never requires server-initiated messages outside of a request context.
2. **HTTP-Only Cookie Forwarding:** The application's auth system stores JWT `access_token` in HTTP-only cookies. The browser-native `EventSource` API does not support `POST` requests, custom request headers, or JSON request bodies — only `GET` with query parameters. A custom `fetch` with `credentials: "include"` and `Content-Type: application/json` is the only mechanism that satisfies all three requirements (POST + JSON body + cookie forwarding) simultaneously.
3. **Infrastructure Simplicity:** SSE runs over standard HTTP/1.1 or HTTP/2 connections. WebSockets require protocol upgrades (`101 Switching Protocols`), dedicated connection management, heartbeat/ping-pong keepalives, and specialized load balancer configuration on Vercel and Railway. SSE requires zero additional infrastructure.
4. **LangGraph Streaming Alignment:** The backend's `crag_agent.astream(state, stream_mode="updates")` yields discrete state updates after each node completes — a natural fit for SSE's line-delimited `data:` protocol. Each LangGraph node completion maps 1:1 to an SSE event, enabling the Thought Inspection Panel to update in real-time without buffering.
5. **Automatic Reconnection (Future):** SSE natively supports `retry:` directives and `Last-Event-ID` headers for automatic reconnection, providing a resilience path without custom retry logic. WebSocket reconnection requires explicit client-side state management and re-handshake negotiation.

---

## [Date: 2026-09-16] Phase 4: Markdown Rendering with `react-markdown` + `remark-gfm`

**Context:** The `generate_node` returns structured Markdown containing `##` headers, `|` pipe tables, `**bold**` metrics, `` `code` `` spans, and ` ```python ``` ` fenced code blocks. The frontend must render this as a styled editorial financial report, not raw text. Two approaches were evaluated:
1. **Custom Regex Parser:** Hand-roll a Markdown-to-JSX transformer targeting only the subset of Markdown syntax the agent emits.
2. **`react-markdown` + `remark-gfm`:** Battle-tested AST-based Markdown renderer with GitHub Flavored Markdown plugin for pipe tables and strikethrough.

**Decision:** Install `react-markdown` and `remark-gfm` as production dependencies. Use custom component overrides to map rendered elements to the brutalist design system (serif prose, monospace tables, square-cornered code blocks).

**Rationale:**
1. **Correctness Guarantee:** Financial tables with pipe-delimited columns (`| Revenue | $383.3B |`) require precise alignment parsing. A regex approach risks edge cases with escaped pipes, multi-line cells, or nested inline formatting. `remark-gfm` implements the full GFM specification via a proper AST parser.
2. **Component Override Architecture:** `react-markdown` exposes a `components` prop allowing every HTML element (`h2`, `table`, `code`, `p`) to be replaced with custom React components. This enables strict enforcement of Design.md rules (Newsreader serif for `<p>`, JetBrains Mono for `<code>`, mustard accent for `<th>`) without forking or patching the library.
3. **Zero XSS Surface:** `react-markdown` renders Markdown to React elements via an AST, never using `dangerouslySetInnerHTML`. This is critical for a financial application where LLM-generated content must not execute arbitrary HTML or JavaScript.
