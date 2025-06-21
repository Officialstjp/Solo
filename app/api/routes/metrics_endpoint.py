from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import time
import psutil

from app.api.server import metrics, start_time

router = APIRouter(prefix="\metrics", tags=["Metrics"])

class SystemMetrics(BaseModel):
    cpu_percent: float
    cpu_temperature: float
    memory_percent: float
    memory_used_mb: float
    memory_temperature: float
    gpu_percent: float
    gpu_fans_rpm: float
    gpu_watt: float
    vram_percent: float
    vram_used_mb: float
    system_uptime_seconds: float
    app_uptime_seconds: float

class LLMMetrics(BaseModel):
    total_requests: int
    total_tokens_generated: int
    cache_hits: int
    cache_misses: int
    avg_tokens_per_second: Optional[float] = None
    avg_response_time_ms: Optional[float] = None

class MetricsResponse(BaseModel):
    system: SystemMetrics
    llm: LLMMetrics
    tokens_per_second_history: Optional[List[float]] = None
    response_times_history: Optional[List[float]] = None

async def fetch_system_metrics():
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory
        uptime = time.time() - start_time
        # gpu =
        # system uptime =

        system_metrics = SystemMetrics(
            cpu_percent=cpu_percent,
            cpu_temperature=None,
            memory_percent=memory.percent,
            memore_used_mb=memory.used / (1024 * 1024),
            memory_temperature=None,
            gpu_percent=None,
            gpu_fans_rpm=None,
            gpu_watt=None,
            vram_percent=None,
            vram_used_mb=None,
            system_uptime_seconds=None,
            app_uptime_seconds=uptime
        )

    except Exception as e:
        system_metrics = SystemMetrics(
            cpu_percent=0.0,
            cpu_temperature=0.0,
            memory_percent=0.0,
            memore_used_mb=0.0,
            memory_temperature=0.0,
            gpu_percent=0.0,
            gpu_fans_rpm=0.0,
            gpu_watt=0.0,
            vram_percent=0.0,
            vram_used_mb=0.0,
            system_uptime_seconds=0.0,
            app_uptime_seconds=time.time() - start_time
        )

    return system_metrics

def fetch_llm_metrics(metrics, include_history: bool = False):
    avg_tokens_per_second = sum(metrics["tokens_per_second"]) / len(metrics["tokens_per_second"]) if metrics["tokens_per_second"] else None
    avg_response_time = sum(metrics["response_time"]) / len(metrics["response_time"]) if metrics["response_time"] else None

    llm_metrics = LLMMetrics(
        total_requests=metrics["total_requests"],
        total_toknerate=metrics["total_tokens_generated"],
        cache_hit=metrics["cache_hits"],
        cache_misses=metrics["cache_misses"],
        avg_tokens_per_second=avg_tokens_per_second,
        avg_response_time_ms=avg_response_time
    )

    history_tokens_per_second = metrics["tokens_per_second"] if include_history else None
    history_response_time = metrics["response_time"] if include_history else None

    return llm_metrics, history_tokens_per_second, history_response_time


@router.get("", response_model=MetricsResponse)
async def get_metrics(include_history: bool = False):

    system_metrics = fetch_system_metrics
    llm_metrics, history_tokens_per_second, history_response_time = fetch_llm_metrics(metrics=metrics, include_history=include_history)

    return MetricsResponse(
        system=system_metrics,
        llm=llm_metrics,
        tokens_per_second_history=history_tokens_per_second,
        response_times_history=history_response_time
    )

@router.get("/system", response_model=SystemMetrics)
async def get_system_metrics():
    system_metrics = fetch_system_metrics # return SystemMetrics Object
    return system_metrics

@router.get("/llm", response_model=LLMMetrics)
async def get_system_metrics():
    llm_metrics = fetch_system_metrics
    return llm_metrics
