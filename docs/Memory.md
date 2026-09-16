# Project Memory & Progress Tracker

## 1. Project Overview
- **Project:** Financial SEC Due-Diligence CRAG Agent
- **Status:** Phase 3 (The CRAG Agent) - COMPLETE ✓ (All 6 Sub-Phases Verified, 70/70 Tests Green, Live E2E Verified)

---

## 2. Phase 1 Status: COMPLETE ✓

All 5 Sub-Phases implemented, tested, merged to `main`, and pushed to remote.

- **Sub-Phase 1.1** ✓ — Environment & Project Scaffolding (Next.js 16, FastAPI, Tailwind, bespoke typography)
- **Sub-Phase 1.2** ✓ — Supabase Schema & Database Connection Layer (users, auth_tokens, pgvector extension, repositories)
- **Sub-Phase 1.3** ✓ — Asynchronous SMTP Email Dispatcher & Templates (aiosmtplib, brutalist Jinja2 templates, dev mode fallback)
- **Sub-Phase 1.4** ✓ — Cryptographic Auth Engine & FastAPI Endpoints (SHA-256 hashing, JWT, anti-replay, HTTP-only cookies, 6 integration tests)
- **Sub-Phase 1.5** ✓ — Frontend Authentication UI & Protected Routing (API client, AuthContext, editorial login/verify/dashboard, edge middleware)

**Full Test Suite: 11 passed (all green)**

---

## 3. Current Phase: Phase 2 — Data Ingestion Pipeline (Backend)

### Architectural Decision
We are **NOT** fetching and parsing PDFs dynamically at runtime. Instead, Phase 2 is a **dedicated backend ingestion pipeline** (CLI script) that pre-processes SEC 10-K filings offline. See `decision_log.md` for full rationale.

### Pipeline Flow
```
SEC EDGAR API → Download 10-K → LlamaParse (PDF→Markdown) → Structure-Aware Chunking → BGE Embedding (384d) → Supabase pgvector (HNSW)
```

---

### Sub-Phase 2.1: Vector Store Schema & Database Migration — COMPLETE ✓

- `002_sec_vector_schema.sql` executed in Supabase.
- `sec_filings` and `sec_chunks` tables active with HNSW cosine index (`m=16, ef_construction=64`).
- CTE pre-filtered `match_sec_chunks` RPC operational with metadata filtering by ticker and fiscal year.
- Pydantic models (`filing.py`, `chunk.py`) and repositories (`filing_repo.py`, `chunk_repo.py`) tested and verified.

---

### Sub-Phase 2.2: SEC EDGAR Document Sourcing — COMPLETE ✓

- `SECEdgarClient` implemented with `asyncio.Semaphore(8)` + monotonic interval throttle.
- CIK resolution via `company_tickers.json` with in-memory caching.
- Form 10-K extraction from columnar submissions JSON matching report date and filing date.
- Primary document downloaded and cached to `data/filings/{ticker}/{accession}/`.
- Verified via `test_sec_download.py` and `test_sec_client.py`.

---

### Sub-Phase 2.3: LlamaParse PDF-to-Markdown Integration — COMPLETE ✓

- `SECDocumentParser` operational with `DEFAULT_SEC_PARSING_INSTRUCTION`.
- Apple FY 2023 10-K parsed into high-fidelity Markdown (259,615 characters, 671 table rows, 62 header delimiters).
- Cached to `data/filings/AAPL/0000320193-23-000106/parsed.md`.
- Verified via `test_parser.py` and `test_parser.py` unit suite.

---

### Sub-Phase 2.4: Structure-Aware Chunking Engine

**Status:** Code Complete & Verified (Commits 1–4 pushed). Awaiting user visual inspection of table chunks.

#### Implemented Components:
1. **Dependencies**:
   - `langchain-text-splitters>=0.3.0` added to `requirements.txt` and installed in `.venv`.
2. **Chunker Implementation (`backend/app/ingestion/chunker.py`)**:
   - `FinancialDocumentChunker` class with 3-stage architecture:
     - **Stage 1 (Hierarchy)**: `MarkdownHeaderTextSplitter` splitting on `#`, `##`, `###` into 140 section documents with lineage.
     - **Stage 2 (Atomic Tables)**: Regex (`TABLE_REGEX`) isolates Markdown pipe-tables. Tables are NEVER severed mid-row regardless of character length. Non-table prose exceeding 1,500 characters is split via `RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)`.
     - **Stage 3 (Context Prefixing)**: Prepends `[Document: {company_name} 10-K (FY {fiscal_year}) | Section: {section_title}]\n\n` to each chunk. Packages into `ChunkCreate` Pydantic models with `has_table`, token counts, and header metadata.
