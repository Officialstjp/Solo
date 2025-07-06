"""
Moduele Name: app/api/routes/llm_endpoints.py
Purpose: API endpoints for LLM interactions
"""

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import asyncio
import time
import uuid

from app.utils.events import EventBus, EventType, LLMRequestEvent, LLMResponseEvent, ModelLoadRequestEvent, ModelLoadedEvent, SessionClearEvent
from app.core.model_manager import ModelManager
from app.core.model_service import ModelService
from app.core.prompt_templates import PromptLibrary
from app.core.db_service import DatabaseService
from app.api.dependencies import get_event_bus, get_model_manager, get_model_service, get_prompt_library, get_metrics, get_db_service
from app.utils.logger import get_logger

logger = get_logger(name="LLM_API", json_foramt=False)

# Parameter and metrics basemodels
class LLMParameters(BaseModel):
    model_id: Optional[str] = None
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.95
    maintain_history: bool = True
    max_history: int = 10
    template_id: Optional[str] = None

class LLMMetrics(BaseModel):
    tokens_used: int
    generation_time_ms: float
    tokens_per_second: float
    cache_hit: bool
    model_name: str

# models for request/response
class LLMRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None
    session_id: Optional[str] = None
    parameters: Optional[LLMParameters] = None
    chat_history: Optional[List[Dict[str, str]]] = None

class LLMResponse(BaseModel):
    response: str
    session_id: str
    metrics: Optional[LLMMetrics] = None

# Model loading and status models
class ModelLoadRequest(BaseModel):
    priority: bool = False

class ModelLoadResponse(BaseModel):
    status: str
    model_id: str
    message: Optional[str] = None

class ModelStatus(BaseModel):
    model_id: str
    loaded: bool
    status: str  # "loaded", "loading", "not_loaded", "error"
    last_used: Optional[float] = None
    error: Optional[str] = None


