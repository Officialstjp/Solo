# Solo Database - Common Queries Reference

This document provides a collection of useful SQL queries for working with the Solo PostgreSQL database, organized by task type.

## Metrics and Analytics

### LLM Performance Metrics

```sql
-- Get LLM performance statistics by model
SELECT
    model_id,
    COUNT(*) AS requests,
    AVG(generation_time_ms) AS avg_gen_time_ms,
    AVG(tokens_per_second) AS avg_tokens_per_sec,
    SUM(tokens_generated) AS total_tokens,
    SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) AS cache_hits,
    ROUND(SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) AS cache_hit_rate
FROM metrics.llm_metrics
WHERE timestamp >= NOW() - INTERVAL '7 days'
GROUP BY model_id
ORDER BY requests DESC;

-- Get hourly LLM usage patterns
SELECT
    DATE_TRUNC('hour', timestamp) AS hour,
    COUNT(*) AS requests,
    SUM(tokens_generated) AS tokens_generated,
    AVG(generation_time_ms) AS avg_gen_time_ms
FROM metrics.llm_metrics
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', timestamp)
ORDER BY hour;

-- Identify slow-performing requests
SELECT
    request_id,
    model_id,
    timestamp,
    tokens_generated,
    generation_time_ms,
    tokens_per_second,
    prompt_tokens,
    parameters
FROM metrics.llm_metrics
WHERE timestamp >= NOW() - INTERVAL '24 hours'
ORDER BY generation_time_ms DESC
LIMIT 20;
```

### System Performance Metrics

```sql
-- Get system resource utilization over time
SELECT
    DATE_TRUNC('hour', timestamp) AS hour,
    AVG(cpu_percent) AS avg_cpu,
    MAX(cpu_percent) AS max_cpu,
    AVG(memory_percent) AS avg_memory,
    MAX(memory_percent) AS max_memory,
    AVG(gpu_percent) AS avg_gpu,
    MAX(gpu_percent) AS max_gpu
FROM metrics.system_metrics
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', timestamp)
ORDER BY hour;

-- Identify resource usage spikes
SELECT
    timestamp,
    cpu_percent,
    memory_percent,
    gpu_percent,
    gpu_temperature
FROM metrics.system_metrics
WHERE
    timestamp >= NOW() - INTERVAL '7 days'
    AND (cpu_percent > 90 OR memory_percent > 90 OR gpu_percent > 90)
ORDER BY timestamp DESC;

-- Get correlation between LLM usage and system metrics
WITH llm_hourly AS (
    SELECT
        DATE_TRUNC('hour', timestamp) AS hour,
        COUNT(*) AS request_count
    FROM metrics.llm_metrics
    WHERE timestamp >= NOW() - INTERVAL '24 hours'
    GROUP BY DATE_TRUNC('hour', timestamp)
),
system_hourly AS (
    SELECT
        DATE_TRUNC('hour', timestamp) AS hour,
        AVG(cpu_percent) AS avg_cpu,
        AVG(memory_percent) AS avg_memory,
        AVG(gpu_percent) AS avg_gpu
    FROM metrics.system_metrics
    WHERE timestamp >= NOW() - INTERVAL '24 hours'
    GROUP BY DATE_TRUNC('hour', timestamp)
)
SELECT
    l.hour,
    l.request_count,
    s.avg_cpu,
    s.avg_memory,
    s.avg_gpu
FROM llm_hourly l
JOIN system_hourly s ON l.hour = s.hour
ORDER BY l.hour;
```

### Cache Effectiveness

```sql
-- Cache hit ratio over time
SELECT
    DATE_TRUNC('day', timestamp) AS day,
    COUNT(*) AS total_requests,
    SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) AS cache_hits,
    ROUND(SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) AS cache_hit_ratio
FROM metrics.llm_metrics
WHERE timestamp >= NOW() - INTERVAL '30 days'
GROUP BY DATE_TRUNC('day', timestamp)
ORDER BY day;

-- Top cached prompts by hit count
SELECT
    cache_key,
    hit_count,
    created_at,
    expires_at,
    LENGTH(prompt) AS prompt_length,
    LENGTH(response) AS response_length
FROM metrics.response_cache
ORDER BY hit_count DESC
LIMIT 20;

-- Expiring cache entries
SELECT
    cache_key,
    hit_count,
    created_at,
    expires_at,
    NOW() - created_at AS age,
    expires_at - NOW() AS time_until_expiry
FROM metrics.response_cache
WHERE expires_at < NOW() + INTERVAL '24 hours'
ORDER BY expires_at;
```

## User and Conversation Management

### User Activity