3. **Automated Verification Harness**:
   - `backend/scripts/test_chunker.py`: CLI verification script generating 299 total chunks (243 prose, 56 atomic tables) from Apple's 10-K in 0.033s. Validates table row syntax and prints sampled table.
   - `backend/tests/test_chunker.py`: 3 unit tests verifying synthetic doc chunking, table preservation beyond chunk_size, and prose splitting. All passing.

**Verification Checkpoint 2.4:**
- Run `python backend/scripts/test_chunker.py`.
- Visually verify sampled table chunk is not severed mid-row and contains complete pipe delimiters.
- Total chunk count: 299 (243 prose, 56 atomic tables).

#### Tasks:
1. **Create `/backend/app/ingestion/chunker.py`:**
   - `FinancialDocumentChunker` class
   - **Stage 1 — Header Splitting:**
     - Use `MarkdownHeaderTextSplitter` from `langchain-text-splitters` to split on `#`, `##`, `###`
     - Each split retains its full header hierarchy as metadata
   - **Stage 2 — Table-Aware Secondary Splitting:**
     - Regex detection of Markdown pipe-table blocks (`|...|` bounded regions)
     - Tables treated as atomic units (never split mid-table)
     - Prose-only sections exceeding `chunk_size=1500` characters split via `RecursiveCharacterTextSplitter` with `chunk_overlap=200`
   - **Stage 3 — Metadata Enrichment:**
     - Each chunk gets metadata dict: `{ "ticker": str, "company_name": str, "fiscal_year": int, "section_title": str, "chunk_index": int, "has_table": bool, "source_file": str }`
     - Content prefix: `[Document: {company} 10-K (FY {year}) | Section: {section_title}]\n\n{content}`
   - Returns: `list[ChunkCreate]` ready for embedding and upsertion

2. **Add dependencies to `requirements.txt`:**
   - `langchain-text-splitters>=0.3.0`

**Verification Checkpoint 2.4:**
- Chunk the parsed AAPL Markdown from 2.3
- Assert: zero tables are split mid-row (regex validation)
- Assert: all chunks have complete metadata
- Assert: chunk count is reasonable (expect 100–400 for a typical 10-K)
- Assert: average chunk size within 500–2000 character range

---

### Sub-Phase 2.5: Embedding Generation & Vector Upsertion

**Objective:** Generate 384-dimensional embeddings for all chunks using a local sentence-transformer model and upsert everything into Supabase pgvector.

#### Tasks:
1. **Update `/backend/app/core/config.py`:**
   - Add settings: `EMBEDDING_MODEL_NAME` (default `"BAAI/bge-small-en-v1.5"`), `EMBEDDING_DIMENSION` (default `384`), `EMBEDDING_DEVICE` (default `"cpu"`), `EMBEDDING_BATCH_SIZE` (default `32`)

2. **Create `/backend/app/ingestion/embedder.py`:**
   - `DocumentEmbedder` class with lazy singleton `SentenceTransformer` model loading
   - `embed_chunks(chunks: list[str]) -> list[list[float]]`:
     - Batch encode with `model.encode(chunks, normalize_embeddings=True, batch_size=32, show_progress_bar=True)`
     - No instruction prefix for document chunks (BGE protocol)
   - `embed_query(query: str) -> list[float]`:
     - Prepend `"Represent this sentence for searching relevant passages: "` before encoding
     - Single vector return for runtime retrieval
   - Logging: model load time, embedding batch duration, vectors per second throughput

