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
from utils.logger import get_logger
from utils.events import EventBus, EventType, LLMRequestEvent, LLMResponseEvent
from core.model_manager import ModelManager, ModelInfo, ModelFormat
from core.prompt_templates import PromptLibrary, PromptTemplate
from core.model_cache import ResponseCache

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

    def __init__(
        self,
        event_bus: EventBus,
        model_path: str,
        model_manager: Optional[ModelManager] = None,
        prompt_library: Optional[PromptLibrary] = None,
        prompt_template: Optional[str] = None,
        cache_dir: Optional[str] = None,
        cache_enabled: bool = True
    ):
        """ Initialize the LLM runner component """
        self.logger = get_logger("main")
        self.event_bus = event_bus
        self.model_path = model_path
        self.model = None
        self.model_manager = model_manager or ModelManager()
        self.prompt_library = prompt_library or PromptLibrary()
        self.prompt_template = prompt_template
        self.cache_dir = cache_dir
        self.cache_enabled = cache_enabled

        # Create a session map to track ongoing conversations
        self.sessions: Dict[str, List[Dict[str, str]]] = {}

    async def initialize(self):
        """ Initialize the LLM model """
        self.logger.info("Intitializing LLM runner...")
        self.model = LlamaModel(
            model_path=self.model_path,
            model_manager=self.model_manager,
            prompt_library=self.prompt_library,
            prompt_template=self.prompt_template,
            cache_dir=self.cache_dir,
            cache_enabled=self.cache_enabled
        )
        self.logger.info("LLM runner initialized")

    async def run(self):
        """ Main run loop for the LLM component """
        await self.initialize()

        self.logger.info("Starting LLM runner loop")

        async for event in self.event_bus.subscribe(EventType.LLM_REQUEST):
            if isinstance(event, LLMRequestEvent):
                self.logger.info(f"Received LLM request: session_id={event.session_id}")

                try:
                    # Get or create session history
                    session_id = event.session_id or str(uuid.uuid4())
                    if session_id not in self.sessions:
                        self.sessions[session_id] = []

                    # Add user message to history
                    self.sessions[session_id].append({
                        "role": "user",
                        "content": event.prompt
                    })

                    # Get chat history if maintain_history is requested
                    chat_history = None
                    if event.parameters.get("maintain_history", True):
                        chat_history = self.sessions[session_id]

                    # Generate response
                    response, metrics = await self.model.generate(
                        prompt=event.prompt,
                        system_prompt=event.system_prompt,
                        chat_history=chat_history,
                        max_tokens=event.parameters.get("max_tokens", 512),
                        temperature=event.parameters.get("temperature", 0.7),
                        top_p=event.parameters.get("top_p", 0.95),
                        stop=event.parameters.get("stop", None),
                        use_cache=event.parameters.get("use_cache", True),
                    )

                    # Add assistant response to history
                    self.sessions[session_id].append({
                        "role": "assistant",
                        "content": response
                    })

                    # Limit history length
                    max_history = event.parameters.get("max_history", 10)
                    if len(self.sessions[session_id]) > max_history * 2:  # *2 because each exchange is 2 messages
                        # Keep first message (usually system) and trim older messages
                        initial_messages = self.sessions[session_id][:1] if self.sessions[session_id] else []
                        self.sessions[session_id] = initial_messages + self.sessions[session_id][-(max_history * 2):]

                    # Include model info in response
                    model_info = self.model_manager.get_model_info(self.model_path)
                    model_name = model_info.name if model_info else os.path.basename(self.model_path)

                    # Publish response event
                    response_event = LLMResponseEvent(
                        session_id=session_id,
                        response=response,
                        tokens_used=metrics["tokens_used"],
                        generation_time_ms=metrics["generation_time_ms"],
                        model_name=model_name
                    )

                    await self.event_bus.publish(response_event)

                except Exception as e:
                    self.logger.error(f"Error processing LLM request: {str(e)}")
                    # Send error response
                    error_response = LLMResponseEvent(
                        session_id=event.session_id,
                        response=f"Error: {str(e)}",
                        tokens_used=0,
                        generation_time_ms=0,
                        model_name="error"
                    )
                    await self.event_bus.publish(error_response)

            await asyncio.sleep(0.01)

    def clear_session(self, session_id: str):
        """Clear a conversation session

        Args:
            session_id: Session ID to clear
        """
        if session_id in self.sessions:
            del self.sessions[session_id]

async def llm_runner_component(
    event_bus: EventBus,
    model_path: str,
    prompt_template: Optional[str] = None,
    cache_enabled: bool = True
):
    """ Create and return the LLM runner component """
    # Create shared managers
    model_manager = ModelManager()
    prompt_library = PromptLibrary()

    # Create cache directory if caching is enabled
    cache_dir = None
    if cache_enabled:
        base_dir = Path(__file__).resolve().parent.parent.parent
        cache_dir = os.path.join(base_dir, "cache", "llm_responses")
        os.makedirs(cache_dir, exist_ok=True)

    runner = LLMRunner(
        event_bus=event_bus,
        model_path=model_path,
        model_manager=model_manager,
        prompt_library=prompt_library,
        prompt_template=prompt_template,
        cache_dir=cache_dir,
        cache_enabled=cache_enabled
    )
    await runner.run()
