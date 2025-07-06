from typing import Dict, List, Optional, Any
import json
import asyncpg
from datetime import datetime, timedelta

from app.core.db.connection import get_connection_pool

class MetricsDatabase:
    """
    Database service for metrics operations
    """

    async def log_system_metrics(self, metrics: Dict[str, float]):
        """Log system metrics to the database

        Args:
            metrics: Dictionary of system metrics
        """
        pool = await get_connection_pool()
        async with pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO metrics.system_metrics
                (cpu_percent, cpu_temperature, memory_percent, memory_used_mb,
                memory_temperature, gpu_percent, gpu_fans_rpm, gpu_watt,
                gpu_temperature, vram_percent, vram_used_mb,
                system_uptime_seconds, app_uptime_seconds)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ''',
            metrics.get('cpu_percent'), metrics.get('cpu_temperature'),
            metrics.get('memory_percent'), metrics.get('memory_used_mb'),
            metrics.get('memory_temperature'), metrics.get('gpu_percent'),
            metrics.get('gpu_fans_rpm'), metrics.get('gpu_percent'),
            metrics.get('gpu_temperature'), metrics.get('vram_percent'),
            metrics.get('vram_used_mb'), metrics.get('system_uptime_seconds'),
            metrics.get('app_uptime_seconds'))

        async def log_llm_metrics(self,
                                  model_id: str,
                                  session_id: Optional[str],
                                  request_id: str,
                                  tokens_generated: int,
                                  generation_time_ms: float,
                                  tokens_per_second: Optional[float] = None,
                                  cache_hit: bool = False,
                                  prompt_tokens: Optional[int] = None,
                                  total_tokens: Optional[int] = None,
                                  parameters: Optional [Dict[str, Any]] = None):
            """Log LLM generation metrics

            Args:
                model_id: ID of the model used
                session_id: Session ID (optional)
                request_id: Unique request ID
                tokens_generated: Number of tokens generated
                generation_time_ms: Generation time in milliseconds
                tokens_per_second: Tokens per second (optional)
                cache_hit: Whether this was a cache hit
                prompt_tokens: Number of tokens in the prompt (optional)
                total_tokens: Total tokens used (optional)
                parameters: Generation parameters (optional)
            """
            if tokens_generated is None and generation_time_ms > 0:
                tokens_per_second = (tokens_generated / generation_time_ms) * 1000

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO metrics.llm_metrics
                    (model_id, session_id, request_id, tokens_generated,
                    generation_time_ms, tokens_per_second, cache_hit,
                    prompt_tokens, total_tokens, parameters)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ''',
                model_id, session_id, request_id, tokens_generated,
                generation_time_ms, tokens_per_second, cache_hit,
                prompt_tokens, total_tokens,
                json.dumps(parameters) if parameters else None)

        async def get_system_metrics(self,
                                     start_time: Optional[datetime] = None,
                                     end_time: Optional[datetime] = None,
                                     limit: int = 100):
            """ Get system metrics for a time range

            Args:
                start_time: Start time (optional)
                end_time: End time (optional)
                limit: Maximum number of records to reutrn
            Returns:
                List of system metrics records
            """
            if start_time is None:
                start_time = datetime.now() - timedelta(hours=24)

            if end_time is None:
                end_time = datetime.now()

            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                records = await conn.fetch('''
                    SELECT * FROM metrics.system_metrics
                    WHERE timestamp BETWEEN $1 and $2
                    ORDER BY timestamp DESC
                    LIMIT $3
                ''', start_time, end_time, limit)
