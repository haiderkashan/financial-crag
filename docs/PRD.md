# Project Requirements Document (PRD)

**Project:** Financial SEC Due-Diligence CRAG Agent

## 1. Vision & Purpose

This application is a production-grade AI financial analyst tool designed to assist human analysts in extracting, calculating, and verifying data from complex SEC 10-K filings. While serving as a functional product, it also acts as a flagship portfolio piece demonstrating enterprise-grade AI engineering.

## 2. Target Audience

- **Primary:** Financial analysts, equity researchers, and retail investors needing deep dives into company financials.
- **Secondary:** Hiring managers and Senior AI Engineers reviewing the architecture for robust failure-handling and production readiness.

## 3. Core Problems Addressed

- **Tabular Data Destruction:** Overcoming standard RAG limitations by utilizing LlamaParse for structure-aware parsing of financial tables.
- **Arithmetic Hallucination:** Preventing LLMs from guessing math by routing numerical queries to a sandboxed Python REPL execution tool.
- **Silent Retrieval Failures:** Implementing Corrective RAG (CRAG) with LangGraph to grade retrieved context and trigger Tavily web search fallbacks when internal documents lack the answer.

## 4. Key Features

- **Custom User Authentication:** Bespoke passwordless / email-verified auth system utilizing transactional SMTP (for magic links & verification codes), cryptographic JWT tokens (access and refresh pairs), and Supabase PostgreSQL for user state and token revocation—eliminating vendor lock-in and proving deep backend security competence.
- **SEC 10-K Ingestion Pipeline:** Asynchronous pre-processing pipeline that sources filings from SEC EDGAR API, parses PDFs via LlamaParse (preserving financial tables as Markdown), applies structure-aware chunking, generates local embeddings (`BAAI/bge-small-en-v1.5`, 384d), and upserts into Supabase `pgvector` with HNSW indexing — demonstrating production-grade ETL engineering.
- **Chat Interface:** A highly customized, typographic-first chat UI.
- **Thought Inspection Panel:** A dedicated UI section exposing the agent's internal state machine (e.g., "Evaluating Context -> Irrelevant -> Triggering Web Search -> Executing Math").
- **Persistent History:** User sessions and chat histories saved securely in Supabase.
