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
from typing import Dict, Any, Optional, List, Union, Tuple, Set
import asyncio
import time
from pathlib import Path
import uuid
from enum import Enum
from dataclasses import dataclass

from llama_cpp import Llama
from app.utils.logger import get_logger
from app.utils.events import EventBus, EventType, LLMRequestEvent, LLMResponseEvent, SessionClearEvent, ModelLoadRequestEvent, ModelLoadedEvent, ModelUnloadedEvent
from app.core.model_manager import ModelManager, ModelInfo, ModelFormat
from app.core.prompt_templates import PromptLibrary, PromptTemplate
from app.core.model_cache import ResponseCache


class ModelFormat(str, Enum):
    """Known model formats with their prompt templates"""
    MISTRAL = "mistral"
    MISTRAL_INSTRUCT = "mistral-instruct"
    LLAMA2 = "llama2"
    LLAMA3 = "llama3"
    TINYLLAMA = "tinyllama"
    PHI = "phi"
    PHI2 = "phi2"
    PHI3 = "phi3"
    PHI4 = "phi4"
    MIXTRAL = "mixtral"
    UNCATEGORIZED = "uncategorized"

@dataclass
class ModelInfo:
    """Information about a specific model"""
    path: str
    name: str
    format: ModelFormat
    context_length: int
    quantization: str
    parameter_size: str
    supported_features: List[str]
    metadata: Dict[str, Any]

    @property
    def file_size_mb(self) -> float:
        """Get the file size in MB"""
        try:
            return os.path.getsize(self.path) / (1024 * 1024)
        except (FileNotFoundError, OSError):
            return 0.0

    @property
    def short_description(self) -> str:
        """Get a short description of the model"""
        return f"{self.name} ({self.parameter_size}, {self.quantization}, {self.file_size_mb:.1f}MB)"

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