```sql
-- Most active users
SELECT
    u.user_id,
    u.name,
    COUNT(DISTINCT s.session_id) AS session_count,
    COUNT(DISTINCT c.conversation_id) AS conversation_count,
    COUNT(m.message_id) AS message_count,
    MAX(s.last_active) AS last_active
FROM users.users u
LEFT JOIN users.sessions s ON u.user_id = s.user_id
LEFT JOIN users.conversations c ON s.session_id = c.session_id
LEFT JOIN users.messages m ON c.conversation_id = m.conversation_id
GROUP BY u.user_id, u.name
ORDER BY message_count DESC;

-- Recent user sessions
SELECT
    s.session_id,
    u.user_id,
    u.name,
    s.created_at,
    s.last_active,
    s.status,
    COUNT(DISTINCT c.conversation_id) AS conversation_count,
    COUNT(m.message_id) AS message_count
FROM users.sessions s
JOIN users.users u ON s.user_id = u.user_id
LEFT JOIN users.conversations c ON s.session_id = c.session_id
LEFT JOIN users.messages m ON c.conversation_id = m.conversation_id
WHERE s.last_active >= NOW() - INTERVAL '7 days'
GROUP BY s.session_id, u.user_id, u.name, s.created_at, s.last_active, s.status
ORDER BY s.last_active DESC;
```

### Conversation Analysis

```sql
-- Get conversation history for a specific user
SELECT
    c.conversation_id,
    c.title,
    c.created_at,
    c.updated_at,
    COUNT(m.message_id) AS message_count,
    EXTRACT(EPOCH FROM (c.updated_at - c.created_at)) / 60 AS duration_minutes
FROM users.conversations c
JOIN users.sessions s ON c.session_id = s.session_id
JOIN users.users u ON s.user_id = u.user_id
LEFT JOIN users.messages m ON c.conversation_id = m.conversation_id
WHERE u.user_id = 'user123'
GROUP BY c.conversation_id, c.title, c.created_at, c.updated_at
ORDER BY c.updated_at DESC;

-- Get messages for a specific conversation
SELECT
    m.message_id,
    m.role,
    m.created_at,
    m.model_id,
    m.tokens,
    SUBSTRING(m.content, 1, 100) || CASE WHEN LENGTH(m.content) > 100 THEN '...' ELSE '' END AS content_preview
FROM users.messages m
WHERE m.conversation_id = 'conv123'
ORDER BY m.created_at;

-- Find conversations with specific keywords
SELECT
    c.conversation_id,
    c.title,
    u.name AS user_name,
    c.created_at,
    COUNT(m.message_id) AS message_count
FROM users.conversations c
JOIN users.sessions s ON c.session_id = s.session_id
JOIN users.users u ON s.user_id = u.user_id
JOIN users.messages m ON c.conversation_id = m.conversation_id
WHERE
    m.content ILIKE '%machine learning%'
    OR c.title ILIKE '%machine learning%'
GROUP BY c.conversation_id, c.title, u.name, c.created_at
ORDER BY c.created_at DESC;
```

## Model Management

### Model Usage and Performance

```sql
-- Model usage statistics
SELECT
    m.model_id,
    m.name,
    m.format,
    m.parameter_size,
    m.quantization,
    COUNT(lm.request_id) AS usage_count,
    AVG(lm.generation_time_ms) AS avg_generation_time_ms,
    AVG(lm.tokens_per_second) AS avg_tokens_per_second,
    SUM(lm.tokens_generated) AS total_tokens_generated
FROM models.models m
LEFT JOIN metrics.llm_metrics lm ON m.model_id = lm.model_id
GROUP BY m.model_id, m.name, m.format, m.parameter_size, m.quantization
ORDER BY usage_count DESC;

-- Model performance comparison
SELECT
    m.model_id,
    m.name,
    m.parameter_size,
    m.quantization,
    COUNT(lm.request_id) AS request_count,
    AVG(lm.generation_time_ms) AS avg_gen_time_ms,
    AVG(lm.tokens_per_second) AS avg_tokens_per_sec,
    AVG(lm.tokens_generated) AS avg_tokens_generated
FROM models.models m
JOIN metrics.llm_metrics lm ON m.model_id = lm.model_id
WHERE lm.timestamp >= NOW() - INTERVAL '30 days'
GROUP BY m.model_id, m.name, m.parameter_size, m.quantization
HAVING COUNT(lm.request_id) > 10
ORDER BY avg_tokens_per_sec DESC;

-- Inactive models
SELECT
    model_id,
    name,
    format,
    parameter_size,
    context_length,
    first_added,
    last_used,
    NOW() - COALESCE(last_used, first_added) AS time_since_last_use,
    file_size_mb
FROM models.models
WHERE is_active = TRUE AND (last_used IS NULL OR last_used < NOW() - INTERVAL '30 days')
ORDER BY COALESCE(last_used, first_added);
```