3. **Create `/backend/app/ingestion/pipeline.py`:**
   - `IngestionPipeline` class orchestrating the full flow:
     - `ingest_filing(ticker: str, fiscal_year: int)` — single filing end-to-end
     - `ingest_batch(tickers: list[str], fiscal_years: list[int])` — multi-filing batch
   - Pipeline steps:
     1. Check if filing already exists in DB (idempotency via accession_number)
     2. Download via `SECEdgarClient`
     3. Update `parse_status = 'parsing'`
     4. Parse via `SECDocumentParser`
     5. Update `parse_status = 'chunked'`
     6. Chunk via `FinancialDocumentChunker`
     7. Embed via `DocumentEmbedder`
     8. Update `parse_status = 'embedded'`
     9. Bulk upsert to Supabase via `chunk_repo.bulk_upsert_chunks()`
     10. Update `parse_status = 'complete'`, set `total_chunks`
   - Error handling: catch exceptions at each step, set `parse_status = 'failed'`, log full traceback
   - CLI entry point: `python -m backend.app.ingestion.pipeline --ticker AAPL --year 2023`

4. **Create CLI runner `/backend/scripts/run_ingestion.py`:**
   - argparse with `--ticker`, `--year`, `--batch-file` (CSV of ticker,year pairs)
   - Calls `IngestionPipeline.ingest_filing()` or `ingest_batch()`
   - Pretty console output with progress indicators

5. **Add dependencies to `requirements.txt`:**
   - `sentence-transformers>=3.0.0`
   - `torch` (CPU-only: `--index-url https://download.pytorch.org/whl/cpu`)
   - `numpy`

**Verification Checkpoint 2.5 (FINAL — Phase 2 Complete):**
- Run full pipeline: `python -m backend.app.ingestion.pipeline --ticker AAPL --year 2023`
- Verify in Supabase dashboard:
  - `sec_filings` table has 1 record with `parse_status = 'complete'`
  - `sec_chunks` table has N chunks with non-null `embedding` vectors
  - `total_chunks` matches actual chunk count
- Run `match_sec_chunks` RPC with a test query embedding:
  - Query: "What were Apple's total revenue and operating expenses?"
  - Verify: top results contain relevant financial table chunks with similarity > 0.5
- Run idempotency test: re-run pipeline for same ticker/year, verify no duplicate records
- Run pytest integration test covering the full pipeline lifecycle

---

## 4. Phase Roadmap & Completion Tracker

- [x] **Phase 1: Foundation & Custom Auth** — COMPLETE ✓
  - [x] Sub-Phase 1.1: Environment & Project Scaffolding
  - [x] Sub-Phase 1.2: Supabase Schema & Database Connection Layer
  - [x] Sub-Phase 1.3: Asynchronous SMTP Email Dispatcher & Templates
  - [x] Sub-Phase 1.4: Cryptographic Auth Engine & FastAPI Endpoints
  - [x] Sub-Phase 1.5: Frontend Authentication UI & Protected Routing
- [x] **Phase 2: Data Ingestion Pipeline (Backend)** — COMPLETE ✓
  - [x] Sub-Phase 2.1: Vector Store Schema & Database Migration ✓
  - [x] Sub-Phase 2.2: SEC EDGAR Document Sourcing ✓
  - [x] Sub-Phase 2.3: LlamaParse PDF-to-Markdown Integration ✓
  - [x] Sub-Phase 2.4: Structure-Aware Chunking Engine ✓
  - [x] Sub-Phase 2.5: Embedding Generation & Vector Upsertion ✓
- [x] **Phase 3: The CRAG Agent (Backend)** — COMPLETE ✓
  - [x] Sub-Phase 3.1: Config, Dependencies & Agent State Schema ✓
  - [x] Sub-Phase 3.2: Retrieve Node + Grade Node ✓
  - [x] Sub-Phase 3.3: Web Search Fallback (Tavily) + Query Transform ✓
  - [x] Sub-Phase 3.4: Tool Decision Node + Math REPL Node ✓
  - [x] Sub-Phase 3.5: Generate Node + Graph Assembly + Streaming API ✓
  - [x] Sub-Phase 3.6: Integration Tests & End-to-End Verification ✓
- [ ] **Phase 4: API & Streaming Integration** — IN PROGRESS
  - [ ] Sub-Phase 4.1: TypeScript Types & SSE Stream Client
  - [ ] Sub-Phase 4.2: React State Management Hook (`useAgentStream`)
  - [ ] Sub-Phase 4.3: Agent Dashboard Layout (Shell & Query Bar)
  - [ ] Sub-Phase 4.4: Thought Inspection Panel Component
  - [ ] Sub-Phase 4.5: Markdown Rendering & Synthesis Document
  - [ ] Sub-Phase 4.6: Integration Wiring & Error Boundaries
