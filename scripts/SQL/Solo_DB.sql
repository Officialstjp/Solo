-- Role: "Stjp"
-- DROP ROLE IF EXISTS "Stjp";

-- Role: admins
-- DROP ROLE IF EXISTS admins;

-- Application role with appropriate privileges
CREATE ROLE solo_app_role NOLOGIN;
GRANT USAGE, CREATE ON SCHEMA public TO solo_app_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO solo_app_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO solo_app_role;

-- Application user
CREATE USER solo_app WITH PASSWORD '${POSTGRES_PASSWORD}';
GRANT solo_app_role TO solo_app;

CREATE ROLE "Stjp" WITH
  LOGIN
  SUPERUSER
  INHERIT
  CREATEDB
  CREATEROLE
  REPLICATION
  BYPASSRLS
  PASSWORD '${POSTGRES_ADMPASSWORD}';

GRANT admins TO "Stjp" WITH ADMIN OPTION;

CREATE TABLE system_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cpu_percent FLOAT,
    cpu_temperature FLOAT,
    memory_percent FLOAT,
    memory_used_mb FLOAT,
    memory_temperature FLOAT,
    gpu_percent FLOAT,
    gpu_fans_rpm FLOAT,
    gpu_watt FLOAT,
    vram_percent FLOAT,
    vram_used_mb FLOAT,
    system_uptime_seconds FLOAT,
    app_uptime_seconds FLOAT
);

-- For time-series partitioning
CREATE INDEX idx_system_metrics_timestamp ON system_metrics(timestamp);

CREATE TABLE llm_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255),
    request_id VARCHAR(255) NOT NULL,
    tokens_generated INTEGER NOT NULL,
    generation_time_ms FLOAT NOT NULL,
    tokens_per_second FLOAT,
    cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
    prompt_tokens INTEGER,
    total_tokens INTEGER,
    parameters JSONB  -- Store generation parameters (temperature, top_p, etc.)
);

CREATE INDEX idx_llm_metrics_timestamp ON llm_metrics(timestamp);
CREATE INDEX idx_llm_metrics_model_id ON llm_metrics(model_id);
CREATE INDEX idx_llm_metrics_session_id ON llm_metrics(session_id);

CREATE TABLE daily_metrics_summary (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    total_requests INTEGER NOT NULL DEFAULT 0,
    total_tokens_generated BIGINT NOT NULL DEFAULT 0,
    avg_tokens_per_second FLOAT,
    avg_response_time_ms FLOAT,
    cache_hits INTEGER NOT NULL DEFAULT 0,
    cache_misses INTEGER NOT NULL DEFAULT 0,
    most_used_model VARCHAR(255),
    peak_cpu_percent FLOAT,
    peak_memory_percent FLOAT,
    peak_gpu_percent FLOAT
);

CREATE TABLE models (
    id SERIAL PRIMARY KEY,
    model_id VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    format VARCHAR(50) NOT NULL,  -- MISTRAL, LLAMA3, PHI, etc.
    parameter_size VARCHAR(20) NOT NULL, -- 7B, 13B, etc.
    quantization VARCHAR(20) NOT NULL, -- Q4_0, Q5_K_M, etc.
    context_length INTEGER NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    file_size_mb FLOAT NOT NULL,
    first_added TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used TIMESTAMPTZ,
    metadata JSONB,  -- Additional model metadata
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_models_format ON models(format);
CREATE INDEX idx_models_parameter_size ON models(parameter_size);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active TIMESTAMPTZ,
    preferences JSONB  -- User preferences
);

CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(255) REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active, closed
    metadata JSONB  -- Session metadata
);

CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(255) NOT NULL UNIQUE,
    session_id VARCHAR(255) NOT NULL REFERENCES sessions(session_id),
    title VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    summary TEXT,  -- AI-generated summary of the conversation
    metadata JSONB  -- Additional conversation metadata
);

CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(255) NOT NULL UNIQUE,
    conversation_id VARCHAR(255) NOT NULL REFERENCES conversations(conversation_id),
    role VARCHAR(50) NOT NULL,  -- user, assistant, system
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model_id VARCHAR(255),  -- Which model generated this (if assistant)
    request_id VARCHAR(255),  -- For linking to metrics
    tokens INTEGER,
    metadata JSONB  -- Additional message metadata
);

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);

-- Requires pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255) NOT NULL UNIQUE,
    title VARCHAR(255),
    content TEXT NOT NULL,
    source VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB
);

CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255) NOT NULL REFERENCES documents(doc_id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),  -- Adjust dimension based on embedding model
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB,
    UNIQUE(doc_id, chunk_index)
);

-- Index for vector similarity search
CREATE INDEX idx_document_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops);

CREATE TABLE response_cache (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR(255) NOT NULL UNIQUE,
    prompt TEXT NOT NULL,
    parameters JSONB NOT NULL,
    response TEXT NOT NULL,
    metrics JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_response_cache_expires_at ON response_cache(expires_at);