def create_router(app: FastAPI) -> APIRouter:
    """
    Create and configure the LLM router
    Args:
        app: The FastAPI application instance

    Returns:
        APIRouter: configured router with LLM endpoints
    """
    router = APIRouter(prefix="/llm", tags=["LLM"])

    @router.post("/gemerate", response_model=LLMResponse)
    async def generate_text(
        request: LLMRequest,
        event_bus: EventBus = Depends(get_event_bus),
        model_manager: ModelManager = Depends(get_model_manager),
        prompt_library: PromptLibrary = Depends(get_prompt_library),
        metrics: dict = Depends(get_metrics),
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """
        Generate text using the LLM
        """
        try:
            if not event_bus:
                raise HTTPException(status_code=500, detail="Event bus not initialized")

            session_id = request.session_id or str(uuid.uuid4())

            params = request.parameters or LLMParameters()

            metrics["total_requests"] = metrics.get("total_requests", 0) + 1

            llm_request = LLMRequestEvent(
                prompt=request.prompt,
                system_prompt=request.system_prompt,
                chat_history=request.chat_history,
                session_id=session_id,
                parameters={
                    "model_id": params.model_id,
                    "max_tokens": params.max_tokens,
                    "temperature": params.temperature,
                    "top_p": params.top_p,
                    "maintain_history": params.maintain_history,
                    "max_history": params.max_history,
                    "template_id": params.template_id
                }
            )
            # create a future to wait for the response
            response_future = asyncio.Future()

            async def handle_response(event):
                if isinstance(event, LLMResponseEvent) and event.session_id == session_id:
                    response_future.set_result(event)
                    return True # unsubscribe after recieving response
                return False

            # subsribe to responses
            subscription_id = await event_bus.subscribe_with_handler(
                EventType.LLM_RESPONSE,
                handle_response
            )

            try:
                start_time = time.time()
                await event_bus.publish(EventType.LLM_REQUEST, llm_request)

                try:
                    # wait for response with timeout
                    response_event = await asyncio.wait_for(response_future, timeout=60.0)

                    end_time = time.time()
                    generation_time = (end_time - start_time) * 1000 #ms

                    metrics["total_tokens_generated"] = metrics.get("total_tokens_generated", 0) + response_event.tokens_used
                    metrics.setdefault("response_times", []).append(generation_time)

                    tokens_per_second = response_event.tokens_used / (generation_time / 1000) if generation_time > 0 else 0
                    metrics["tokens_per_second"].append(tokens_per_second)

                    if hasattr(response_event, "cached") and response_event.cached:
                        metrics["cache_hits"] = metrics.get("cache_hits", 0) + 1
                    else:
                        metrics.setdefault("cache_misses", []).append(response_event.model_name)

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
                            cache_hit=getattr(response_event, "cached", False),
                            model_name=response_event.model_name
                        )
                    )

                except asyncio.TimeoutError:
                    raise HTTPException(status_code=504, detail="LLM response timed out")

            finally:
                # unsubscribe
                event_bus.subscribe(EventType.LLM_RESPONSE, subscription_id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error generating text: {str(e)}", ecx_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to generate text: {str(e)}")

    @router.post("/models/{model_id}/load", response_model=ModelLoadResponse)
    async def load_model(
        model_id: str,
        request: ModelLoadRequest,
        event_bus: EventBus = Depends(get_event_bus),
        model_manager: ModelManager = Depends(get_model_manager)
    ):
        """ Explicitly load a model into memory """
        try:
            model = model_manager.get_model(model_id)
            if not model:
                raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

            # create a future to wait for the response
            load_future = asyncio.Future()

            async def handle_model_loaded(event):
                if (isinstance(event, ModelLoadedEvent) and
                    event.model_id == model_id):
                    load_future.set_result(event)
                    return True
                return False

            subscription_id = await event_bus.subsribe_with_handler(
                EventType.MODEL_LOADED,
                handle_model_loaded
            )

            try:
                await event_bus.publish(ModelLoadRequestEvent(
                    model_id=model_id,
                    priority=request.priority
                ))

                try:
                    loaded_event = await asyncio.wait_for(load_future, timeout=60.0)

                    if loaded_event.success:
                        return ModelLoadResponse(
                            status="success",
                            model_id=model_id,
                            message="Model loaded successfully"
                        )
                    else:
                        return ModelLoadResponse(
                            status="error",
                            model_id=model_id,
                            message=f"Failed to load model: {loaded_event.error_message}"
                        )

                except asyncio.TimeoutError:
                    raise HTTPException(status_code=504, detail="Model loading timed out")

            finally:
                # unsubscribe to avoid memory leaks
                await event_bus.unsubscribe(subscription_id)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to load model: {str(e)}")

    @router.get("/models/{model_id}/status", response_model=ModelStatus)
    async def get_model_status(
        model_id: str,
        model_service: ModelService = Depends(get_model_service)
    ):
        """
        Get the status of a specific model
        """
        try:
            model_info = model_service.model_manager.get_model(model_id)
            if not model_info:
                raise HTTPException(status_coed=404, detail=f"Model {model_id} not found")

            # check if model is loaded
            is_loaded = model_id in model_service.models
            is_loading = model_id in model_service.loading_models

            status = "loading" if is_loading else "loaded" if is_loaded else "not_loaded"
            last_used = model_service.model_last_used.get(model_id)

            return ModelStatus(
                model_id=model_id,
                loaded=is_loaded,
                status=status,
                last_used=last_used
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting model status: {str(e)}")
            raise HTTPException(status=500, detail=f"Failed to get model status: {str(e)}")

    @router.post("/sessions/{session_id}/clear")
    async def clear_session(
        session_id: str,
        event_bus: EventBus = Depends(get_event_bus)
    ):
        """
        Clear a converstaion session
        """
        try:
            await event_bus.publish(SessionClearEvent(session_id=session_id))

            return {
                "status": "success",
                "message": f"Session {session_id} cleared"
            }
        except Exception as e:
            logger.error(f"Error clearing session: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to clear session: {str(e)}")

    @router.post("/stream", response_model=None)
    async def stream_response(request: LLMRequest):
        """
        Stream a response from the LLM

        This would be a streaming version of the generate endpoint using
        Server-Sent Events (SSE) to stream tokens as they're generated
        """
        raise HTTPException(status_code=501, detail="Streaming not implemented yet")

    """
    @router.get("/", response_model=[Response Model class])
    async def xyz(response: [Response Model Class])

    @router.post("/", response_model=None)
    async def xyz(request: [Request Model Class])
    """

    return router
