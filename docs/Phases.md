# Project Phases

**Rule for AI:** Do not proceed to the next phase until the current phase is fully complete, tested, and approved by the user.

- **Phase 1: Foundation & Custom Auth**
  - Scaffold Next.js (frontend) and FastAPI (backend).
  - Build custom SMTP & JWT authentication system.
  - Setup Supabase database connection and user/session schema.
- **Phase 2: Data Ingestion Pipeline (Backend)**
  - Create the script to download 10-K filings.
  - Process PDFs through LlamaParse.
  - Chunk data and store embeddings in Supabase `pgvector`.
- **Phase 3: The CRAG Agent (Backend)**
  - Define the LangGraph State graph.
  - Build nodes: Retrieve, Grade, Web Search (Tavily), Math (Python REPL), Generate.
  - Test the agent locally via FastAPI Swagger/Postman.
- **Phase 4: API & Streaming Integration**
  - Connect the Next.js frontend to the FastAPI backend.
  - Implement streaming for both the AI's "thought process" and the final text.
- **Phase 5: UI/UX & Bespoke Aesthetic**
  - Implement the strict design guidelines (no icons, bespoke typography).
  - Build the "Thought Inspection" UI panel for the agent.
