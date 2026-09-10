# System Architecture

## 1. High-Level Stack

- **Frontend:** Next.js (React), styled with custom CSS/Tailwind (adhering strictly to Design.md). Hosted on Vercel.
- **Auth:** Clerk.
- **Backend (API & AI):** Python FastAPI.
- **Database & Vector Store:** Supabase (PostgreSQL with `pgvector` extension).
- **AI Orchestration:** LangGraph (Python).
- **LLM/Embeddings:** Groq (Llama-3.3-70B) or OpenAI API; local sentence-transformers for embeddings.
- **External Tools:** LlamaParse (Ingestion), Tavily (Search), Python REPL (Math).

## 2. Decoupled Flow

1. **Client:** User sends a query via the Next.js UI.
2. **Gateway:** Next.js API routes validate the user via Clerk and forward the request to the FastAPI backend.
3. **Agent (LangGraph):**
   - Embeds the query and searches Supabase `pgvector`.
   - Grades the chunks.
   - Loops through Tools (Search, REPL) if needed.
   - Generates the final markdown response.
4. **Streaming:** FastAPI streams the thought process and final response back to the Next.js UI.

## 3. Directory Structure

/
├── frontend/ # Next.js Application
│ ├── app/ # Next.js App Router
│ ├── components/ # UI Components
│ └── lib/ # Frontend utilities
├── backend/ # FastAPI Application
│ ├── api/ # API Routes
│ ├── agent/ # LangGraph State, Nodes, and Edges
│ ├── tools/ # Python REPL, Web Search
│ └── core/ # Config, Prompts
└── docs/ # Project Blueprints & Memory
