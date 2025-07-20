from typing import Dict, List, Optional, Any
import json
import asyncpg
from datetime import datetime, timedelta
from utils.logger import get_logger
from core.db.connection import get_connection_pool
from pydantic import BaseModel, Field

class SystemMetrics(BaseModel):
    """ Pydantic model for system metrics data """
    cpu_percent: float
    cpu_temperature: float
    memory_percent: float
    memory_used_mb: float
    memory_temperature: float
    gpu_percent: float
    gpu_temperature: float
    gpu_fans_rpm: float
    gpu_watt: float
    vram_percent: float
    vram_used_mb: float
    network_received: float
    network_sent: float
    disk_writes_s_C: float
    disk_reads_s_C: float
    disk_writes_s_D: float
    disk_reads_s_D : float
    system_uptime_seconds: float
    app_uptime_seconds: float
    timestamp: Optional[datetime] = None

class LLMMetrics(BaseModel):
    """ Pydantic model for LLM metrics data """
    model_id: str
    session_id: str
    request_id: str
    tokens_generated: int
    generation_time_ms: float
    tokens_per_second: float
    cache_hit: bool
    prompt_tokens: int
    total_tokens: int
    parameters: Dict
    timestamp: Optional[datetime] = None

class SystemMetricsResponse(BaseModel):
    """ Response model for system metrics queries """
    metrics: List[SystemMetrics]
    count: int

class LLMMetricsResponse(BaseModel):
    """ Response model for LLM metrics queries """
    metrics: List[LLMMetrics]
    count: int

class ModelUsageSummary(BaseModel):
    """ Summary metrics for LLM operations """
    request_count: int
    total_tokens: int
    avg_tokens_per_second: float
    avg_generation_time_ms: float
    cache_hits: int

class LLMSummary(BaseModel):
    """ Summary metrics for LLM operations """
    request_count: int
    total_tokens: int
    avg_tokens_per_second: float
    avg_generation_time_ms: float
    cache_hits: int

class SystemSummary(BaseModel):
    """ Summary metrics for system performance """
    avg_cpu_percent: float
    avg_memory_percent: float
    avg_gpu_percent: float
    max_cpu_percent: float
    max_memory_percent: float
    max_gpu_percent: float

class TimePeriod(BaseModel):
    """ Time period for metrics queries """
    start: str
    end: str
    duration_hours: float

class MetricsSummary(BaseModel):
    """ Complete metrics summar response """
    time_period: TimePeriod
    llm: Optional[LLMSummary] = None
    system: Optional[SystemSummary] = None
    models: List[ModelUsageSummary] = []
    error: Optional [str] = None

