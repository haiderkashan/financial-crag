# System Architecture

## 1. High-Level Stack

- **Frontend:** Next.js (React), styled with custom CSS/Tailwind (adhering strictly to Design.md). Hosted on Vercel.
- **Auth:** Custom SMTP & JWT Authentication (FastAPI security, passwordless magic links/OTP via SMTP, secure sessions & token revocation stored in Supabase PostgreSQL).
- **Backend (API & AI):** Python FastAPI.
- **Database & Vector Store:** Supabase (PostgreSQL with `pgvector` extension).
- **AI Orchestration:** LangGraph (Python).
- **LLM/Embeddings:** Groq (Llama-3.3-70B) or OpenAI API; local sentence-transformers for embeddings.
- **External Tools:** LlamaParse (Ingestion), Tavily (Search), Python REPL (Math).

## 2. Decoupled Flow

1. **Client:** User sends a query or logs in via the Next.js UI.
2. **Gateway / Auth:** Next.js communicates with FastAPI for custom SMTP passwordless magic-link verification and receives cryptographically signed JWTs (HTTP-only cookies / Bearer headers). Protected requests are verified against FastAPI auth dependencies and Supabase user state.
3. **Agent (LangGraph):**
   - Embeds the query and searches Supabase `pgvector`.
   - Grades the chunks.
   - Loops through Tools (Search, REPL) if needed.
   - Generates the final markdown response.
4. **Streaming:** FastAPI streams the thought process and final response back to the Next.js UI.

## 3. Directory Structure

```
/
├── frontend/                    # Next.js Application
│   ├── app/                     # Next.js App Router
│   ├── components/              # UI Components
│   └── lib/                     # Frontend utilities
├── backend/                     # FastAPI Application
│   ├── app/
│   │   ├── api/                 # API Routes (v1/health, v1/auth)
│   │   ├── core/                # Config, Security, Prompts
│   │   ├── db/                  # Supabase client & repositories
│   │   ├── models/              # Pydantic schemas
│   │   ├── services/            # Email service, business logic
│   │   ├── ingestion/           # Phase 2: Data Ingestion Pipeline
│   │   │   ├── sec_client.py    # SEC EDGAR API downloader
│   │   │   ├── parser.py        # LlamaParse PDF-to-Markdown
│   │   │   ├── chunker.py       # Structure-aware chunking
│   │   │   ├── embedder.py      # Sentence-transformer encoder
│   │   │   └── pipeline.py      # End-to-end orchestrator
│   │   ├── agent/               # Phase 3: LangGraph State, Nodes, Edges
│   │   └── tools/               # Phase 3: Python REPL, Web Search
│   ├── migrations/              # SQL migration files
│   ├── scripts/                 # Test & utility scripts
│   └── tests/                   # Pytest test suites
├── data/                        # Local filing cache (gitignored)
│   └── filings/                 # Downloaded SEC 10-K documents
└── docs/                        # Project Blueprints & Memory
```

## 4. Data Ingestion Pipeline Flow (Phase 2)

```
SEC EDGAR API                     LlamaParse API
     │                                  │
     ▼                                  │
┌──────────┐    ┌──────────┐    ┌───────┴──────┐
│ Download │───▶│ Raw PDF/ │───▶│   Parse to   │
│ 10-K     │    │ HTM File │    │   Markdown   │
└──────────┘    └──────────┘    └──────┬───────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │ Structure-Aware │
                              │   Chunking      │
                              │ (Header + Table)│
                              └───────┬────────┘
                                      │
                                      ▼
                              ┌────────────────┐
                              │ BGE Embedding  │
                              │ (384d, Local)  │
                              └───────┬────────┘
                                      │
                                      ▼
                              ┌────────────────┐
                              │ Supabase       │
                              │ pgvector Store │
                              │ (HNSW Index)   │
                              └────────────────┘
```
