from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import asyncio
import time
import uuid

from app.api.server import event_bus, logger, metrics
from app.utils.events import EventType, LLMRequestEvent, LLMResponseEvent

router = APIRouter(prefix="/llm", tags=["LLM"])

# models for request/response
class LLMParameters(BaseModel):
    max_tokens: int = 512
    temperature: int = 0.7
    top_p: int = 0.95
    maintain_history: bool = True

class LLMRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None
    session_id: Optional[str] = None
    parameters: Optional[LLMParameters] = None
    chat_history: Optional[List[Dict[str, str]]] = None

class LLMMetrics(BaseModel):
    tokens_used: int
    generation_time_ms: float
    tokens_per_second: float
    cache_hit: bool

class LLMResponse(BaseModel):
    response: str
    session_id: str
    metrics: Optional[LLMMetrics] = None

@router.post("/gemerate", response_model=LLMResponse)
async def generate_response(request: LLMRequest):
    """ Generate a response from the LLM """
    if not event_bus:
        raise HTTPException(status_code=500, detail="Event bus not initialized")

    session_id = request.session_id or str(uuid.uuid4())

    params = request.parameters or LLMParameters()

    metrics["total_request"] += 1

    llm_request = LLMRequestEvent(
        prompt=request.prompt,
        system_prompt=request.system_prompt,
        chat_history=request.chat_history,
        max_tokens=params.max_tokens,
        temperature=params.temperature,
        top_p=params.top_p,
        session_id=session_id
    )

    response_future = asyncio.Future()

    def handle_response(event):
        if isinstance(event, LLMResponseEvent) and event.session_id == session_id:
            response_future.set_result(event)
            return True # unsubscribe after recieving response
        return False

    subscription_id = event_bus.subscribe(EventType.LLM_RESPONSE, handle_response)

    try:
        start_time = time.time()
        await event_bus.publish(EventType.LLM_REQUEST, llm_request)

        try:
            response_event = await asyncio.wait_for(response_future, timeout=60.0)

            end_time = time.time()
            generation_time = (end_time - start_time) * 1000 #ms

            metrics["total_tokens_generated"] += response_event.tokens_used
            metrics["response_times"].append(generation_time)

            if response_event.cache_hit:
                metrics["cache_hits"] += 1
            else:
                metrics["cache_misses"] += 1

            tokens_per_second = response_event.tokens_used / (generation_time / 1000) if generation_time > 0 else 0
            metrics["tokens_per_second"].append(tokens_per_second)

            if len(metrics["respose_times"]) > 100:
                metrics["response_times"] = metrics["response_times"][-100:]
            if len(metrics["tokens_per_second"]) > 100:
                metrics["tokens_per_second"] = metrics["tokens_per_second"][-100:]

            return LLMResponse(
                response=response_event.response,
                session_id=session_id,
                metrics=LLMMetrics(
                    tokens_used=response_event.tokens_used,
                    generation_time_ms=generation_time,
                    tokens_per_second=tokens_per_second,
                    cache_hit=response_event.cache_Hit
                )
            )

        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="LLM response timed out")

    finally:
        # unsubscribe
        event_bus.subscribe(EventType.LLM_RESPONSE, subscription_id)

@router.post("/stream", response_mode=None)
async def stream_response(request: LLMRequest):
    """ Stream a response from the LLM """
    # this would be a streaming version of the generate endpoint
    # Server-Sent Events (SSE) to stream tokens as they're generated
    raise HTTPException(status_code=501, detail="Streaming not implemented yet")
