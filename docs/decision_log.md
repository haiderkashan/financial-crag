# Decision Log

_This file tracks the "Why" behind technical choices made during development._

## [Date: Current] Pivot from Streamlit to Next.js/FastAPI/Supabase

**Context:** Initially considered Streamlit for the UI and local ChromaDB for vector storage.
**Decision:** Shifted to Next.js (frontend), FastAPI (backend), and Supabase (pgvector).
**Rationale:** To elevate the project from a "portfolio script" to a "production-grade product," a decoupled architecture is required. Next.js allows for the strict, bespoke typographic design we want, while Supabase provides persistent, scalable vector storage and database functionality.