- [ ] **Phase 5: UI/UX & Bespoke Aesthetic**
  - [ ] Implement strict design guidelines (no icons, bespoke typography, running document layout)
  - [ ] Build "Thought Inspection" state machine UI panel

---

## 7. Phase 4 Architecture: API & Streaming Integration

### Overview

Phase 4 bridges the CRAG backend to the Next.js 16 frontend. The core challenge is consuming Server-Sent Events (SSE) from `POST /api/v1/agent/query` over a `fetch` request that forwards HTTP-only authentication cookies, then parsing the stream into two distinct UI channels: a real-time Thought Inspection terminal panel and a typeset editorial Markdown synthesis document.

### Transport Architecture

```
┌─────────────────────────────────────┐
│         Next.js 16 Client           │
│                                     │
│  fetch(POST, {credentials:"include"})│
│         ↓ ReadableStream            │
│  TextDecoder → Line Buffer          │
│         ↓ SSE Parser                │
│  ┌─────────────┬──────────────┐     │
│  │ type:"step"  │type:"generation"│  │
│  │     ↓        │      ↓         │  │
│  │ steps[]      │ generation str │  │
│  │ Thought Panel│ Synthesis Doc  │  │
│  └─────────────┴──────────────┘     │
└─────────────────────────────────────┘
         ↑ HTTP POST + JSON body
         ↑ access_token cookie (HTTP-only)
┌─────────────────────────────────────┐
│    FastAPI Streaming Endpoint       │
│    POST /api/v1/agent/query         │
│    Content-Type: text/event-stream  │
│                                     │
│  crag_agent.astream(state, "updates")│
│         ↓ per-node state diffs      │
│  AgentStepEvent JSON lines          │
└─────────────────────────────────────┘
```

### SSE Event Contract (from Backend)

Each SSE line: `data: {"type":"<type>","node":"<node>","message":"<msg>","content":"<content>"}\n\n`

| Event Type     | `node`        | `message`                          | `content`        | UI Target              |
|:---------------|:--------------|:-----------------------------------|:-----------------|:-----------------------|
| `"step"`       | Node name     | Human-readable log string          | `null`           | Thought Inspection     |
| `"generation"` | `"generate"`  | `null`                             | Full MD string   | Synthesis Document     |
| `"done"`       | `null`        | `null`                             | `null`           | Finalize loading state |
| `"error"`      | `null`        | Error description                  | `null`           | Error display          |

### Design System Enforcement (from Design.md)

| Element               | Font             | Color / Background                      | Rule                          |
|:----------------------|:-----------------|:----------------------------------------|:------------------------------|
| Report Prose          | Newsreader serif | `#111111` on `#F7F7F5`                 | No chatbot bubbles            |
| Financial Tables      | JetBrains Mono   | `#111111`, `1px solid` borders         | Zero border-radius            |
| Thought Panel         | JetBrains Mono   | `#F7F7F5` on `#111111` (inverted)      | Terminal aesthetic             |
| Active Node Indicator | JetBrains Mono   | Mustard `#E5A823`                       | Sparingly; max impact          |
| Headers / Labels      | Geist sans-serif | `#111111`                               | Stark, geometric              |
| Action Symbols        | Any              | ASCII only: `→`, `//`, `[ ]`, `■`, `▶` | Zero icon libraries            |

---

### Sub-Phase 4.1: TypeScript Types & SSE Stream Client

**Goal:** Define the TypeScript type contract and build a reusable SSE stream reader in `frontend/src/lib/`.

**Files:**
- `[NEW] frontend/src/types/agent.ts` — TypeScript interfaces:
  ```typescript
  interface AgentQueryRequest {
    question: string;
    ticker?: string;
    fiscal_year?: number;
  }

  interface AgentStepEvent {
    type: "step" | "generation" | "done" | "error";
    node: string | null;
    message: string | null;
    content: string | null;
  }
  ```

- `[MODIFY] frontend/src/lib/api.ts` — Add `streamAgentQuery()`:
  - Uses `fetch(url, { method: "POST", credentials: "include", body: JSON.stringify(request) })`.
  - Returns an async iterator / callback-based API that yields parsed `AgentStepEvent` objects.
  - Implements SSE line buffering: reads `response.body.getReader()`, decodes via `TextDecoder`, splits on `\n\n`, strips `data: ` prefix, and `JSON.parse` each event.
  - Supports `AbortController` for user-initiated cancellation.
  - Handles HTTP error responses (401 → redirect to login, 422 → validation error display).

