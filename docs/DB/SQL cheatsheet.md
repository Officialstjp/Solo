# Databases
... to be documented maybe

## Database schemas
In PostgresQL, a schema is a namespace that contains named database objects such as tables, views, indixes, data types, functions and operators.

Schemas allow for:
1. **Logical Organization**
2. **Name Collision Prevention**: Tables in different schemas can have the same name without conflict

``` SQL
metrics.users -- A table tracking user metrics
app.users     -- A table for application users
```
3. **Security Boundaries**: Grant permissions at the schema level for more granular access control
```SQL
-- Allow read-only access to metrics data
GRANT USAGE ON SCHEMA metrics TO readonly_role;
GRANT SELECT ON ALL TABLES IN SCHEMA metrics TO readonly_role;
```
4. Module Seperation: Seperate core functionality from extensions or third-party modules
5. Simplified Maintanence: Perform operations on groups of related objects

## How to implement Schemas
```SQL
-- Create schemas
CREATE SCHEMA metrics;
CREATE SCHEMA users;
CREATE SCHEMA models;
CREATE SCHEMA rag;

-- Create a table in specific schema
CREATE TABLE metrics.system_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPZ NOT NULL DEFAULT NOW(),
    cpu_percent FLOAT,
);

-- Set search path (default schema order)
SET search_path TO users, public;
```

Solo Example:
```Text
solo (database)
├── metrics (schema for all performance data)
│   ├── system_metrics
│   ├── llm_metrics
│   └── daily_metrics_summary
├── models (schema for model management)
│   └── models
├── users (schema for user-related data)
│   ├── users
│   ├── sessions
│   ├── conversations
│   └── messages
└── rag (schema for retrieval-augmented generation)
    ├── documents
    └── document_chunks
```

## Table Partitioning
### Introduction

Partitioned Tables have the some key advantages, compared to normal tables, notably:
1. Data Distribution:
- Regular Tables store all data in a single table file
- Pratitioned tables distribute data across multiple child tables based on the partiton key
2. Query Processing:
- PostgreSQL can skip irrelevant partitions during queries (partition pruning)
- The parititon key must be included in WHERE clauses to benefit from this optimization
3. Maintenance Operation:
- You can maintain (vacuum, reindex) individual partitions without affecting the entire dataset
- You can easily archive or drop old data by detaching or dropping partitions
4. Constraints:
- Primary keys must include the partition key
- Foreing keys have some limititation across partitons

### How Partition Tables Work
When you insert data into a partitioned table, PostgreSQL:
1. Evalues which partiton the data belongs to based on the partition key
2. Routes the data to the appropriate child table
3. Maintains the partition constraint automatically

When you query a partitioned table, PostgreSQL:
1. Analyzes WHERE clauses to determine which partitions might contian matching data
2. Only scans relevant partitions
3. Combines results from all scanned partitions

1. **Query Performance**:
```SQL
-- Without partitioning: Must scan the entire table (potentially millions of rows)
SELECT * FROM metrics.system_metrics
WHERE timestamp BETWEEN '2025-07-15' AND '2025-07-16';

-- With partitioning: Only scans the July 2025 partition (maybe thousands of rows)
-- Same query but much faster!
SELECT * FROM metrics.system_metrics
WHERE timestamp BETWEEN '2025-07-15' AND '2025-07-16';
```
2. Maintenance Efficiency: Perform maintenance operations on individual partitions
```SQL
-- Archive old data by detaching a partition
ALTER TABLE metrics.system_metrics DETACH PARTITION metrics.system_metrics_y2025m01;
```
3. Faster Data Deletion: Drop entire partition instead of deleting rows
``` SQL
-- Much faster than DELETE FROM metrics.system_metrics WHERE timestamp < '2025-01-01'
DROP TABLE metrics.system_metrics_y2024m12;
```
4. Optimized Storage: Place different partitions on different storage devices
5. Parallel Query Execution: PostgreSQL can scan multiple partitions in parallel

Types of Partitioning in PostgreSQL
1. Range Partitioning: Divide by ranges of values (most common for time-series data)
``` SQL
PARTITION BY RANGE (timestamp);
```
2. List Partitioning: Divide by discrete values
```SQL
PARTITION BY LIST (country_code);
```
3. Hash Partitioning: Distribute data evenly using a hash function
```SQL
PARTITION BY HASH (user_id);
```

## How to Implement Range Partitioning for Time-Series Data
``` SQL
-- Create a partitioned table
CREATE TABLE metrics.system_metrics (
    id SERIAL,
    timestamp, TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cpu_percent FLOAT,
    -- other fields
) PARTITION BY RANGE (timestamp);

-- Create monthly partitions
CREATE TABLE metrics.system_metrics_y2025m07 PARTITION OF metrics.system_metrics
    FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');

CREATE TABLE metrics.system_metrics_y2025m08 PARTITION OF metrics.system_metrics
    FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');

-- Add more partitions as needed
```

