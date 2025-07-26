"""
Module Name: app/core/llm_runner.py
Purpose   : Wrapper for llama.cpp inference with cuBLAS GPU acceleration
Params    : None
History   :
    Date            Notes
    2025-06-08      Init
    2025-06-15      Enhanced with model management and prompt templates

    TODO: Streaming support, async batching
"""

import os
from typing import Dict, Any, Optional, List, Union, Tuple
import asyncio
import time
from pathlib import Path
import uuid

from llama_cpp import Llama
from app.utils.logger import get_logger
from app.utils.events import EventBus, EventType, LLMRequestEvent, LLMResponseEvent, SessionClearEvent
from app.core.model_manager import ModelManager, ModelInfo, ModelFormat
from app.core.prompt_templates import PromptLibrary, PromptTemplate
from app.core.model_cache import ResponseCache

class LlamaModel:
    """ Wrapper for llama.cpp model inference """

    def __init__( # this init overwrites app.config config settings <- ============ LOOK AT ==========
            self,
            model_path: str,
            model_manager: Optional[ModelManager] = None,
            prompt_library: Optional[PromptLibrary] = None,
            n_ctx: int = 8192,  # context
            n_batch: int = 512,  # tokens per micro-batch
            n_threads: int = 12,  # CPU threads for offloaded layers
            n_threads_batch=12,   # CPU threads for batching phase
            n_gpu_layers: int = 35,  # -1 means use all layers on gpu
            prompt_template: Optional[str] = None,
            cache_dir: Optional[str] = None,
            cache_enabled: bool = True,
            verbose: bool = False,
    ):
        """ Initialize the LLM model """
        self.logger = get_logger("main")
        self.logger.info(f"Initializing LlamaModel with model: {model_path}")

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_batch = n_batch
        self.n_threads = n_threads
        self.n_threads_batch = n_threads_batch
        self.n_gpu_layers = n_gpu_layers

        # Set up model manager or use provided one
        self.model_manager = model_manager or ModelManager()

        # Get model info
        self.model_info = self.model_manager.get_model_info(model_path)
        if not self.model_info:
            # If not found in manager, analyze it
            self.model_info = self.model_manager.analyze_model(model_path)

        # Set up prompt library or use provided one
        self.prompt_library = prompt_library or PromptLibrary()

        # Determine prompt template to use
        self.prompt_template_name = prompt_template
        if not self.prompt_template_name:
            # Try to detect from model format
            template = self.prompt_library.get_template_for_model(self.model_info.format)
            self.prompt_template_name = template.name if template else "mistral"

        # Set up response cache
        self.cache = ResponseCache(
            cache_dir=cache_dir,
            enabled=cache_enabled
        )

        self.logger.info(f"Using prompt template: {self.prompt_template_name}")
        self.logger.info("Loading model, this may take a while...")
        start_time = time.time()

        try:
            self.model = Llama(
                model_path=model_path,
                n_ctx=n_ctx,
                n_batch=n_batch,
                n_threads=n_threads,
                n_threads_batch=n_threads_batch,
                n_gpu_layers=n_gpu_layers,
                verbose=verbose,
            )
            load_time = time.time() - start_time
            self.logger.info(f"Model loaded in {load_time:.2f} seconds")
        except Exception as e:
            self.logger.error(f"Failed to load model: {str(e)}")
            raise

    def _get_prompt_template(self) -> PromptTemplate:
        """Get the current prompt template"""
        template = self.prompt_library.get_template(self.prompt_template_name)
        if not template:
            # Fall back to default if template not found
            template = self.prompt_library.get_template("mistral")
            if not template:
                # Create a minimal default template if none exists
                template = PromptTemplate(
                    name="default",
                    format_model=ModelFormat.UNCATEGORIZED,
                    default_system_prompt="You are a helpful assistant.",
                    stop_tokens=["</s>"]
                )
        return template

    def _get_stop_tokens(self) -> list[str]:
        """Get stop tokens for the current template"""
        template = self._get_prompt_template()
        return template.stop_tokens

    def _sanitize_response(self, response: str) -> str:
        """Clean up the model response based on model format"""
        template = self._get_prompt_template()
        return template.extract_response(response)

    async def generate(
            self,
            prompt: str,
            system_prompt: Optional[str] = None,
            chat_history: Optional[List[Dict[str, str]]] = None,
            max_tokens: int = 512,
            temperature: float = 0.7,
            top_p: float = 0.95,
            stop: Optional[List[str]] = None,
            stream: bool = False,
            use_cache: bool = True,
    ) -> Tuple[str, Dict[str, Any]]:
        """ Generate a response from the model """
        self.logger.info("Generating response...")

        # Format the prompt using the template
        template = self._get_prompt_template()
        full_prompt = template.format_prompt(
            user_prompt=prompt,
            system_prompt=system_prompt,
            chat_history=chat_history
        )

        # Prepare generation parameters
        params = {
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stop": stop if stop is not None else self._get_stop_tokens(),
            "stream": stream
        }

        # Check cache if enabled
        if use_cache:
            cached_result = self.cache.get(full_prompt, params)
            if cached_result:
                self.logger.info("Using cached response")
                return cached_result

        self.logger.debug(f"Full prompt: {full_prompt}")
        self.logger.debug(f"Stop tokens: {params['stop']}")

        # Run in a separate thread to avoid blocking the event loop
        start_time = time.time()

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.model.create_completion(
                full_prompt,
                max_tokens=params["max_tokens"],
                temperature=params["temperature"],
                top_p=params["top_p"],
                stop=params["stop"],
                stream=params["stream"],
            )
        )
        self.logger.debug(f"Raw response: {response}")

        generation_time = time.time() - start_time
        tokens_used = response.get("usage", {}).get("total_tokens", 0)

        result = response.get("choices", [{}])[0].get("text", "")

        result = self._sanitize_response(result)

        metrics = {
            "tokens_used": tokens_used,
            "generation_time_ms": int(generation_time * 1000),
            "tokens_per_second": tokens_used / generation_time if generation_time > 0 else 0,
            "model_name": os.path.basename(self.model_path),
            "timestamp": time.time()
        }

        self.logger.info(
            f"Generated {tokens_used} tokens in {generation_time:.2f}s "
            f"({metrics['tokens_per_second']:.2f} tokens/s)"
        )

        # Cache the result if caching is enabled
        if use_cache:
            self.cache.put(full_prompt, params, result, metrics)

        return result, metrics