**Verification Checkpoint:**
- Write a manual test: call `streamAgentQuery` against the running FastAPI backend with a valid session cookie.
- Verify that the console logs each parsed `AgentStepEvent` in sequence: multiple `step` events → one `generation` event → one `done` event.
- Verify that passing an invalid/expired cookie returns a 401 and the function throws `ApiError`.

---

### Sub-Phase 4.2: React State Management Hook (`useAgentStream`)

**Goal:** Encapsulate all streaming state and side-effect logic into a single custom React hook.

**File:** `[NEW] frontend/src/hooks/useAgentStream.ts`

**State Shape:**
```typescript
interface AgentStreamState {
  status: "idle" | "streaming" | "complete" | "error";
  steps: AgentStepEvent[];        // Accumulated thought log
  activeNode: string | null;       // Currently executing node name
  generation: string | null;       // Final markdown content
  error: string | null;            // Error message if failed
  elapsedMs: number;               // Wall-clock execution time
}
```

**Returned Interface:**
```typescript
interface UseAgentStreamReturn {
  state: AgentStreamState;
  submitQuery: (req: AgentQueryRequest) => void;
  cancelQuery: () => void;
  resetState: () => void;
}
```

**Implementation Details:**
- `submitQuery` transitions `status` from `"idle"` → `"streaming"`, clears previous results, starts a timer, and calls `streamAgentQuery()`.
- Each `"step"` event appends to `steps[]` and updates `activeNode`.
- The `"generation"` event sets `generation`.
- `"done"` transitions to `"complete"`, stops the timer.
- `"error"` transitions to `"error"`, captures `message`.
- `cancelQuery` calls `abortController.abort()` and transitions to `"idle"`.
- `resetState` clears all state back to initial values.
- Uses `useRef` for `AbortController` to avoid stale closure issues.
- Uses `useCallback` for stable function references.

**Verification Checkpoint:**
- Build a minimal test harness component that renders `state.status`, `state.steps.length`, and `state.generation?.length`.
- Mock the streaming client to emit 5 step events, 1 generation event, and 1 done event with 200ms delays.
- Verify the component re-renders with correct state at each transition: `idle → streaming → complete`.
- Verify `cancelQuery()` mid-stream transitions to `idle` and stops accumulating events.

---

### Sub-Phase 4.3: Agent Dashboard Layout (Shell & Query Bar)

**Goal:** Transform the static `dashboard/page.tsx` placeholder into the active Analyst Workspace with a query input bar and a dual-panel layout.

**Files:**
- `[MODIFY] frontend/src/app/dashboard/page.tsx` — Restructure layout.
- `[NEW] frontend/src/components/QueryBar.tsx` — Query input form.

**Layout Architecture:**
```
┌──────────────────────────────────────────────────────────────┐
│ HEADER: CRAG-SEC // ANALYST WORKSPACE // [analyst@email] [Log Out] │
├──────────────────────────────────────────────────────────────┤
│ QUERY BAR:                                                    │
│ ┌──────────────────────────────┬──────────┬──────┬─────────┐ │
│ │ [Analyst Question...]         │ Ticker   │ Year │ [SUBMIT]│ │
│ └──────────────────────────────┴──────────┴──────┴─────────┘ │
├───────────────────────────────┬──────────────────────────────┤
│ THOUGHT INSPECTION PANEL      │ SYNTHESIS DOCUMENT            │
│ (Sub-Phase 4.4)               │ (Sub-Phase 4.5)               │
│ bg-[#111111] font-mono        │ bg-[#F7F7F5] font-serif       │
│ ~30% width                    │ ~70% width                    │
└───────────────────────────────┴──────────────────────────────┘
```

**QueryBar Design Rules:**
- Question input: `<textarea>` with serif font (Newsreader), placeholder `"What was Apple's total net sales in FY 2023?"`.
- Ticker input: `<input>` with mono font, uppercase transform, max 10 chars, placeholder `"AAPL"`.
- Fiscal Year input: `<input type="number">` with mono font, placeholder `"2023"`.
- Submit button: Stark black button, all-caps Geist sans, text `[ EXECUTE QUERY ]`. Disabled when `status === "streaming"`.
- No icons anywhere. Use `//` separators, `[ ]` bracket notation, and `→` arrows.
- All inputs: sharp 1px `#1A1A1A` borders, zero border-radius, no box shadows.