**Automating Partition Creation**
For a production system, you would typically create a function to automatically create future partitions:
``` SQL
-- Function to create partitions for the next 3 months
CREATE OR REPLACE FUNCTION metrics.create_future_partitions(months_ahead int DEFAULT 3)
RETURNS void AS $$
DECLARE
    current_month DATE;
    partition_name_system TEXT;
    partition_name_llm TEXT;
    start_date TEXT;
    end_date TEXT;
BEGIN
    FOR i IN 0..months_ahead LOOP
        current_month := date_trunc('month', now()) + (i || ' month')::interval;

        -- Generate partition names
        partition_name_system := 'metrics.system_metrics_y' ||
                          to_char(current_month, 'YYYY') ||
                          'm' ||
                          to_char(current_month, 'MM');

        partition_name_llm := 'metrics.llm_metrics_y' ||
                        to_char(current_month, 'YYYY') ||
                        'm' ||
                        to_char(current_month, 'MM');

        -- Format date ranges
        start_date := to_char(current_month, 'YYYY-MM-DD');
        end_date := to_char(current_month + interval '1 month', 'YYYY-MM-DD');

        -- Create the system metrics partition if it doesn't exist
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %s PARTITION OF metrics.system_metrics
            FOR VALUES FROM (%L) TO (%L)',
            partition_name_system, start_date, end_date);

        -- Create the LLM metrics partition if it doesn't exist
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %s PARTITION OF metrics.llm_metrics
            FOR VALUES FROM (%L) TO (%L)',
            partition_name_llm, start_date, end_date);

        RAISE NOTICE 'Created partitions for %', to_char(current_month, 'YYYY-MM');
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Call it manually to create initial partitions
SELECT metrics.create_future_partitions(6);
```

**Add indexes to Partitions**
```SQL
-- Add an index to all system metrics partitions
CREATE INDEX idx_system_metrics_cpu ON metrics.system_metrics(cpu_percent);

-- Add an index to a specific partition
CREATE INDEX idx_system_metrics_202507_memory ON metrics.system_metrics_y2025m07(memory_percent);
```

``` SQL
-- Detach old partitions (no longer queryable through parent table)
ALTER TABLE metrics.system_metrics
DETACH PARTITION metrics.system_metrics_y2025m01;

-- Archive to compressed table
CREATE TABLE metrics.system_metrics_archive_2025m01
AS SELECT * FROM metrics.system_metrics_y2025m01;

-- Drop the original partition
DROP TABLE metrics.system_metrics_y2025m01;
```

## Monitoring Partitons
Queries to monitor partitions:
``` SQL
-- List all partitions of a table
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
ORDER BY child.relname;

-- Check if a specific partition exists
SELECT EXISTS (
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'metrics'
    AND c.relname = 'system_metrics_y2025m07'
);
```
## Performance best practices
1. Always filter by partition key in WHERE clauses to enable partition pruning
2. Create a DEFAULT partition to catch unexpected data:
```SQL
CREATE TABLE metrics.system_metrics_default
PARTITION OF metrics.syste_metrics DEFAULT;
```
3. Consider sub-partitioning for very large tables (e.g., by month then by day)
4. Monitor partition sizes and ensure they stay relatively balanced
5. Use EXPLAIN ANALYZE to verify that partition pruning is working:
```SQL
EXPLAIN ANALYZE
SELECT * FROM metrics.system_metrics
WHERE timestamp BETWEEN '2025-07-01' AND '2025-07-31';
```

## Setting up pg_cron
The pg_cron extension allows you to schedule PostgreSQL commands directly within the database, similar to Linux cron jobs.

1. Installaion in Docker
Add pgvector Docker setup, add the pg_cron extension by modifying the Docker Compose file:
``` yml
services:
    db:
        image: pgvector/pgvector:pg17
        # ... other
        command: >
         postgres -c config_file=/etc/postgresql/postgresql.conf
                -c shared_preload_libraries='pg_stat_statements,vector,pg_cron'
                -c cron.database_name='${POSTGRES_DB:-solo}'
```

2. Install the Extension in PostreSQL
Once the container is running with pg_cron in shared_preload_libraries:
``` SQL
-- Conect to the database
\c solo

-- Create the extension
CREATE EXTENSION pg_cron;

-- Verify it's installed
SELECT * FROM pg_extension WHERE extname = 'pg_cron';
```

3. Schedule partition creation function
```SQL
-- Schedule the function to run at midnight on the first day of each month
SELECT cron.schedule('0 0 1 * *', $$SELECT metrics.create_partitions()$$);

-- List all scheduled jobs
SELECT * FROM cron.job;
```

```SQL
-- Analyze tables to update statistics
ANALYZE metrics.system_metrics;

-- Vacuum to reclaim space
VACUUM FULL metrics.system_metrics_y2025m01;
```
