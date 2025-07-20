"""
Module: model_service
Purpose: Provide on-the fly model switching
"""

import asyncio
import time
import os
from typing import Dict, Any, Optional, List, Set
import uuid

from utils.logger import get_logger
from utils.events import EventBus, EventType, ModelLoadRequestEvent, ModelLoadedEvent, ModelUnloadedEvent
from core.model_manager import ModelManager
from core.llm_runner import LlamaModel

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
