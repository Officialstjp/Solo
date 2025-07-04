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
1. **Query Performance**:
```SQL
-- Only accesses July 2025 partition
SELECT * FROM metrics.system_metrics
WHERE timestamp BETWEEN '2025-07-01' AND '2025-07-31';
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

How to Implement Range Partitioning for Time-Series Data
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

Automating Partition Creation
For a production system, you would typically create a function to automatically create future partitions:
``` SQL
CREATE OR REPLACE FUNCTION metrics.create_month_partition()
RETURNS VOID AS $$
DECLARE
    next_month DATE;
    partition_name TEXT;
    start_date TEXT;
    end_date TEXT;
BEGIN
    -- Calculate the first day of next month
    next_month -= date_trunc('month', now()) + interval '1 Month';

    -- Generate partition name (e.g., system_metrics_y2025m08)
    partition_name := 'metrics.system_metrics' ||
                      to_char(next_month, 'YYYY') ||
                      'm' ||
                      to_char(next_month, 'MM');

    -- Format date ranges
    start_date := to_char(next_month, 'YYYY-MM-DD');
    end_date := to_char(next_month + interval '1 month', 'YYYY-MM-DD');

    -- Create the partition if it doesn't exist
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %s PARTITION OF metrics.system_metrics
        FOR VALUES FROM (%L) TO (%L)',
        partition_name, start_date, end_date);

    RAISE NOTICE 'Created partition: %', partition_name;
END;
$$ LANGUAGE plpgsql;

-- Create a scheduled job to run monthly
-- (This requires pg_cron extension)
SELECT cron.schedule('0 0 1 * *', 'SELECT metrics.crete_month_partition()');
```

**Performance and Maintenance Considerations**
1. **Query Optimization**: Always include the partition key in your WHERE clause when possible

2. **Partition Pruning**: PostgreSQL can skip scanning irrelevant partitions, but only if queries use the partition key

3. **Indexing Strategy**: Create appropriate indexes on each partition (indexes are not inherited automatically)

4. **Constraint Exclusion**: Set constraint_exclusion = on in PostgreSQL configuration to optimize partition pruning

5. **Maintenance Windows**: Schedule routine maintenance during off-peak hours

```SQL
-- Analyze tables to update statistics
ANALYZE metrics.system_metrics;

-- Vacuum to reclaim space
VACUUM FULL metrics.system_metrics_y2025m01;
```