## RAG Components

### Document Management

```sql
-- Document statistics
SELECT
    COUNT(DISTINCT doc_id) AS document_count,
    SUM(LENGTH(content)) AS total_content_length,
    AVG(LENGTH(content)) AS avg_document_length,
    COUNT(DISTINCT source) AS unique_sources
FROM rag.documents;

-- Document chunks analysis
SELECT
    d.doc_id,
    d.title,
    d.source,
    COUNT(dc.id) AS chunk_count,
    AVG(LENGTH(dc.content)) AS avg_chunk_length
FROM rag.documents d
JOIN rag.document_chunks dc ON d.doc_id = dc.doc_id
GROUP BY d.doc_id, d.title, d.source
ORDER BY chunk_count DESC;

-- Find similar document chunks (requires pgvector)
WITH query_embedding AS (
    SELECT embedding
    FROM rag.document_chunks
    WHERE doc_id = 'doc123' AND chunk_index = 5
)
SELECT
    dc.doc_id,
    d.title,
    dc.chunk_index,
    SUBSTRING(dc.content, 1, 100) || '...' AS content_preview,
    dc.embedding <=> (SELECT embedding FROM query_embedding) AS distance
FROM rag.document_chunks dc
JOIN rag.documents d ON dc.doc_id = d.doc_id
WHERE dc.doc_id != 'doc123' OR dc.chunk_index != 5
ORDER BY dc.embedding <=> (SELECT embedding FROM query_embedding)
LIMIT 10;
```

## Database Maintenance
```sql
-- Check database size
SELECT pg_size_pretty(pg_database_size('solo')) AS database_size;

-- Check table sizes
SELECT
    schemaname,
    relname AS table_name,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
    pg_size_pretty(pg_relation_size(relid)) AS table_size,
    pg_size_pretty(pg_indexes_size(relid)) AS index_size
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;

-- Check partition information
SELECT
    nmsp_parent.nspname AS parent_schema,
    parent.relname AS parent,
    nmsp_child.nspname AS child_schema,
    child.relname AS child,
    pg_size_pretty(pg_relation_size(child.oid)) AS size
FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
JOIN pg_class child ON pg_inherits.inhrelid = child.oid
JOIN pg_namespace nmsp_parent ON nmsp_parent.oid = parent.relnamespace
JOIN pg_namespace nmsp_child ON nmsp_child.oid = child.relnamespace
WHERE parent.relname = 'system_metrics'
ORDER BY pg_relation_size(child.oid) DESC;

-- Check index usage
SELECT
    schemaname,
    relname AS table_name,
    indexrelname AS index_name,
    idx_scan AS index_scans,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC
LIMIT 10;

-- Check cache hit ratio
SELECT
    sum(heap_blks_read) as heap_read,
    sum(heap_blks_hit)  as heap_hit,
    sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as ratio
FROM pg_statio_user_tables;
```

### 3.2 Maintenance Queries

```sql
-- Analyze tables to update statistics
ANALYZE VERBOSE metrics.system_metrics;
ANALYZE VERBOSE metrics.llm_metrics;

-- Vacuum tables to reclaim space
VACUUM VERBOSE metrics.response_cache;

-- Reindex tables
REINDEX TABLE metrics.system_metrics;

-- Find and kill long-running queries
SELECT
    pid,
    now() - pg_stat_activity.query_start AS duration,
    query
FROM pg_stat_activity
WHERE query != '<IDLE>' AND query NOT ILIKE '%pg_stat_activity%'
ORDER BY duration DESC;

-- Kill a specific query
SELECT pg_cancel_backend(PID);
```

### 3.3 Metrics Queries

```sql
-- Top models by usage count
SELECT
    model_id,
    COUNT(*) AS usage_count,
    SUM(tokens_generated) AS total_tokens,
    AVG(generation_time_ms) AS avg_generation_time_ms
FROM metrics.llm_metrics
WHERE timestamp >= NOW() - INTERVAL '7 days'
GROUP BY model_id
ORDER BY usage_count DESC;

-- Daily metrics summary
SELECT
    DATE_TRUNC('day', timestamp) AS day,
    COUNT(*) AS request_count,
    SUM(tokens_generated) AS tokens_generated,
    AVG(generation_time_ms) AS avg_generation_time_ms,
    SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) AS cache_hits,
    SUM(CASE WHEN NOT cache_hit THEN 1 ELSE 0 END) AS cache_misses
FROM metrics.llm_metrics
WHERE timestamp >= NOW() - INTERVAL '30 days'
GROUP BY DATE_TRUNC('day', timestamp)
ORDER BY day DESC;

-- System metrics peaks
SELECT
    DATE_TRUNC('day', timestamp) AS day,
    MAX(cpu_percent) AS max_cpu_percent,
    MAX(memory_percent) AS max_memory_percent,
    MAX(gpu_percent) AS max_gpu_percent
FROM metrics.system_metrics
WHERE timestamp >= NOW() - INTERVAL '7 days'
GROUP BY DATE_TRUNC('day', timestamp)
ORDER BY day DESC;
```

