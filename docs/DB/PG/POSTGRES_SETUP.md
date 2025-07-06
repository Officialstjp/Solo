# PostgreSQL Setup Guide

## Requirements

- Docker and Docker Compose
- PostgreSQL client tools (optional, for direct DB management)
- Minimum 2GB RAM allocated to Docker

## Environment Variables

The PostgreSQL setup uses the following environment variables:

| Variable | Description | Default Value |
|----------|-------------|---------------|
| `POSTGRES_USER` | Main PostgreSQL user | `solo_app` |
| `POSTGRES_PASSWORD` | Password for main user | `changeme` |
| `POSTGRES_APPPASSWORD` | Password for application role | `AppUserPwd123` |
| `POSTGRES_ADMPASSWORD` | Password for admin role | `AdminPwd456` |
| `POSTGRES_DB` | Main database name | `solo` |
| `POSTGRES_PORT` | Port to expose PostgreSQL | `5432` |

These variables can be set in a `.env` file at the project root.

## Setup Process

1. Create a `.env` file with secure passwords for production environments
2. Start the database container:
   ```bash
   docker-compose up -d db
   ```
3. Verify the database is running:
   ```bash
   docker-compose ps
   ```

## File Structure

The PostgreSQL setup uses the following directory structure:

```
Solo/
├─ scripts/
│  ├─ DockerInit/             # Scripts executed during container initialization
│  │  └─ 00-init-db.sh        # Environment variable substitution script
│  ├─ postgresql/             # PostgreSQL configuration
│  │  ├─ postgresql.conf      # Main PostgreSQL configuration file
│  │  └─ init-scripts/        # SQL scripts to be processed by init-db.sh
│  │     └─ 11-Solo_DB.sql    # Main database schema definition
│  └─ db/                     # Database management scripts
│     ├─ backup-db.ps1        # PowerShell backup script
│     ├─ restore-db.ps1       # PowerShell restore script
│     └─ schedule-backups.ps1 # PowerShell script for scheduled backups
└─ backups/                   # Directory for database backups
```

## Secrets Management

The Solo project implements a secure approach to secrets management with several layers:

### 1. Environment Variable Substitution

The `init-db.sh` script uses `envsubst` to replace variables in SQL scripts before execution. This prevents secrets from being stored in plain text within SQL files.

### 2. Environment Variables and .env Files

secrets are stored in `.env` files (which should not be committed to version control). Example `.env` file:
```
POSTGRES_USER=solo_app
POSTGRES_PASSWORD=strong_password_here
POSTGRES_APPPASSWORD='secure_app_password'
POSTGRES_ADMPASSWORD='secure_admin_password'
```

## PostgreSQL Extensions

The Solo database uses these PostgreSQL extensions:

- `vector`: For vector embeddings (RAG functionality)
- `pg_cron`: For scheduled maintenance tasks
- `pgaudit`: For detailed audit logging
- `wal2json`: For logical replication and change data capture

## Troubleshooting

### Connection Issues

If you can't connect to the database:

1. Check if the container is running: `docker-compose ps`
2. View logs: `docker-compose logs db`
3. Verify port mapping: `docker-compose port db 5432`
4. Check credentials in `.env` file

### Initialization Errors

If the database fails to initialize:

1. Check SQL script syntax: `docker-compose logs db | grep ERROR`
2. Verify environment variables are passed correctly
3. Ensure volume permissions are correct
4. Confirm the `gettext-base` package is properly installed for `envsubst`

### Common Initialization Issues

1. **Missing envsubst command**:
   ```
   /docker-entrypoint-initdb.d/00-init-db.sh: line 22: envsubst: command not found
   ```
   Solution: Ensure the `gettext-base` package is properly installed in the Dockerfile, the solutions in **2.** might help here aswell.

2. **Database Already Exists**:
   ```
   PostgreSQL Database directory appears to contain a database; Skipping initialization
   ```
   Solution:
   use `docker-compose down -v` to remove volumes and start fresh
   use `docker system prune --all --force` to remove all cached docker installation files (next installation will take longer)


