-- ==============================================================================
-- Migration: 002_sec_vector_schema.sql
-- Description: SEC filings registry, chunks with vector(384) embeddings,
--              HNSW cosine index, and match_sec_chunks search RPC function.
-- Model: BAAI/bge-small-en-v1.5 (384 dimensions)
-- ==============================================================================

-- 1. Ensure Vector Extension is enabled (also initialized in 001)
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. SEC Filings Registry Table
CREATE TABLE IF NOT EXISTS public.sec_filings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(10) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    form_type VARCHAR(20) NOT NULL DEFAULT '10-K',
    fiscal_year INTEGER NOT NULL,
    fiscal_period VARCHAR(10) NOT NULL DEFAULT 'FY',
    accession_number VARCHAR(30) UNIQUE NOT NULL,
    filing_date DATE DEFAULT NULL,
    source_url TEXT DEFAULT NULL,
    parse_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    total_chunks INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for sec_filings
CREATE INDEX IF NOT EXISTS idx_sec_filings_ticker ON public.sec_filings (ticker);
CREATE INDEX IF NOT EXISTS idx_sec_filings_fiscal_year ON public.sec_filings (fiscal_year);
CREATE INDEX IF NOT EXISTS idx_sec_filings_ticker_year ON public.sec_filings (ticker, fiscal_year);
CREATE INDEX IF NOT EXISTS idx_sec_filings_accession ON public.sec_filings (accession_number);
CREATE INDEX IF NOT EXISTS idx_sec_filings_status ON public.sec_filings (parse_status);

-- Attach updated_at trigger to sec_filings
DROP TRIGGER IF EXISTS set_sec_filings_updated_at ON public.sec_filings;
CREATE TRIGGER set_sec_filings_updated_at
BEFORE UPDATE ON public.sec_filings
FOR EACH ROW
EXECUTE FUNCTION public.handle_updated_at();

-- 3. SEC Document Chunks Table with Vector(384)
CREATE TABLE IF NOT EXISTS public.sec_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filing_id UUID NOT NULL REFERENCES public.sec_filings(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    section_title VARCHAR(500) DEFAULT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding VECTOR(384) NOT NULL,
    token_count INTEGER DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Unique index to enforce idempotency per chunk per filing
CREATE UNIQUE INDEX IF NOT EXISTS idx_sec_chunks_filing_chunk_idx ON public.sec_chunks (filing_id, chunk_index);

-- B-Tree index for section and filing filtering
CREATE INDEX IF NOT EXISTS idx_sec_chunks_filing_id ON public.sec_chunks (filing_id);
CREATE INDEX IF NOT EXISTS idx_sec_chunks_filing_section ON public.sec_chunks (filing_id, section_title);

-- 4. HNSW Vector Index (Hierarchical Navigable Small World)
-- Using vector_cosine_ops for normalized BGE-small embeddings
-- Parameters: m = 16 (bi-directional links), ef_construction = 64 (construction search depth)
CREATE INDEX IF NOT EXISTS idx_sec_chunks_embedding_hnsw
ON public.sec_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 5. Row Level Security (RLS) Configuration
ALTER TABLE public.sec_filings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sec_chunks ENABLE ROW LEVEL SECURITY;

-- 6. Grant Table and Sequence Permissions to service_role
GRANT ALL ON TABLE public.sec_filings TO service_role;
GRANT ALL ON TABLE public.sec_chunks TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;

-- 7. High-Performance Filtered Vector Match RPC Function
-- Pre-filters by ticker and/or fiscal_year before vector similarity ordering (<=>)
CREATE OR REPLACE FUNCTION public.match_sec_chunks(
    query_embedding vector(384),
    match_threshold float DEFAULT 0.0,
    match_count int DEFAULT 10,
    filter_ticker varchar DEFAULT NULL,
    filter_fiscal_year int DEFAULT NULL
)
RETURNS TABLE (
    id uuid,
    filing_id uuid,
    ticker varchar,
    company_name varchar,
    fiscal_year int,
    chunk_index int,
    section_title varchar,
    content text,
    metadata jsonb,
    similarity float
)
AS $$
BEGIN
    RETURN QUERY
    WITH target_filings AS (
        SELECT sf.id, sf.ticker, sf.company_name, sf.fiscal_year
        FROM public.sec_filings sf
        WHERE (filter_ticker IS NULL OR sf.ticker = filter_ticker)
          AND (filter_fiscal_year IS NULL OR sf.fiscal_year = filter_fiscal_year)
    )
    SELECT
        sc.id,
        sc.filing_id,
        tf.ticker,
        tf.company_name,
        tf.fiscal_year,
        sc.chunk_index,
        sc.section_title,
        sc.content,
        sc.metadata,
        (1 - (sc.embedding <=> query_embedding))::float AS similarity
    FROM public.sec_chunks sc
    JOIN target_filings tf ON tf.id = sc.filing_id
    WHERE (1 - (sc.embedding <=> query_embedding)) >= match_threshold
    ORDER BY sc.embedding <=> query_embedding ASC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql STABLE;

-- Grant execute permissions on RPC function
GRANT EXECUTE ON FUNCTION public.match_sec_chunks TO service_role;
GRANT EXECUTE ON FUNCTION public.match_sec_chunks TO authenticated;
GRANT EXECUTE ON FUNCTION public.match_sec_chunks TO anon;