class ModelService:
    """
    Service for managing multiple LLM models with dynamic loading / unloading
    """

    def __init__(
        self,
        event_bus: EventBus,
        model_manager: ModelManager,
        default_model_id: str,
        max_models: int = 2,
        model_timeout: float = 1800.0, # 30 minutes
        check_interval: float = 300.0
    ):
        """
        Initialize the model service
        Args:
            event_bus: App event bus instance
            model_manager: App model manager instance
            default_model_id: ID of the default model
            max_models: Maximzm number of models to keep loaded
            model_timeout: Time in seconds after which unused models are unloaded
            check_interval: Interval in seconds to check for unused models
        """
        self.logger = get_logger("ModelService")
        self.event_bus = event_bus
        self.model_manager = model_manager
        self.default_model_id = default_model_id
        self.max_models = max_models
        self.model_timeout = model_timeout
        self.check_interval = check_interval

        # state
        self.models: Dict[str, LlamaModel] = {} # model_id -> model
        self.model_last_used: Dict[str, float] = {} # model_id -> timestamp
        self.loading_models: Set[str] = set() # set of models currently being loaded

        self.maintenance_task = None

    async def initialize(self):
        """ Initialize the model service and load default model """
        self.logger.info("Initializing model service")

        # Start listening for model events
        listen_task = asyncio.create_task(self._listen_for_model_events())

        # Start maintenance task
        self.maintenance_task = asyncio.create_task(self._run_maintenance())

        # Load default model
        await self.get_model(self.default_model_id)

        self.logger.info("Model service initialized")

        # Keep this component running indefinitely
        try:
            # Use an event to wait forever unless cancelled
            stop_event = asyncio.Event()
            await stop_event.wait()
        except asyncio.CancelledError:
            self.logger.info("Model service initialization cancelled")
            raise
        finally:
            # Ensure cleanup if the task is cancelled
            if listen_task and not listen_task.done():
                listen_task.cancel()

    async def _run_maintenance(self):
        """ Peridocially check for and unload unused models """
        while True:
            await asyncio.sleep(self.check_interval)
            await self._check_unused_models()

    async def _check_unused_models(self):
        """ Check for and unload models that haven't been used recently """
        now = time.time()
        models_to_unload = []

        min_models_to_keep = 1

        for model_id, last_used in self.model_last_used.items():
            if now - last_used > self.model_timeout:
                models_to_unload.append((model_id, last_used))

        models_to_unload.sort(key=lambda x: x[1])

        if len(self.models) - len(models_to_unload) < min_models_to_keep:
            models_to_keep = min_models_to_keep - (len(self.models) - len(models_to_unload))
            models_to_unload = models_to_unload[:-models_to_keep] if models_to_keep > 0 else models_to_unload

        for model_id, _ in models_to_unload:
            self.logger.info(f"Unloading idle model: {model_id}")
            await self._unload_model(model_id, reason="idle")

    async def _handle_model_load_request(self, event: ModelLoadRequestEvent):
        """ Handle a model load request """
        model_id = event.model_id
        priority = event.priority

        try:
            self.logger.info(f"Recieved request to load model: {model_id} (priority: {priority})")
            model = await self.get_model(model_id, priority=priority)

            model_info = self.model_manager.get_model_info(model_id)
            await self.event_bus.publish(ModelLoadedEvent(
                model_id=model_id,
                success=True,
                model_info=model_info
            ))
        except Exception as e:
            self.logger.error(f"Failed to load model {model_id}: {str(e)}")

            await self.event_bus.publish(ModelLoadedEvent(
                model_id=model_id,
                success=False,
                error_message=str(e)
            ))

    async def get_model(self, model_id: str, priority: bool = False) -> LlamaModel:
        """
        Get a model by ID, loading it if necessary
        Args:
            model_id: The ID of the model to tet
            priority: Wether this is a priority request
        Returns:
            LlamaModel: the loaded model
        """
        # if already loaded, update timestamp and return
        if model_id in self.models:
            self.model_last_used[model_id] = time.time()
            return self.models[model_id]

        # if model is being loaded, wait for it
        if model_id in self.loading_models:
            self.logger.info(f"Waiting for model {model_id} to finish loading")
            while model_id in self.loading_models:
                await asyncio.sleep(0.1)

            if model_id in self.models:
                self.model_last_used[model_id] = time.time()
                return self.models[model_id]
            else:
                raise ValueError(f"Failed to load model {model_id}")


        # need to load the model
        self.loading_models.add(model_id)
        try:
            model_info = self.model_manager.get_model_info(model_id)
            if not model_info:
                # Try to find by basename if model_id is a filename
                available_models = self.model_manager.list_available_models()
                found_model = None
                for model in available_models:
                    if os.path.basename(model.path) == model_id or model.name == model_id:
                        found_model = model
                        break

                if found_model:
                    model_info = found_model
                    self.logger.info(f"Found model {model_id} by name match: {model_info.name}")
                elif len(available_models) > 0:
                    # Fall back to first available model
                    model_info = available_models[0]
                    self.logger.warning(f"Model {model_id} not found. Falling back to {model_info.name}")
                else:
                    self.logger.error(f"Model {model_id} not found and no fallback models available")
                    raise ValueError(f"Model {model_id} not found and no fallback models available")

            model_path = model_info.path
            if not model_path:
                raise ValueError(f"Model path not found for {model_id}")

            if not os.path.exists(model_path):
                self.logger.error(f"Model file not found at {model_path}")
                # If this is the default model, try to fall back to any available model
                if model_id == self.default_model_id:
                    available_models = [m for m in self.model_manager.list_available_models()
                                       if os.path.exists(m.path)]
                    if available_models:
                        model_info = available_models[0]
                        model_path = model_info.path
                        self.logger.warning(f"Falling back to available model: {model_info.name}")
                    else:
                        raise FileNotFoundError(f"Model file {model_path} not found and no fallback models available")
                else:
                    raise FileNotFoundError(f"Model file {model_path} not found")

            if len(self.models) >= self.max_models:
                await self._make_space_for_model(priority)

            self.logger.info(f"Loading model {model_id} from {model_path}")

            model = LlamaModel(
                model_path=model_path,
                model_manager=self.model_manager
            )

            self.models[model_id] = model
            self.model_last_used[model_id] = time.time()

            return model

        finally:
            self.loading_models.remove(model_id)

    async def _make_space_for_model(self, priority: bool = False):
        """
        Make space for a new model by unloading the least recently use one
        Args:
            priority: Wheter this is a priority request
        """
        sorted_models = sorted(self.model_last_used.items(), key=lambda x: x[1])

        # Don't unload the default model unless it's a priority request or it's the only one
        if not priority and len(sorted_models) > 1:
            sorted_models = [(mid, time) for mid, time in sorted_models if mid != self.default_model_id]

        if not sorted_models:
            self.logger.warning("No models to unload, proceeding without unloading")
            return

        model_id, _ = sorted_models[0]
        await self._unload_model(model_id, reason="lru")

    async def _listen_for_model_events(self):
        """Listen for model-related events"""
        async for event in self.event_bus.subscribe(EventType.MODEL_LOAD_REQUEST):
            if isinstance(event, ModelLoadRequestEvent):
                # Handle in background to not block event processing
                asyncio.create_task(self._handle_model_load_request(event))

    async def _unload_model(self, model_id: str, reason: str):
        """
        Unload a model

        Args:
            model_id: The ID of the model to unload
            reason: The reason for unloading the model ("manual", "lru", "idle", "error",...)
        """
        if model_id not in self.models:
            return

        self.logger.info(f"Unloading model {model_id} (reason: {reason})")

        # remove from dicts
        model = self.models.pop(model_id)
        self.model_last_used.pop(model_id)

        model = None

        await self.event_bus.publish(ModelUnloadedEvent(
            model_id=model_id,
            reason=reason
        ))

    async def shutdown(self):
        """ Shutdown the service and unload all models """
        self.logger.info("Shutting down model service")

        if self.maintenance_task:
            self.maintenance_task.cancel()
            try:
                await self.maintenance_task
            except asyncio.CancelledError:
                pass

        for model_id in list(self.models.keys()):
            await self._unload_model(model_id, reason="shutdown")

        self.logger.info("Model service shut down")

class LLMRunner:
    """ Main LLM runner component that interfaces with the event bus """

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
        self._tasks: List[asyncio.Task] = [] # keep track of background tasks

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
        self.logger.info("LLM runner initialized successfully")

    async def run(self):
        """ Main run loop for the LLM component """
        await self.initialize()

        # create and track background tasks
        request_handler_task = asyncio.create_task(self._handle_llm_requests())
        session_clear_task = asyncio.create_task(self._handle_session_clears())
        self._tasks.extend([request_handler_task, session_clear_task])

        # wait for tasks to complete (they should run indefinitely)
        await asyncio.gather(*self._tasks)

    async def shutdown(self):
        """ Shutdown the LLM runner component """
        self.logger.info("Shutting down LLM runner...")
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # Wait for all tasks to finish
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self.logger.info("LLM runner shutdown complete")

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
    try:
        # Run the runner
        await runner.run()
    finally:
        await runner.shutdown()