class LLMRunner:
    """ Main LLM runner component that interfaces with the event bus """

    from app.core.model_service import ModelService
    def __init__(
        self,
        event_bus: EventBus,
        model_service: ModelService,
        default_model_id: str,
        prompt_library: Optional[PromptLibrary] = None,
        cache_dir: Optional[str] = None,
        cache_enabled: bool = True
    ):
        """
        Initialize the LLM runner component

        Args:
            event_bus: Event bus for communication
            model_service: Service for managing models
            default_model_id: ID of the default model
            prompt_library: Library of prompt templates
            cache_dir: Directory for response caching
            cache_enabled: Whether to enable response caching
        """
        self.logger = get_logger("LLMRunner")
        self.event_bus = event_bus
        self.model_service = model_service
        self.prompt_library = prompt_library or PromptLibrary()
        self.cache_dir = cache_dir
        self.cache_enabled = cache_enabled

        # Create a session map to track ongoing conversations
        self.sessions: Dict[str, List[Dict[str, str]]] = {}

        self.cache = None
        if cache_enabled:
            self.cache = ResponseCache(
                cache_dir=cache_dir,
                enabled=cache_enabled
            )

    async def initialize(self):
        """ Initialize the LLM model """
        self.logger.info("Intitializing LLM runner...")

        await self.model_service.initialize()

        self.logger.info("LLM runner initialized")

    async def run(self):
        """ Main run loop for the LLM component """
        await self.initialize()

        self.logger.info("Starting LLM runner loop")

        # Create tasks for different event types
        llm_request_task = asyncio.create_task(self._handle_llm_requests())
        session_clear_task = asyncio.create_task(self._handle_session_clears())

        # Wait for all tasks to complete (they shouldn't unless there's an error)
        await asyncio.gather(
            llm_request_task,
            session_clear_task
        )

    async def _handle_llm_requests(self):
        """ Handle LLM request events """
        async for event in self.event_bus.subscribe(EventType.LLM_REQUEST):
                if isinstance(event, LLMRequestEvent):
                    asyncio.create_task(self._process_llm_request(event)) # procss in background

    async def _handle_session_clears(self):
        """ Handle session clear events """
        async for event in self.event_bus.subscribe(EventType.SESSION_CLEAR):
                if isinstance(event, SessionClearEvent):
                    asyncio.create_task(self._clear_session(event.session_id))

    async def _clear_session(self, session_id: str):
        """ Clear sessions history """
        if session_id in self.sessions:
            self.logger.info(f"Clearing session {session_id}")
            del self.sessions[session_id]

    async def _process_llm_request(self, event: LLMRequestEvent):
        """ Process an LLM request event """
        self.logger.info(f"Processing LLM request: session_id={event.session_id}")

        try:
            # get parameters
            params = event.parameters or {}

            model_id = params.get("model_id", self.default_model_id)

            # get or create session
            session_id = event.session_id
            if session_id not in self.sessions:
                self.sessions[session_id] = []

            # add message to history if needed
            if event.chat_history is None:
                self.sessions[session_id].append({
                    "role": "user",
                    "content": event.prompt
                })

            # get chat history if needed
            chat_history = None
            if params.get("maintain_history", True):
                chat_history = event.chat_history or self.sessions[session_id]

            # get model
            try:
                model = await self.model_service.get_model(model_id)
            except Exception as e:
                self.logger.error(f"Failed to get model {model_id}: {str(e)}")

            template_id = params.get("template_id")
            if template_id:
                template = self.prompt_library.get_template(template_id)
                if not template:
                    self.logger.warning(f"Template {template_id} not found, using default")

            # generate response
            response, metrics = await model.generate(
                prompt=event.prompt,
                system_prompt=event.system_prompt,
                chat_history=chat_history,
                max_tokens=params.get("max_tokens", 512),
                temperature=params.get("temperature", 0.7),
                top_p=params.get("top_p", 0.95),
                stop=params.get("stop", None),
                use_cache=params.get("use_cache", self.cache_enabled),
            )

            if event.chat_history is None:
                self.sessions[session_id].append({
                    "role": "assistant",
                    "content": response
                })

            # limit history length
            max_history = params.get("max_history", 10)
            if len(self.sessions[session_id]) > max_history * 2:
                # keep first message (usually system) and trim older messages
                initial_messages = self.sessions[session_id][:1] if self.sessions[session_id] else []
                self.sessions[session_id] = initial_messages + self.sessions[session_id][-(max_history * 2):]

            model_info = self.model_service.model_manager.get_model(model_id)
            model_name = model_info.get("name", model_id) if model_info else model_id

            # create response event
            response_event = LLMResponseEvent(
                session_id=session_id,
                response=response,
                tokens_used=metrics["tokens_used"],
                generation_time_ms=metrics["generation_time_ms"],
                model_name=model_name,
                cache=metrics.get("cached", False)
            )

            await self.event_bus.publish(response_event)

        except Exception as e:
            self.logger.error(f"Error processing LLM request: {str(e)}", exc_info=True)

            error_response = LLMResponseEvent(
                session_id=event.session_id,
                response=f"Error: {str(e)}",
                tokens_used=0,
                generation_time_ms=0,
                model_name="error"
            )
            await self.event_bus.publish(error_response)

async def llm_runner_component(
    event_bus,
    model_service,
    default_model_id,
    cache_enabled=True,
    cache_dir=None
):
    """
    Main LLM runner component that interfaces with the event bus

    Args:
        event_bus: Event bus for communication
        model_service: Service for model management
        default_model_id: ID of the default model
        cache_enabled: Whether to enable response caching
        cache_dir: Directory for response caching
    """
    logger = get_logger("LLMRunner")
    logger.info("Starting LLM runner component")

    # Create LLM runner
    runner = LLMRunner(
        event_bus=event_bus,
        model_service=model_service,
        default_model_id=default_model_id,
        cache_enabled=cache_enabled,
        cache_dir=cache_dir
    )

    # Run the runner
    await runner.run()