**Verification Checkpoint:**
- Run `npm run dev` and navigate to `/dashboard`.
- Verify the layout renders with the header, query bar, and two empty panels.
- Verify the form validation: submit is disabled with empty question, ticker enforces uppercase, fiscal year enforces numeric range.
- Verify the brutalist aesthetic matches Design.md: zero rounded corners, no icons, correct fonts.

---

### Sub-Phase 4.4: Thought Inspection Panel Component

**Goal:** Build the real-time terminal panel that displays state machine step events as they stream in.

**File:** `[NEW] frontend/src/components/ThoughtPanel.tsx`

**Design:**
- Dark terminal aesthetic: `bg-[#111111]`, text `#F7F7F5`, `font-mono` (JetBrains Mono).
- Each step event renders as a log line: `>> [NODE_NAME] message_text`.
- The active node (currently executing) is highlighted with mustard `#E5A823`.
- Completed nodes show a static `■` prefix. Active node shows a pulsing `▶` prefix (CSS animation, no JS).
- Auto-scrolls to bottom on new step events.
- When `status === "idle"`, shows: `// AWAITING ANALYST QUERY`.
- When `status === "complete"`, shows a final summary line: `// EXECUTION COMPLETE — {elapsed}s — {steps.length} NODES TRAVERSED`.

**State Machine Visual Sequence Example:**
```
// CRAG AGENT — THOUGHT INSPECTION LOG
// ————————————————————————————

■ [RETRIEVE] Found 10 chunks from Supabase (ticker=AAPL, year=2023).
■ [GRADE_DOCUMENTS] Evaluated 10 chunks: 7 relevant, 3 discarded. Web search not needed.
■ [TOOL_DECISION] Math not required — figures explicitly stated.
▶ [GENERATE] Synthesizing response from Audited SEC 10-K Filings...

// EXECUTION COMPLETE — 30.83s — 4 NODES TRAVERSED
```

**Verification Checkpoint:**
- Pass a mocked `steps[]` array with 4 events and `status="complete"` as props.
- Verify each step renders on its own line with the correct prefix (`■` for complete, `▶` for active).
- Verify mustard accent on the active node.
- Verify auto-scroll behavior when new steps are appended.

---

### Sub-Phase 4.5: Markdown Rendering & Synthesis Document

**Goal:** Render the `generation` Markdown string as a styled editorial financial report.

**Dependencies (Require User Approval):**
- `react-markdown` — AST-based Markdown-to-React renderer.
- `remark-gfm` — GitHub Flavored Markdown plugin (pipe tables, strikethrough, autolinks).

**File:** `[NEW] frontend/src/components/SynthesisDocument.tsx`

**Component Override Map (react-markdown `components` prop):**

| Markdown Element | React Override                                               |
|:-----------------|:-------------------------------------------------------------|
| `## Heading`     | `<h2 className="font-sans text-lg font-bold border-b border-dark ...">` |
| `**bold**`       | `<strong className="font-semibold">`                         |
| `| table |`      | `<table className="font-mono text-sm w-full border border-dark">` |
| `<th>`           | `<th className="bg-dark text-parchment font-mono px-3 py-2 text-left border border-dark">` |
| `<td>`           | `<td className="font-mono px-3 py-2 border border-dark">`   |
| `` `code` ``     | `<code className="font-mono bg-parchment-subtle px-1">`     |
| ```` ```python ```` | `<pre className="bg-dark text-parchment font-mono p-4 overflow-x-auto">` |
| `<p>`            | `<p className="font-serif text-base leading-relaxed mb-4">` |
| `<li>`           | `<li className="font-serif ml-6 list-disc">`                |

**Behavior:**
- When `status === "idle"`: Shows editorial placeholder text: `"Submit an analyst query to generate a due-diligence synthesis report."`
- When `status === "streaming"` and no `generation` yet: Shows `"// SYNTHESIZING REPORT..."` in mono.
- When `generation` arrives: Renders full Markdown with component overrides.
- When `status === "error"`: Shows typographic error message in serif, red accent.

**Verification Checkpoint:**
- Pass a sample Markdown string containing `##` headers, a `|` pipe table, `**bold**` metrics, and a ` ```python ``` ` code block.
- Verify the table renders with monospace font, dark header row, and square-cornered borders.
- Verify prose renders in Newsreader serif.
- Verify code blocks render in JetBrains Mono with dark background.
- Verify zero icons, zero rounded corners, zero gradients.

