DROP ROLE IF EXISTS "stjp";
DROP ROLE IF EXISTS "solo_app";
DROP ROLE IF EXISTS "solo_app_role";
DROP ROLE IF EXISTS "solo_readonly";

-- Create schemas for logical organization
CREATE SCHEMA IF NOT EXISTS metrics;
CREATE SCHEMA IF NOT EXISTS models;
CREATE SCHEMA IF NOT EXISTS users;
CREATE SCHEMA IF NOT EXISTS rag;
CREATE SCHEMA IF NOT EXISTS security;

-- Application role with appropriate privileges
CREATE ROLE solo_app_role NOLOGIN;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO solo_app_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO solo_app_role;

-- Application user
CREATE USER "solo_app" WITH PASSWORD ${POSTGRES_APPPASSWORD};
GRANT solo_app_role TO "solo_app";

-- Adm user
CREATE ROLE "stjp" WITH
  LOGIN
  SUPERUSER
  INHERIT
  CREATEDB
  CREATEROLE
  REPLICATION
  BYPASSRLS
  PASSWORD ${POSTGRES_ADMPASSWORD};

-- Create read-only role for dashboards
CREATE ROLE solo_readonly NOLOGIN;
GRANT USAGE ON SCHEMA metrics TO solo_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA metrics TO solo_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA metrics
    GRANT SELECT ON TABLES TO solo_readonly;

-- Update role permissions to include new schemas
GRANT USAGE, CREATE ON SCHEMA metrics, models, users, rag TO solo_app_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA metrics, models, users, rag
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO solo_app_role;

-- System metrics with partitioning
CREATE TABLE metrics.system_metrics (
    id SERIAL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cpu_percent FLOAT,
    cpu_temperature FLOAT,
    memory_percent FLOAT,
    memory_used_mb FLOAT,
    memory_temperature FLOAT,
    gpu_percent FLOAT,
    gpu_fans_rpm FLOAT,
    gpu_watt FLOAT,
    gpu_temperature FLOAT,
    vram_percent FLOAT,
    vram_used_mb FLOAT,
    system_uptime_seconds FLOAT,
    app_uptime_seconds FLOAT
) PARTITION BY RANGE (timestamp);

--- Creat initial partitions (adjust dates as needed)
CREATE TABLE metrics.system_metrics_default PARTITION OF metrics.system_metrics DEFAULT;

CREATE TABLE metrics.system_metrics_y202507 PARTITION OF metrics.system_metrics
    FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');

CREATE TABLE metrics.system_metrics_y202508 PARTITION OF metrics.system_metrics
    FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');

-- Create index on the partition key
CREATE INDEX idx_system_metrics_timestamp ON metrics.system_metrics(timestamp);

-- LLM metrics with partitioning
CREATE TABLE metrics.llm_metrics (
    id SERIAL,
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
    parameters JSONB
) PARTITION BY RANGE (timestamp);

-- Create initial partitions (adjust dates as needed)
CREATE TABLE metrics.llm_metrics_default PARTITION OF metrics.llm_metrics DEFAULT;

CREATE TABLE metrics.llm_metrics_y202507 PARTITION OF metrics.llm_metrics
    FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');

CREATE TABLE metrics.llm_metrics_y202508 PARTITION OF metrics.llm_metrics
    FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');

-- Create indexes
CREATE INDEX idx_llm_metrics_timestamp ON metrics.llm_metrics(timestamp);
CREATE INDEX idx_llm_metrics_model_id ON metrics.llm_metrics(model_id);
CREATE INDEX idx_llm_metrics_session_id ON metrics.llm_metrics(session_id);

-- Daily metrics summary
CREATE TABLE metrics.daily_metrics_summary (
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

-- Models table in models schema
CREATE TABLE models.models (
    id SERIAL PRIMARY KEY,
    model_id VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    format VARCHAR(50) NOT NULL,
    parameter_size VARCHAR(20) NOT NULL,
    quantization VARCHAR(20) NOT NULL,
    context_length INTEGER NOT NULL,
    file_path VARCHAR (255) NOT NULL,
    file_size_mb FLOAT NOT NULL,
    first_added TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used TIMESTAMPTZ,
    metadata JSONB,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_models_format ON models.models(format);
CREATE INDEX idx_models_parameter_size ON models.models(parameter_size);

-- Users tables in users schema
CREATE TABLE users.users (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active TIMESTAMPTZ,
    preferences JSONB
);

CREATE TABLE users.sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(255) REFERENCES users.users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    metadata JSONB
);

CREATE TABLE users.conversations (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(255) NOT NULL UNIQUE,
    session_id VARCHAR(255) NOT NULL REFERENCES users.sessions(session_id),
    title VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    summary TEXT,
    metadata JSONB
);

CREATE TABLE users.messages (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(255) NOT NULL UNIQUE,
    conversation_id VARCHAR(255) NOT NULL REFERENCES users.conversations(conversation_id),
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model_id VARCHAR(255),
    request_id VARCHAR(255),
    tokens INTEGER,
    metadata JSONB
);

CREATE INDEX idx_messages_conversation_id ON users.messages(conversation_id);
CREATE INDEX idx_messages_created_at ON users.messages(created_at);

-- RAG components in rag schema
-- FIRST, ensure pgvector extension is available
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE rag.documents (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255) NOT NULL UNIQUE,
    title VARCHAR(255),
    content TEXT NOT NULL,
    source VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB
);