### 3.4 Partition Management

```sql
-- Create partitions for the next 3 months
SELECT metrics.create_future_partitions(3);

-- List all partitions with sizes
SELECT
    nmsp_child.nspname AS schema,
    child.relname AS partition,
    pg_size_pretty(pg_relation_size(child.oid)) AS size,
    to_char(min(timestamp), 'YYYY-MM-DD') AS min_date,
    to_char(max(timestamp), 'YYYY-MM-DD') AS max_date,
    count(*) AS row_count
FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
JOIN pg_class child ON pg_inherits.inhrelid = child.oid
JOIN pg_namespace nmsp_parent ON nmsp_parent.oid = parent.relnamespace
JOIN pg_namespace nmsp_child ON nmsp_child.oid = child.relnamespace
LEFT JOIN metrics.system_metrics sm ON (child.relname = 'system_metrics_y' ||
                                      to_char(sm.timestamp, 'YYYYMM'))
WHERE parent.relname = 'system_metrics'
GROUP BY schema, partition, child.oid
ORDER BY partition;

-- Archive old partitions (example for 2025-01)
BEGIN;
-- Create archive table
CREATE TABLE metrics.system_metrics_archive_202501
(LIKE metrics.system_metrics INCLUDING ALL);

-- Copy data
INSERT INTO metrics.system_metrics_archive_202501
SELECT * FROM metrics.system_metrics_y202501;

-- Detach partition
ALTER TABLE metrics.system_metrics
DETACH PARTITION metrics.system_metrics_y202501;

-- Verify row count before dropping
SELECT count(*) FROM metrics.system_metrics_y202501;
SELECT count(*) FROM metrics.system_metrics_archive_202501;

-- Drop original partition if counts match
DROP TABLE metrics.system_metrics_y202501;
COMMIT;
```

``` SQL
-- Connection status
SELECT
    datname AS database,
    usename AS username,
    application_name,
    client_addr,
    state,
    COUNT(*) AS connection_count
FROM pg_stat_activity
WHERE datname IS NOT NULL
GROUP BY datname, usename, application_name, client_addr, state
ORDER BY connection_count DESC;

-- Lock information
SELECT
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_statement,
    blocking_activity.query AS blocking_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.DATABASE IS NOT DISTINCT FROM blocked_locks.DATABASE
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.GRANTED;
```

### Performance Tuning

```sql
-- Find slow queries
SELECT
    substring(query, 1, 100) AS query_preview,
    calls,
    total_time,
    mean_time,
    rows
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 20;

-- Index usage statistics
SELECT
    schemaname AS schema_name,
    relname AS table_name,
    indexrelname AS index_name,
    idx_scan AS index_scans,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched,
    CASE
        WHEN idx_scan = 0 THEN 'Unused'
        ELSE 'Used'
    END AS usage_status
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Missing indexes (tables with seq scans but few index scans)
SELECT
    schemaname AS schema_name,
    relname AS table_name,
    seq_scan,
    seq_tup_read,
    idx_scan,
    n_live_tup AS estimated_row_count
FROM pg_stat_user_tables
WHERE seq_scan > 10 AND idx_scan = 0
ORDER BY seq_scan DESC, n_live_tup DESC;
```

## pg_cron Job Management

```sql
-- List all scheduled jobs
SELECT
    jobid,
    schedule,
    command,
    nodename,
    database,
    username,
    active,
    jobname
FROM cron.job
ORDER BY jobid;

-- Schedule a new job
SELECT cron.schedule('maintenance_weekly', '0 0 * * 0', 'VACUUM ANALYZE metrics.llm_metrics');

-- Schedule the partition creation job
SELECT cron.schedule('create_monthly_partitions', '0 0 1 * *', 'SELECT metrics.create_partitions()');

-- Disable a job
SELECT cron.unschedule(jobid) FROM cron.job WHERE jobname = 'maintenance_weekly';

-- Check job run history
SELECT
    jobid,
    runid,
    command,
    status,
    start_time,
    end_time,
    return_message
FROM cron.job_run_details
ORDER BY start_time DESC
LIMIT 20;
```
