# Solo Project Database Design
The database will be used to store various types of data, including metrics, model information, user sessions, conversation history, and vector embeddings for RAG capabilities.


## Database Schema

### 1. Metrics Data

The metrics tables will store both system-level and LLM-specific performance metrics.

#### 1.1 System Metrics

```sql
CREATE TABLE system_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cpu_percent FLOAT,
    cpu_temperature FLOAT,
    memory_percent FLOAT,
    memory_used_mb FLOAT,
    memory_temperature FLOAT,
    gpu_percent FLOAT,
    gpu_temperature FLOAT,
    gpu_fans_rpm FLOAT,
    gpu_watt FLOAT,
    vram_percent FLOAT,
    vram_used_mb FLOAT,
    network_recieved FLOAT,
    network_sent FLOAT,
    disk_writes_s_C FLOAT,
    disk_reads_s_C FLOAT,
    disk_writes_s_D FLOAT,
    disk_reads_s_D  FLOAT,
    system_uptime_seconds FLOAT,
    app_uptime_seconds FLOAT
);

-- For time-series partitioning
CREATE INDEX idx_system_metrics_timestamp ON system_metrics(timestamp);
```

#### 1.2 LLM Performance Metrics

```sql
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
```

#### 1.3 Aggregated Metrics

```sql
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
```

### 2. Models Information

```sql
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
```

### 3. User Sessions and Conversations

```sql
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
```

### 4. Vector Database for RAG (Retrieval-Augmented Generation)

```sql
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
```

### 5. Caching System

```sql
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
```

### 6. Security

```sql
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

CREATE INDEX IF NOT EXISTS idx_login_attempts_username ON security.login_attempts(username)
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON security.login_attempts(ip_address)
CREATE INDEX IF NOT EXISTS idx_login_attempts_timestamp ON security.login_attempts(timestamp)
CREATE INDEX IF NOT EXISTS idx_security_events_user_id ON security.security_events(user_id)
CREATE INDEX IF NOT EXISTS idx_security_events_timestamp ON security.security_events(timestamp)
```

## Database Migration Strategy

For managing database migrations, we'll use Alembic with SQLAlchemy. This allows:

1. Version-controlled schema changes
2. Forward and backward migrations
3. Automated schema updates during deployment

## Partitioning Strategy for Metrics Data

For metrics tables that will grow continuously, we use time-based partitioning:

```sql
-- Example for system_metrics
CREATE TABLE system_metrics (
    id SERIAL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- other fields
) PARTITION BY RANGE (timestamp);

-- Create partitions by month
CREATE TABLE system_metrics_y2025m06 PARTITION OF system_metrics
    FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');
CREATE TABLE system_metrics_y2025m07 PARTITION OF system_metrics
    FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');
-- Add more partitions as needed
```

## Integration with Solo Architecture

The database component will integrate with the Solo architecture through:

1. **DB Service Layer**: A dedicated `db_service.py` module will provide an abstraction layer for database operations.
2. **SQLAlchemy ORM**: For object-relational mapping and type safety.
3. **Event-Based Updates**: Database writes will be triggered through the application's event bus.
4. **Connection Pooling**: To efficiently manage database connections.

## Docker Deployment

The PostgreSQL database will be deployed as a Docker container with:

1. **Persistent Volume**: For data durability across container restarts
2. **Environment Variables**: For configuration management
3. **Health Checks**: To ensure database availability
4. **Backup Strategy**: Regular backups to prevent data loss

Example Docker Compose configuration:

```yaml
version: '3.8'

services:
  db:
    image: postgres:16
    container_name: solo-postgres
    environment:
      POSTGRES_DB: solo
      POSTGRES_USER: solo_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "solo_user", "-d", "solo"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  postgres-data:
```

## Performance Considerations

1. **Indexes**: Carefully designed indexes for frequently queried columns
2. **Partitioning**: Time-based partitioning for metrics tables to improve query performance
3. **JSONB**: Use of JSONB for flexible schema while maintaining good query performance
4. **Archiving**: Strategy for archiving or aggregating old metrics data
5. **Connection Pooling**: To manage database connections efficiently

## Security Considerations

1. **Connection Encryption**: Use SSL for database connections
2. **Authentication**: Strong password policies and role-based access
3. **Input Validation**: All database inputs will be validated and sanitized
4. **Principle of Least Privilege**: Database users will have minimal required permissions
5. **Sensitive Data**: Encryption of sensitive data at rest

## Future Expansion

The database design allows for future expansion to support:

1. **Multi-user Support**: User authentication and access control
2. **Extended Metrics**: Additional performance and usage metrics
3. **Model Versioning**: Track changes to models over time
4. **A/B Testing**: Support for comparing different models or prompts
5. **Feedback Systems**: User feedback on responses for model improvement
6. **Distributed Deployment**: Potential for read replicas or sharding

# Database Management

## 1. Managing Database Secrets

There are several approaches to handle secrets in PostgreSQL initialization scripts:

### Environment Variable Substitution

We use the `envsubst` utility to replace environment variables in SQL scripts before execution:

```bash
# In scripts/DockerInit/00-init-db.sh
echo "Processing SQL files with environment variable substitution..."
for f in /etc/postgresql/init-scripts/*.sql; do
  echo "Processing $f file..."

  # Create a temporary file with variables substituted
  tempfile=$(mktemp)
  export POSTGRES_APPPASSWORD="'${POSTGRES_APPPASSWORD:-AppUserPwd123}'"
  export POSTGRES_ADMPASSWORD="'${POSTGRES_ADMPASSWORD:-AdminPwd456}'"

  envsubst < "$f" > "$tempfile"

  # Execute the processed SQL file
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$tempfile"

  # Clean up and unset variables for security
  rm "$tempfile"
  unset POSTGRES_APPPASSWORD
  unset POSTGRES_ADMPASSWORD
done
```

## 2. Backup Strategy
A full Backup Strategy is still in the works...

### 2.1 Types of Backups

1. **Logical Backups (pg_dump)**
   - Human-readable SQL scripts
   - Easy to restore selectively
   - Slower than physical backups for large databases

2. **Physical Backups (pg_basebackup)**
   - Binary copy of database files
   - Fast for large databases
   - Point-in-time recovery with WAL files

3. **Continuous Archiving**
   - WAL archiving for point-in-time recovery
   - Minimal data loss in case of failure

### 2.2 Backup Schedule Sktech

| Backup Type | Frequency | Retention | Tool |
|-------------|-----------|-----------|------|
| Full Logical | Daily | 7 days | pg_dump |
| Schema-only | Weekly | 4 weeks | pg_dump --schema-only |
| WAL Archives | Continuous | 7 days | archive_command |

### 2.3 Using the Backup Scripts

```powershell
# Create a full backup
.\scripts\db\backup-db.ps1 -Compress -RetainDays 7

# Create a schema-only backup
.\scripts\db\backup-db.ps1 -BackupName "schema_backup" -IncludeSchema -IncludeData:$false

# Set up scheduled backups
.\scripts\db\schedule-backups.ps1 -TimeOfDay "03:00" -DaysOfWeek "Monday","Wednesday","Friday" -RetainDays 30
```

## 4. Further Improvements

1. **Connection Pooling**
   - Implement PgBouncer for connection pooling
   - Configure max_connections appropriately

2. **Vacuum Strategy**
   - Set up autovacuum for busy tables
   - Configure vacuum thresholds

3. **High Availability**
   - Configure streaming replication
   - Implement failover mechanism

4. **Monitoring**
   - Set up pg_stat_statements for query monitoring
   - Implement alert systems for database health
