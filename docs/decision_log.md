# Decision Log

_This file tracks the "Why" behind technical choices made during development._

## [Date: Current] Pivot from Streamlit to Next.js/FastAPI/Supabase

**Context:** Initially considered Streamlit for the UI and local ChromaDB for vector storage.
**Decision:** Shifted to Next.js (frontend), FastAPI (backend), and Supabase (pgvector).
**Rationale:** To elevate the project from a "portfolio script" to a "production-grade product," a decoupled architecture is required. Next.js allows for the strict, bespoke typographic design we want, while Supabase provides persistent, scalable vector storage and database functionality.

## [Date: Current] Architecture Pivot: Dropping Clerk in Favor of Custom SMTP & JWT Authentication

**Context:** The initial architectural draft included Clerk for third-party user authentication.
**Decision:** Dropped Clerk entirely. Transitioned to a custom-engineered authentication system using FastAPI security (JWT access/refresh tokens), asynchronous transactional SMTP for email verification / passwordless magic links, and Supabase PostgreSQL for user state and token lifecycle management.
**Rationale:** Third-party auth providers (like Clerk) abstract away core security and protocol handling. Building authentication from scratch directly demonstrates deep backend engineering, distributed security principles, cryptographic token handling, and transactional email infrastructure—elevating this project into an enterprise-grade showcase without external vendor lock-in.
