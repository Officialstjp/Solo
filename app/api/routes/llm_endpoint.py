"""
Moduele Name: app/api/routes/llm_endpoints.py
Purpose: API endpoints for LLM interactions
History   :
    Date          Notes
    2025-06-08    Initial implementation
    2025-07-19    Added database integration
"""

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import asyncio
import time
import uuid
import json

from app.utils.events import EventBus, EventType, LLMRequestEvent, LLMResponseEvent, ModelLoadRequestEvent, ModelLoadedEvent, SessionClearEvent
from app.core.model_manager import ModelManager
from app.core.model_service import ModelService
from app.core.prompt_templates import PromptLibrary
from app.core.db_service import DatabaseService
from app.core.db.users_db import MessageCreate, ConversationCreate
from app.api.dependencies import get_event_bus, get_model_manager, get_model_service, get_prompt_library, get_metrics, get_db_service
from app.utils.logger import get_logger

logger = get_logger(name="LLM_API", json_format=False)

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
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None

class LLMResponse(BaseModel):
    response: str
    session_id: str
    conversation_id: Optional[str] = None
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

    @router.post("/generate", response_model=LLMResponse)
    async def generate_text(
        request: Request,
        llm_request: LLMRequest,
        event_bus: EventBus = Depends(get_event_bus),
        model_service: ModelService = Depends(get_model_service),
        prompt_library: PromptLibrary = Depends(get_prompt_library),
        metrics: dict = Depends(get_metrics),
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """Generate text from the LLM based on the provided prompt"""
        try:
            # Validate and prepare the request
            user = getattr(request.state, "user", None) if llm_request.user_id else None
            session_id = llm_request.session_id or f"session_{uuid.uuid4().hex}"
            conversation_id = llm_request.conversation_id

            if user and not conversation_id:
                conversation_create = ConversationCreate(
                    session_id=session_id,
                    title=f"Conversation {time.strftime('%Y-%m-%d %H:%M:%S')}",
                )
                conversation = await db_service.create_conversation(
                    user_id=user.id,
                    conversation=conversation_create
                )

                if conversation:
                    conversation_id = conversation_id

            # set up params
            params = llm_request.parameters or LLMParameters()

            # get template if specified
            template = None
            if params.template_id:
                template = prompt_library.get_template(params.template_id)

            # Create LLM request event
            request_id = f"req_{uuid.uuid4().hex}"
            llm_event = LLMRequestEvent(
                request_id=request_id,
                session_id=session_id,
                prompt=llm_request.prompt,
                system_prompt=llm_request.system_prompt,
                chat_history=llm_request.chat_history,
                model_id=params.model_id,
                max_tokens=params.max_tokens,
                temperature=params.temperature,
                top_p=params.top_p,
                maintain_history=params.maintain_history,
                max_history=params.max_history,
                template=template
            )

            # Store user message in database if we have a user and conversation
            if user and conversation_id:
                message_create = MessageCreate(
                    conversation_id=conversation_id,
                    role="user",
                    content=llm_request.prompt,
                    request_id=request_id
                )

                user_message = await db_service.users.create_message(
                    user_id=user.user_id,
                    message=message_create
                )

            # Send request to LLM service
            await event_bus.publish(EventType.LLM_REQUEST, llm_event)

            # Wait for response
            response_event = await model_service.wait_for_response(request_id)

            if not response_event:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to generate response"
                )

            # Update metrics
            metrics["total_requests"] += 1
            metrics["total_tokens_generated"] += response_event.tokens
            if response_event.cache_hit:
                metrics["cache_hits"] += 1
            else:
                metrics["cache_misses"] += 1

            if response_event.generation_time > 0:
                tokens_per_second = response_event.tokens / (response_event.generation_time / 1000)
                metrics["tokens_per_second"].append(tokens_per_second)
                metrics["response_times"].append(response_event.generation_time)

            # Store assistant message in database if we have a user and conversation
            if user and conversation_id:
                message_create = MessageCreate(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=response_event.response,
                    request_id=request_id,
                    model_id=response_event.model_id,
                    tokens=response_event.tokens,
                    metadata={
                        "generation_time_ms": response_event.generation_time,
                        "cache_hit": response_event.cache_hit
                    }
                )

                assistant_message = await db_service.users.create_message(
                    user_id=user.user_id,
                    message=message_create
                )

            # Return the response
            return LLMResponse(
                response=response_event.response,
                session_id=session_id,
                conversation_id=conversation_id,
                metrics=LLMMetrics(
                    tokens_used=response_event.tokens,
                    generation_time_ms=response_event.generation_time,
                    tokens_per_second=tokens_per_second if response_event.generation_time > 0 else 0,
                    cache_hit=response_event.cache_hit,
                    model_name=response_event.model_id
                )
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error generating text: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate response: {str(e)}"
            )

    @router.post("/models/{model_id}/load", response_model=ModelLoadResponse)
    async def load_model(
        model_id: str,
        load_request: ModelLoadRequest,
        event_bus: EventBus = Depends(get_event_bus),
        model_service: ModelService = Depends(get_model_service),
        model_manager: ModelManager = Depends(get_model_manager),
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """ load a model into memory """
        try:
            model_info = model_manager.get_model_info(model_id)
            if not model_info:
                raise HTTPException(
                    status_code=404,
                    detail=f"Model '{model_id}' not found"
                )

            # Create load request event
            request_id = f"load_{uuid.uuid4().hex}"
            load_event = ModelLoadRequestEvent(
                request_id=request_id,
                model_id=model_id,
                priority=load_request.priority
            )
            await event_bus.publish(EventType.MODEL_LOAD_REQUEST, load_event)
            loaded_event = await model_service.wait_for_model_loaded(request_id)

            if not loaded_event:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to load model '{model_id}'"
                )
            # Log model load in database if available
            if db_service:
                try:
                    await db_service.models.log_model_load(
                        model_id=model_id,
                        success=loaded_event.success,
                        error=loaded_event.error if not loaded_event.success else None
                    )
                except Exception as db_err:
                    logger.warning(f"Failed to log model load in database: {str(db_err)}")

            if loaded_event.success:
                return ModelLoadResponse(
                    status="loaded",
                    model_id=model_id,
                    message=f"Model '{model_id}' loaded successfully"
                )
            else:
                return ModelLoadResponse(
                    status="error",
                    model_id=model_id,
                    message=f"Failed to load model: {loaded_event.error}"
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load model: {str(e)}"
            )

    @router.get("/models/{model_id}/status", response_model=ModelStatus)
    async def get_model_status(
        model_id: str,
        model_service: ModelService = Depends(get_model_service),
        model_manager: ModelManager = Depends(get_model_manager)
    ):
        """Get the status of a model"""
        try:
            # Check if model exists
            model_info = model_manager.get_model_info(model_id)
            if not model_info:
                raise HTTPException(
                    status_code=404,
                    detail=f"Model '{model_id}' not found"
                )

            # Check if model is loaded
            loaded = model_id in model_service.models
            loading = model_id in model_service.loading_models

            status = "loaded" if loaded else "loading" if loading else "not_loaded"

            # Get last used time if available
            last_used = model_service.last_used.get(model_id)

            return ModelStatus(
                model_id=model_id,
                loaded=loaded,
                status=status,
                last_used=last_used,
                error=None
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting model status: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get model status: {str(e)}"
            )

    @router.post("/sessions/{session_id}/clear")
    async def clear_session(
        session_id: str,
        event_bus: EventBus = Depends(get_event_bus),
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """Clear a session's history"""
        try:
            # Create clear session event
            clear_event = SessionClearEvent(
                session_id=session_id
            )
            await event_bus.publish(EventType.SESSION_CLEAR, clear_event)

            # If we have a database connection, also clear from DB
            if db_service:
                try:
                    # Note: This still requires a method in users_db to clear session history
                    # await db_service.users.clear_session_history(session_id)
                    pass
                except Exception as db_err:
                    logger.warning(f"Failed to clear session history in database: {str(db_err)}")

            return {"message": f"Session '{session_id}' cleared"}

        except Exception as e:
            logger.error(f"Error clearing session: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to clear session: {str(e)}"
            )

    @router.post("/stream", response_model=None)
    async def stream_text(
        request: Request,
        llm_request: LLMRequest,
        event_bus: EventBus = Depends(get_event_bus),
        model_service: ModelService = Depends(get_model_service),
        prompt_library: PromptLibrary = Depends(get_prompt_library),
        metrics: dict = Depends(get_metrics),
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """ Stream text generation from the LLM"""
        async def generate():
            try:
                # validate and prepare the request
                user = getattr(request.state, "user", None) if llm_request.user_id else None
                session_id = llm_request.session_id or f"session_{uuid.uuid4().hex}"
                conversation_id = llm_request.conversation_id
                if user and not conversation_id:
                    conversation_create = ConversationCreate(
                        session_id=session_id,
                        title=f"Conversation {time.strftime('%Y-%m-%d %H:%M:%S')}",
                    )
                    conversation = await db_service.create_conversation(
                        user_id=user.id,
                        conversation=conversation_create
                    )

                    if conversation:
                        conversation_id = conversation.id

                # set up params
                params = llm_request.parameters or LLMParameters()
                template = None
                if params.template_id:
                    template = prompt_library.get_template(params.template_id)

                # Create LLM request event
                request_id = f"req_{uuid.uuid4().hex}"
                llm_event = LLMRequestEvent(
                    request_id=request_id,
                    session_id=session_id,
                    prompt=llm_request.prompt,
                    system_prompt=llm_request.system_prompt,
                    chat_history=llm_request.chat_history,
                    model_id=params.model_id,
                    max_tokens=params.max_tokens,
                    temperature=params.temperature,
                    top_p=params.top_p,
                    maintain_history=params.maintain_history,
                    max_history=params.max_history,
                    template=template
                )

                # Store user message in database if we have a user and conversation
                if user and conversation_id:
                    message_create = MessageCreate(
                        conversation_id=conversation_id,
                        role="user",
                        content=llm_request.prompt,
                        request_id=request_id
                    )

                    user_message = await db_service.users.create_message(
                        user_id=user.user_id,
                        message=message_create
                    )

                # Send request to LLM service
                await event_bus.publish(EventType.LLM_REQUEST, llm_event)

                # initial response data
                response_data = {
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                    "request_id": request_id,
                    "text": "",
                    "don": False,
                }

                # Subscribe to streaming events
                full_text = ""
                async for token in model_service.stream_response(request_id):
                    full_text += token
                    response_data["text"] = token
                    yield f"data: {json.dumps(response_data)}\n\n"

                # final update with completion flag
                response_data["done"] = True
                response_data["text"] = ""
                yield f"data: {json.dumps(response_data)}\n\n"

                # Get final response metrics
                response_event = await model_service.get_stream_completion(request_id)

                if response_event:
                    metrics["total_requests"] += 1
                    metrics["total_tokens_generated"] += response_event.tokens
                    if response_event.cache_hit:
                        metrics["cache_hits"] += 1
                    else:
                        metrics["cache_misses"] += 1

                # Store assistant message in database if we have a user and conversation
                if user and conversation_id and response_event:
                    message_create = MessageCreate(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=full_text,
                        request_id=request_id,
                        model_id=response_event.model_id,
                        tokens=response_event.tokens,
                        metadata={
                            "generation_time_ms": response_event.generation_time,
                            "cache_hit": response_event.cache_hit
                        }
                    )

                    assistant_message = await db_service.users.create_message(
                        user_id=user.user_id,
                        message=message_create
                    )
            except Exception as e:
                logger.error(f"Error in streaming text generation: {str(e)}", exc_info=True)
                error_data = {
                    "error": str(e),
                    "done": True,
                }
                yield f"data: {json.dumps(error_data)}\n\n"
        return StreamingResponse(generate(), media_type="text/event-stream")

    return router
