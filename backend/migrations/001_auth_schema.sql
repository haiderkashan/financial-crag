-- ==============================================================================
-- Migration: 001_auth_schema.sql
-- Description: Core schema for custom SMTP & JWT authentication and pgvector
-- Extensions: vector, uuid-ossp, pgcrypto
-- ==============================================================================

-- 1. Enable Required Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector"; -- Vector embeddings readiness for Phase 2 CRAG

-- 2. Users Table
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast user lookup by email
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users (email);

-- 3. Auth Tokens Table (for Magic Links & Refresh Tokens)
CREATE TABLE IF NOT EXISTS public.auth_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL, -- SHA-256 hex digest
    token_type VARCHAR(32) NOT NULL, -- 'magic_link' | 'refresh_token'
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Composite index for fast token verification and lookup
CREATE INDEX IF NOT EXISTS idx_auth_tokens_hash_type ON public.auth_tokens (token_hash, token_type);
CREATE INDEX IF NOT EXISTS idx_auth_tokens_user_id ON public.auth_tokens (user_id);
CREATE INDEX IF NOT EXISTS idx_auth_tokens_expires_at ON public.auth_tokens (expires_at);

-- 4. Timestamp Trigger Function
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Attach Trigger to Users Table
DROP TRIGGER IF EXISTS set_users_updated_at ON public.users;
CREATE TRIGGER set_users_updated_at
BEFORE UPDATE ON public.users
FOR EACH ROW
EXECUTE FUNCTION public.handle_updated_at();

-- 5. Row Level Security (RLS) Configuration
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.auth_tokens ENABLE ROW LEVEL SECURITY;

-- Note: The FastAPI backend connects via the Supabase Service Role Key,
-- which bypasses RLS by default. Explicit policies can be layered as needed.

-- 6. Grant Table Permissions to service_role
GRANT ALL ON TABLE public.users TO service_role;
GRANT ALL ON TABLE public.auth_tokens TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