# PostgreSQL Configuration Guide

## Table of Contents
- [Database Structure](#database-structure)
- [Configuration Files](#configuration-files)
- [Extensions](#extensions)
- [Performance Tuning](#performance-tuning)

## Database Structure

The Solo database uses a schema-based organization to logically separate different components:
The structure is layed out in more detail later in the document.

```
solo (database)
├── metrics (schema for all performance data)
│   ├── system_metrics
│   ├── llm_metrics
│   ├── response_cache
│   └── daily_metrics_summary
├── models (schema for model management)
│   └── model_registry
├── users (schema for user-related data)
│   ├── users
│   ├── sessions
│   ├── conversations
│   └── messages
└── rag (schema for retrieval-augmented generation)
    ├── documents
    └── document_chunks
```

## Configuration Files

### postgresql.conf

The main PostgreSQL configuration file (`scripts/postgresql/postgresql.conf`) contains settings for:

- Memory allocation
- Connection limits
- WAL (Write-Ahead Log) configuration
- Query planner settings
- Logging settings

Key settings:

```
# Memory settings
shared_buffers = 1GB               # 25% of available RAM for dedicated servers
work_mem = 64MB                    # Per-operation memory for sorts and hashes
maintenance_work_mem = 256MB       # Memory for maintenance operations

# Connection settings
max_connections = 100              # Maximum concurrent connections
superuser_reserved_connections = 3 # Connections reserved for superusers

# WAL settings
wal_level = replica                # Minimum for replication
max_wal_size = 1GB                 # Maximum WAL size before checkpoint
min_wal_size = 80MB                # Minimum WAL size

# Query planner
random_page_cost = 1.1             # Assumes SSD storage
effective_cache_size = 3GB         # Estimate of OS page cache

# Logging
log_destination = 'csvlog'         # Log format
logging_collector = on             # Enable log collection
log_directory = 'pg_log'           # Directory for logs
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_min_duration_statement = 1000  # Log slow queries (>1s)
```

## Extensions

The Solo database uses several PostgreSQL extensions:

1. **pgvector**: Enables vector similarity search for RAG functionality
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

2. **pg_cron**: Provides scheduled job capabilities for maintenance tasks
   ```sql
   CREATE EXTENSION IF NOT EXISTS pg_cron;
   ```

3. **pgaudit**: Provides detailed audit logging
   ```sql
   CREATE EXTENSION IF NOT EXISTS pgaudit;
   ```

4. **pg_stat_statements**: Tracks execution statistics for all SQL statements
   ```sql
   CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
   ```

## Performance Tuning

### Partitioning

Time-series tables like `metrics.llm_metrics` and `metrics.system_metrics` use range partitioning by timestamp:

```sql
CREATE TABLE metrics.llm_metrics (
    id SERIAL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- other fields
) PARTITION BY RANGE (timestamp);
```

Partitions are automatically created monthly through a scheduled pg_cron job:

```sql
SELECT cron.schedule('create_monthly_partitions', '0 0 1 * *', 'SELECT metrics.create_partitions()');
```

### Indexing Strategy

Key indexes used in the database:

1. **Timestamp Indexes**: BRIN indexes on partitioned timestamp columns
   ```sql
   CREATE INDEX idx_llm_metrics_timestamp ON metrics.llm_metrics USING brin(timestamp);
   ```

2. **Vector Similarity Indexes**: IVFFlat indexes for vector similarity search
   ```sql
   CREATE INDEX idx_document_chunks_embedding ON rag.document_chunks USING ivfflat (embedding vector_cosine_ops);
   ```

3. **Foreign Key Indexes**: B-tree indexes on frequently joined columns
   ```sql
   CREATE INDEX idx_messages_conversation_id ON users.messages(conversation_id);
   ```

### Maintenance

Regular maintenance is scheduled through pg_cron:

```sql
SELECT cron.schedule('weekly_maintenance', '0 0 * * 0', 'SELECT metrics.maintenance()');
```

The maintenance function performs:
- Table analysis for query planning
- Vacuum operations on high-churn tables
- Index maintenance

# PostgreSQL Setup Checklist
Use this checklist to verify the PostgreSQL setup for the Solo project.

## Initial Setup

- [ ] **Environment variables configured**
  - [ ] Created `.env` file with secure passwords
  - [ ] Set `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_APPPASSWORD`, `POSTGRES_ADMPASSWORD`

- [ ] **Docker configuration**
  - [ ] Dockerfile.postgres properly configured with required extensions
  - [ ] docker-compose.yml has correct volume mappings
  - [ ] Health check configured

- [ ] **Directory structure**
  - [ ] `/scripts/DockerInit/00-init-db.sh` exists and is executable
  - [ ] `/scripts/postgresql/init-scripts/11-Solo_DB.sql` SQL script is valid
  - [ ] `/scripts/postgresql/postgresql.conf` configuration file exists

## Container Initialization

- [ ] **Build and start the container**
  ```bash
  docker-compose up -d db
  ```

- [ ] **Verify container is running**
  ```bash
  docker-compose ps
  ```

- [ ] **Check initialization logs**
  ```bash
  docker-compose logs db
  ```

- [ ] **Verify successful initialization**
  - [ ] Look for "PostgreSQL init process complete; ready for start up"
  - [ ] No error messages related to SQL script execution
  - [ ] Environment variable substitution worked correctly

## Database Verification

- [ ] **Connect to the database**
  ```bash
  docker exec -it solo_postgres psql -U $POSTGRES_USER -d $POSTGRES_DB
  ```

- [ ] **Verify schemas exist**
  ```sql
  \dn
  ```
  Should show: metrics, models, users, rag

- [ ] **Verify tables exist**
  ```sql
  \dt metrics.*
  \dt models.*
  \dt users.*
  \dt rag.*
  ```

- [ ] **Verify extensions**
  ```sql
  \dx
  ```
  Should include: pg_cron, vector, pgaudit

- [ ] **Verify partitioning**
  ```sql
  SELECT
    parent.relname AS parent_table,
    child.relname AS child_table
  FROM pg_inherits
  JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
  JOIN pg_class child ON pg_inherits.inhrelid = child.oid
  WHERE parent.relname IN ('system_metrics', 'llm_metrics');
  ```

- [ ] **Verify scheduled tasks**
  ```sql
  SELECT * FROM cron.job;
  ```
  Should show partition creation and maintenance jobs

## Backup and Restore Testing

- [ ] **Create a test backup**
  ```powershell
  .\scripts\db\backup-db.ps1 -BackupName "test_backup"
  ```

- [ ] **Verify backup file**
  ```powershell
  Get-ChildItem .\backups\test_backup.dump
  ```

- [ ] **Test restore functionality**
  ```powershell
  .\scripts\db\restore-db.ps1 -BackupFile "test_backup.dump"
  ```

## Performance Testing

- [ ] **Test inserting data**
  ```sql
  INSERT INTO metrics.llm_metrics
  (model_id, session_id, request_id, tokens_generated, generation_time_ms, cache_hit)
  VALUES
  ('mistral-7b', '12345', '67890', 100, 500, FALSE);
  ```

- [ ] **Test query performance**
  ```sql
  EXPLAIN ANALYZE
  SELECT * FROM metrics.llm_metrics
  WHERE timestamp >= NOW() - INTERVAL '1 day';
  ```

## Security Verification

- [ ] **Check role permissions**
  ```sql
  SELECT * FROM information_schema.role_table_grants
  WHERE grantee = 'solo_app';
  ```

- [ ] **Check network security**
  - [ ] Database only accessible via intended network paths
  - [ ] No unnecessary port exposures