CREATE TABLE rag.document_chunks (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255) NOT NULL REFERENCES rag.documents(doc_id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB,
    UNIQUE(doc_id, chunk_index)
);

-- Index for vector similarity search
CREATE INDEX idx_document_chunks_embedding ON rag.document_chunks USING ivfflat (embedding vector_cosine_ops);

-- Response cache
CREATE TABLE metrics.response_cache (
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

CREATE INDEX idx_response_cache_expires_at ON metrics.response_cache(expires_at);
CREATE INDEX idx_response_cache_key_expires ON metrics.response_cache(cache_key, expires_at);


-- create tables for security schema
CREATE TABLE IF NOT EXISTS security.credentials (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL,
    password_hash TEXT NOT NULL,
    totp_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    totp_secret TEXT,
    last_password_change TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    account_locked BOOLEAN NOT NULL DEFAULT FALSE,
    account_locked_until TIMESTAMPTZ,
    password_reset_token TEXT,
    password_reset_expires TIMESTAMPTZ,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    security_level INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS security.password_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    password_hash TEXT NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS security.login_attempts (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255),
    username VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    user_agent TEXT,
    success BOOLEAN NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_login_attempts_username ON security.login_attempts(username);
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON security.login_attempts(ip_address);
CREATE INDEX IF NOT EXISTS idx_login_attempts_timestamp ON security.login_attempts(timestamp);

CREATE TABLE IF NOT EXISTS security.security_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    user_id VARCHAR(255),
    username VARCHAR(255),
    ip_address VARCHAR(45),
    user_agent TEXT,
    details JSONB,
    timestamp TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_security_events_user_id ON security.security_events(user_id);
CREATE INDEX IF NOT EXISTS idx_security_events_timestamp ON security.security_events(timestamp);

-- Create function to automatically generate new partitions
CREATE OR REPLACE FUNCTION metrics.create_partitions()
RETURNS VOID AS $$
DECLARE
    next_month DATE;
    partition_name_system TEXT;
    partition_name_llm TEXT;
    start_date TEXT;
    end_date TEXT;
BEGIN
    -- Calculate the first day of the next month
    next_month := date_trunc('month', now()) + interval '1 month';

    -- Generate partition names
    partition_name_system := 'metrics.system_metrics_y' ||
                    to_char(next_month, 'YYYY') ||
                    'm' ||
                    to_char(next_month, 'MM');

    partition_name_llm := 'metrics.llm_metrics_y' ||
                    to_char(next_month, 'YYYY') ||
                    'm' ||
                    to_char(next_month, 'MM');

    start_date := to_char(next_month, 'YYYY-MM-DD');
    end_date := to_char(next_month + interval '1 month', 'YYYY-MM-DD');

    -- Create the system metrics partition if it doesn't exists
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %s PARTITION OF metrics.system_metrics
        FOR VALUES FROM (%L) TO (%L)',
        partition_name_system, start_date, end_date);

    -- Create the LLM Metrics partition if it doesn't exist
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %s PARTITION OF metrics.llm_metrics
        FOR VALUES FROM (%L) TO (%L)',
        partition_name_llm, start_date, end_date);

    RAISE NOTICE 'Created partitions for %', next_month;
END;
$$ LANGUAGE plpgsql;

-- Function to perform routine maintenance on metrics tables
CREATE OR REPLACE FUNCTION metrics.maintenance()
RETURNS void AS $$
BEGIN
  -- Analyze tables for query planning
  ANALYZE metrics.system_metrics;
  ANALYZE metrics.llm_metrics;
  ANALYZE metrics.response_cache;

  -- Vacuum tables with significant churn
  VACUUM metrics.response_cache;

  RAISE NOTICE 'Maintenance completed';
END;
$$ LANGUAGE plpgsql;

-- Create the cron extension
CREATE EXTENSION pg_cron;

-- Schedule the function to run at midnight on the first day of each month
SELECT cron.schedule('create_monthly_partitions', '0 0 1 * *', 'SELECT metrics.create_partitions()');

-- Schedule weekly maintenance
SELECT cron.schedule('weekly_maintenance', '0 0 * * 0', 'SELECT metrics.maintenance()');