---

### Sub-Phase 4.6: Integration Wiring & Error Boundaries

**Goal:** Wire `useAgentStream` into the dashboard, connect QueryBar → Hook → Panels, and add resilient error handling.

**Files:**
- `[MODIFY] frontend/src/app/dashboard/page.tsx` — Final wiring.
- `[NEW] frontend/src/components/ErrorBoundary.tsx` — Graceful error display.

**Wiring Flow:**
```
QueryBar.onSubmit(question, ticker, year)
  → useAgentStream.submitQuery({ question, ticker, fiscal_year })
    → streamAgentQuery(request) via fetch POST
      → SSE events parsed and dispatched to state
        → ThoughtPanel receives state.steps, state.activeNode, state.status
        → SynthesisDocument receives state.generation, state.status
```

**Error Handling Matrix:**
| Error Scenario                     | UI Response                                                   |
|:-----------------------------------|:--------------------------------------------------------------|
| 401 Unauthorized (expired cookie)  | Redirect to `/login?redirect=/dashboard`                      |
| 422 Validation Error               | Display inline form error below QueryBar                      |
| Network failure (fetch rejected)   | Display typographic error in SynthesisDocument area            |
| SSE `type: "error"` event          | Display agent error message in both panels                    |
| Stream interrupted mid-execution   | Show partial results + `"// STREAM INTERRUPTED"` in panel     |
| React component crash              | `ErrorBoundary` catches and renders fallback UI               |

**Verification Checkpoint (Full Integration):**
1. Start FastAPI backend: `uvicorn backend.app.main:app --reload`.
2. Start Next.js dev server: `npm run dev`.
3. Log in via magic link → redirected to `/dashboard`.
4. Submit query: `"What was Apple's total net sales in 2023?"` with Ticker `AAPL`, Year `2023`.
5. Verify real-time step events populate the Thought Inspection Panel.
6. Verify the final Markdown response renders as a styled editorial report with tables.
7. Verify error handling: kill the backend mid-stream and confirm graceful error display.

---

### Frontend File Structure After Phase 4

```
frontend/src/
├── app/
│   ├── layout.tsx
│   ├── globals.css
│   ├── page.tsx              (Landing)
│   ├── login/page.tsx        (Login)
│   ├── auth/verify/page.tsx  (Magic Link Verify)
│   └── dashboard/
│       └── page.tsx          (Agent Workspace — MODIFIED)
├── components/
│   ├── QueryBar.tsx          (NEW)
│   ├── ThoughtPanel.tsx      (NEW)
│   ├── SynthesisDocument.tsx (NEW)
│   └── ErrorBoundary.tsx     (NEW)
├── hooks/
│   └── useAgentStream.ts     (NEW)
├── lib/
│   └── api.ts                (MODIFIED — add streamAgentQuery)
├── types/
│   ├── auth.ts
│   └── agent.ts              (NEW)
├── context/
│   └── AuthContext.tsx
└── middleware.ts
```

---

## 8. Active Scratchpad & Working Notes
- Strict adherence to [Design.md](file:///d:/build/Financial%20CRAG/docs/Design.md) and [Rules.md](file:///d:/build/Financial%20CRAG/docs/Rules.md).
- Any architectural pivots or dependency selections must be logged to [decision_log.md](file:///d:/build/Financial%20CRAG/docs/decision_log.md).
- `pgvector` extension already enabled in `001_auth_schema.sql` — no need to re-enable in `002_sec_vector_schema.sql`.
- LlamaParse free tier: 10,000 credits/month (1 credit/page on Fast mode). Sufficient for portfolio development.
- BGE v1.5 query instruction: `"Represent this sentence for searching relevant passages: "` — documents get NO prefix.
- SEC EDGAR requires compliant User-Agent or returns 403. Max 10 req/s per IP.
- Groq on-demand tier: `qwen/qwen3.8-27b` with strict `max_tokens` budgets per node (800 default). Adequate for dev/test.
- Tavily free tier: 1,000 searches/month. Sufficient for development and demo.
- Python REPL sandbox: AST-validated (no imports, no dunder access), restricted builtins, stdout capture.
- Phase 4 dependencies pending user approval: `react-markdown`, `remark-gfm`.

