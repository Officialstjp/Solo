"""
Module Name: app/core/llm_runner.py
Purpose   : Wrapper for llama.cpp inference with cuBLAS GPU acceleration
Params    : None
History   :
    Date            Notes
    2025-06-08      Init

"""

import os
from typing import Dict, Any, Optional, List, Union, Tuple
import asyncio
import time
from pathlib import Path

from llama_cpp import Llama
from utils.logger import setup_logger
from utils.events import EventBus, EventType, LLMRequestEvent, LLMResponseEvent

class LlamaModel:
    """ Wrapper for llama.cpp model inference """

    def __init__(
            self,
            model_path: str,
            n_ctx: int = 4096, # context
            n_batch: int = 512, # tokens per micro-batch
            n_threads: int = 12, # CPU threads for offloaded layers
            n_threads_batch=12,  # CPU threads for batching phase
            n_gpu_layers: int = 35, # -1 means use all layers on gpu
            verbose: bool = False,
    ):
        """ Initialize the LLM model """
        self.logger = setup_logger()
        self.logger.info(f"Initializing LlamaModel with model: {model_path}")

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_batch = n_batch
        self.n_threads = n_threads
        self.n_threads_batch = n_threads_batch
        self.n_gpu_layers = n_gpu_layers

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

    async def generate(
            self,
            prompt: str,
            system_prompt: Optional[str] = None,
            max_tokens: int = 512,
            temperature: float = 0.7,
            top_p: float = 0.95,
            stop: Optional[List[str]] = None,
            stream: bool = False,
    ) -> Tuple[str, Dict[str, Any]]:
        """ Generate a response from the model """
        self.logger.info("Generating response...")

        # Prepare the full prompt with system prompt if provided
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"<|system|>\n{system_prompt}\n<|user|>\n{prompt}<|assistant|>" #tinyllama

        # run in a sepearate thread to avoid blocking the event loop
        start_time = time.time()

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.model.create_completion(
                full_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop=stop,
                stream=stream,
            )
        )

        generation_time = time.time() - start_time
        tokens_used = response.get("usage", {}).get("total_tokens", 0)

        result = response.get("choices", [{}])[0].get("text", "")

        self.logger.info(
            f"Generated {tokens_used} tokens in {generation_time:.2f}s"
            f"({tokens_used/generation_time:.2f} tokens/s)"
        )

        metrics = {
            "tokens_used": tokens_used,
            "generation_time_ms": int(generation_time * 1000),
            "tokens_per_second": tokens_used / generation_time if generation_time > 0 else 0
        }

        return result, metrics

class LLMRunner:
    """ Main LLM runner component that interfaces with the event bus """

    def __init__(self, event_bus: EventBus, model_path: str):
        """ Initialize the LLM runner component """
        self.logger = setup_logger()
        self.event_bus = event_bus
        self.model_path = model_path
        self.model = None

    async def initialize(self):
        """ Initialize the LLM model """
        self.logger.info("Intitializing LLM runner...")
        self.model = LlamaModel(model_path=self.model_path)
        self.logger.info("LLM runner initialized")

    async def run(self):
        """ Main run loop for the LLM component """
        await self.initialize()

        self.logger.info("Starting LLM runner loop")

        async for event in self.event_bus.subscribe(EventType.LLM_REQUEST):
            if isinstance(event, LLMRequestEvent):
                self.logger.info(f"Received LLM request: session_id={event.session_id}")

                try:
                    # generate respone
                    response, metrics = await self.model.generate(
                        prompt=event.prompt,
                        system_prompt=event.system_prompt,
                        max_tokens=event.parameters.get("max_tokens", 512),
                        temperature=event.parameters.get("temperature", 0.7),
                        top_p=event.parameters.get("top_p", 0.95),
                        stop=event.parameters.get("stop", None),
                    )

                    # Publish response event
                    response_event = LLMResponseEvent(
                        session_id=event.session_id,
                        response=response,
                        tokens_used=metrics["tokens_used"],
                        generation_time_ms=metrics["generation_time_ms"],
                        model_name=os.path.basename(self.model_path)
                    )

                    await self.event_bus.publish(response_event)

                except Exception as e:
                    self.logger.error(f"Error processing LLM request: {str(e)}")

            await asyncio.sleep(0.01)

async def llm_runner_component(event_bus: EventBus, model_path: str):
    """ Create and return the LLM runner component """
    runner = LLMRunner(event_bus=event_bus, model_path=model_path)
    await runner.run()