class MetricsDatabase:
    """
    Database service for metrics operations
    """
    def __init__(self):
        """Initialize the metrics database service"""
        self.logger = get_logger("metrics_db")

    async def initialize(self):
        """Initialize the metrics database service"""
        try:
            # Verify tables exist or create if needed
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                # Check if metrics schema exists
                schema_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname = 'metrics')"
                )

                if not schema_exists:
                    self.logger.warning("Metrics schema doesn't exist. Some metrics operations may fail.")

            self.logger.info("Metrics database service initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize metrics database service: {e}")
            return False

    async def log_system_metrics(self, metrics: SystemMetrics) -> bool:
        """
        Log system metrics to the database

        Args:
            metrics: SystemMetrics model with all system metrics data

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            pool = await get_connection_pool()
            async with pool.aqurire() as conn:
                # convert Pydantic to dict
                metrics_dict = metrics.model_dump()

                # create SQL query with placeholders
                columns = ", ".join(metrics_dict.keys())
                placeholders = ", ".join([f"${i+1}" for i in range(len(metrics_dict))])

                query = f"""
                    INSERT INTO metrics.system_metrics
                    (timestamp,{columns})
                    VALUES (NOW(), {placeholders})
                """
                # extract values in same order as columns
                values = list(metrics_dict.values())

                await conn.execute(query, *values)
                return True
        except Exception as e:
            self.logger.error(f"Failed to log system metrics: {str(e)}")
            return False

    async def log_llm_metrics(self, metrics: LLMMetrics) -> bool:
        """
        Log LLM generation metrics to the database

        Args:
            metrics: LLMMetrics model with all LLM metrics data

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Calculate tokens per second if not provided
            if metrics.tokens_per_second is None and metrics.generation_time_ms > 0:
                metrics.tokens_per_second = (metrics.tokens_generated / (metrics.generation_time_ms / 1000))

            # Convert Pydantic model to dict for DB insertion
            metrics_dict = metrics.model_dump()

            # Handle JSON serialization for parameters field
            if metrics_dict.get('parameters'):
                metrics_dict['parameters'] = json.dumps(metrics_dict['parameters'])

            # Create a SQL query with columns and placeholders
            columns = ", ".join(metrics_dict.keys())
            placeholders = ", ".join([f"${i+1}" for i in range(len(metrics_dict))])

            query = f"""
                INSERT INTO metrics.llm_metrics
                (timestamp, {columns})
                VALUES (NOW(), {placeholders})
            """

            # Extract values in the same order as columns
            values = list(metrics_dict.values())

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                await conn.execute(query, *values)

            self.logger.debug(f"Logged LLM metrics for model {metrics.model_id}: {metrics.tokens_generated} tokens in {metrics.generation_time_ms}ms")
            return True
        except Exception as e:
            self.logger.error(f"Failed to log LLM metrics: {str(e)}")
            return False

    async def get_system_metrics(self,
                               start_time: Optional[datetime] = None,
                               end_time: Optional[datetime] = None,
                               limit: int = 100) -> SystemMetricsResponse:
        """Get system metrics for a time range

        Args:
            start_time: Start time (optional)
            end_time: End time (optional)
            limit: Maximum number of records to return

        Returns:
            SystemMetricsResponse with metrics list and count
        """
        try:
            if start_time is None:
                start_time = datetime.now() - timedelta(hours=24)

            if end_time is None:
                end_time = datetime.now()

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                records = await conn.fetch("""
                    SELECT * FROM metrics.system_metrics
                    WHERE timestamp BETWEEN $1 AND $2
                    ORDER BY timestamp DESC
                    LIMIT $3
                """, start_time, end_time, limit)

                # Convert records to Pydantic models
                metrics = []
                for record in records:
                    record_dict = dict(record)
                    metrics.append(SystemMetrics(**record_dict))

                return SystemMetricsResponse(
                    metrics=metrics,
                    count=len(metrics)
                )
        except Exception as e:
            self.logger.error(f"An error occurred getting system metrics: {str(e)}")
            return SystemMetricsResponse(metrics=[], count=0)

    async def get_llm_metrics(self,
                            start_time: Optional[datetime] = None,
                            end_time: Optional[datetime] = None,
                            model_id: Optional[str] = None,
                            session_id: Optional[str] = None,
                            limit: int = 100) -> LLMMetricsResponse:
        """Get LLM metrics for a time range and optional filters

        Args:
            start_time: Start time (optional)
            end_time: End time (optional)
            model_id: Filter by model ID (optional)
            session_id: Filter by session ID (optional)
            limit: Maximum number of records to return

        Returns:
            LLMMetricsResponse with metrics list and count
        """
        try:
            if start_time is None:
                start_time = datetime.now() - timedelta(hours=24)

            if end_time is None:
                end_time = datetime.now()

            query = """
                    SELECT * FROM metrics.llm_metrics
                    WHERE timestamp BETWEEN $1 AND $2
                """
            params = [start_time, end_time]

            if model_id:
                query += f" AND model_id = ${len(params) + 1}"
                params.append(model_id)

            if session_id:
                query += f" AND session_id = ${len(params) + 1}"
                params.append(session_id)

            query += f" ORDER BY timestamp DESC LIMIT ${len(params) + 1}"
            params.append(limit)

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                records = await conn.fetch(query, *params)

                # Convert records to Pydantic models
                metrics = []
                for record in records:
                    record_dict = dict(record)
                    # Parse JSON parameters if they exist
                    if record_dict.get('parameters'):
                        record_dict['parameters'] = json.loads(record_dict['parameters'])
                    metrics.append(LLMMetrics(**record_dict))

                return LLMMetricsResponse(
                    metrics=metrics,
                    count=len(metrics)
                )
        except Exception as e:
            self.logger.error(f"An error occurred getting LLM metrics: {str(e)}")
            return LLMMetricsResponse(metrics=[], count=0)

    async def get_metrics_summary(self,
                                start_time: Optional[datetime] = None,
                                end_time: Optional[datetime] = None) -> MetricsSummary:
        """Get a summary of metrics for a time period

        Args:
            start_time: Start Time (optional)
            end_time: End Time (optional)

        Returns:
            MetricsSummary with aggregated metrics data
        """
        try:
            if start_time is None:
                start_time = datetime.now() - timedelta(hours=24)

            if end_time is None:
                end_time = datetime.now()

            pool = await get_connection_pool()
            async with pool.acquire() as conn:  # Fixed typo from "aquire" to "acquire"
                # LLM metrics summary
                llm_summary = await conn.fetchrow('''
                    SELECT
                        COUNT(*) as request_count,
                        SUM(tokens_generated) as total_tokens,
                        AVG(tokens_per_second) as avg_tokens_per_second,
                        AVG(generation_time_ms) as avg_generation_time_ms,
                        SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) as cache_hits
                    FROM metrics.llm_metrics
                    WHERE timestamp BETWEEN $1 AND $2
                ''', start_time, end_time)

                # System metrics summary (average values)
                system_summary = await conn.fetchrow('''
                    SELECT
                        AVG(cpu_percent) as avg_cpu_percent,
                        AVG(memory_percent) as avg_memory_percent,
                        AVG(gpu_percent) as avg_gpu_percent,
                        MAX(cpu_percent) as max_cpu_percent,
                        MAX(memory_percent) as max_memory_percent,
                        MAX(gpu_percent) as max_gpu_percent
                    FROM metrics.system_metrics
                    WHERE timestamp BETWEEN $1 AND $2
                ''', start_time, end_time)

                # Model usage stats
                model_usage_records = await conn.fetch('''
                    SELECT
                        model_id,
                        COUNT(*) as usage_count,
                        AVG(tokens_per_second) as avg_tokens_per_second,
                        SUM(tokens_generated) as total_tokens
                    FROM metrics.llm_metrics
                    WHERE timestamp BETWEEN $1 AND $2
                    GROUP BY model_id
                    ORDER BY usage_count DESC
                ''', start_time, end_time)

                # Create Pydantic models from query results
                time_period = TimePeriod(
                    start=start_time.isoformat(),
                    end=end_time.isoformat(),
                    duration_hours=(end_time - start_time).total_seconds() / 3600
                )

                llm_summary_model = None
                if llm_summary:
                    llm_summary_model = LLMSummary(**dict(llm_summary))

                system_summary_model = None
                if system_summary:
                    system_summary_model = SystemSummary(**dict(system_summary))

                model_usage_models = []
                if model_usage_records:
                    for record in model_usage_records:
                        model_usage_models.append(ModelUsageSummary(**dict(record)))

                return MetricsSummary(
                    time_period=time_period,
                    llm=llm_summary_model,
                    system=system_summary_model,
                    models=model_usage_models
                )
        except Exception as e:
            self.logger.error(f"Failed to retrieve metrics summary: {e}")
            return MetricsSummary(
                time_period=TimePeriod(
                    start=start_time.isoformat() if start_time else None,
                    end=end_time.isoformat() if end_time else None,
                    duration_hours=0
                ),
                error=str(e)
            )
