"""
Module Name: app/main.py
Purpose   : Entry point for the Solo application.
Params    : None
History   :
    Date            Notes
    2025-06-08      Init
    2025-06-15      Updated to use enhanced model management

"""
# time: about 100h, 06.07.25 10:45, curr daily: 2:30
# continue with router integration and main server setup (step 5), then fill in placeholders and flesh out

import asyncio
import signal
import sys
from typing import Dict, List, Callable, Coroutine, Any
import os
from pathlib import Path

from core.llm_runner import llm_runner_component
from core.llm_tester import llm_tester_component
from core.model_manager import ModelManager
from core.prompt_templates import PromptLibrary
from core.db_service import DatabaseService
from utils.logger import get_logger
from utils.events import EventBus, EventType
import uvicorn
from config import AppConfig


class SoloApp:
    """ Main application for Solo """

    def __init__(self, config_path: str = None):
        """ Initialize application """
        self.config = AppConfig(config_path)

        # Setup logger
        self.logger = get_logger(name = "main",
            log_level=self.config.log_level,
            json_format=self.config.json_logs,
            log_file=self.config.log_file
        )

        # Initialize model manager
        self.model_manager = ModelManager(
            models_dir=self.config.get_models_dir(),
            default_model=self.config.llm.model_path
        )

        # Initialize prompt library
        self.prompt_library = PromptLibrary()

        # Initialize event bus
        self.event_bus = EventBus()

        # Store running tasks
        self.tasks: List[asyncio.Task] = []

        # Register components
        self.components: Dict[str, Callable[[], Coroutine[Any, Any, None]]] = {}

        # Signal handlers for graceful shutdown
        self._setup_signal_handlers()

        self.logger.info("Initialization complete.")

        # Log available models
        models = self.model_manager.list_available_models()
        if models:
            self.logger.info(f"Found {len(models)} models:")
            for model in models:
                self.logger.info(f"  - {model.name} ({model.parameter_size}, {model.quantization})")
        else:
            self.logger.warning("No models found. Please check your models directory.")

    def _setup_signal_handlers(self):
        """ Setup signal handlers for graceful shutdown """
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """ Handle shutdown signals """
        self.logger.info(f"Recieved signal {signum}, initating shutdown")
        for task in asyncio.all_tasks():
            if task is not asyncio.current_task():
                task.cancel()

    def register_component(self, name: str, coro_func: Callable[..., Coroutine[Any, Any, None]], *args, **kwargs):
        """ Register a component with the application """
        self.components[name] = lambda: coro_func(*args, **kwargs)
        self.logger.info(f"Component registered: {name}")

    async def start_component(self, name: str):
        """ Start a registered component """
        if name not in self.components:
            self.logger.error(f"Component not found: {name}")
            return

        coro = self.components[name]()
        task = asyncio.create_task(coro)
        task.set_name(name)
        self.tasks.append(task)
        self.logger.info(f"Component started: {name}")

    async def monitor_tasks(self): # Currently, planned are only tasks that run indefinetly until shutdown, so we treat all results as unexpected
        """ Monitor running tasks and restart if necessary """
        while True:
            for task in self.tasks[:]:
                if task.done():
                    name = task.get_name()

                    if name == "task_monitor":
                        continue

                    try:
                        result = task.result()
                        self.logger.warning(f"Task {name} completed unexpectedly with result: {result}")
                        # Restart the component
                        self.tasks.remove(task)
                        await self.start_component(name)
                        self.logger.info(f"Component {name} restarted after completion")
                    except Exception as e:
                        self.logger.error(f"Task {name} failed with exception: {str(e)}")
                        # Restart the component
                        self.tasks.remove(task)
                        await self.start_component(name)
                        self.logger.info(f"Component {name} restarted")

            await asyncio.sleep(1)

    async def startup(self):
        """ Start all registered components """
        self.logger.info("Starting Solo...")

        # start all components
        for name in self.components:
            await self.start_component(name)

        # start task monitor
        monitor_task = asyncio.create_task(self.monitor_tasks())
        monitor_task.set_name("task_monitor")
        self.tasks.append(monitor_task)

        self.logger.info("Solo startup complete")

    async def shutdown(self):
        """ Gracefully shutdown the application """
        self.logger.info("Shutting down Solo....")

        if hasattr(self, 'db_service') and self.db_service:
            await self.db_service.close()

        for task in self.tasks:
            task.cancel()

        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

        self.logger.info("Shutdown complete")

        return True

    async def run_api_server(self, event_bus, config, db_service):
        """
        Run the API server using the application factory

        Args:
            event_bus: The event bus instance
            config: The application configuration
        """
        from app.api.factory import create_app
        import uvicorn
        import asyncio

        logger = get_logger("APIServer")
        logger.info(f"Starting API server on port {config.api_port}")

        # Create the FastAPI app using the factory
        app = create_app(db_service=db_service)

        # Configure uvicorn server
        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=config.api_port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve() # girlboss

    async def run_db_service(self):
        """ Initialize and run the database service"""
        self.logger.info("Initializing database service...")
        self.db_service = DatabaseService()

        connection_successful = await self.db_service.initialize()
        if connection_successful:
            self.logger.info("Database connection successful")
        else:
            self.logger.warning("Database connection failed, some features may be unavailable")

async def main():
    """ Main entry point for the application """
    app = SoloApp()

    # Default to first available model if none specified
    model_path = app.config.llm.model_path
    if not model_path:
        default_model = app.model_manager.get_default_model()
        if default_model:
            model_path = default_model.path
            app.logger.info(f"Using default model: {default_model.name}")
        else:
            app.logger.error("No model specified and no models found. Cannot continue.")
            return

    # --- register components ---
    app.register_component(
        "db_service",
        app.run_db_service
    )

    app.register_component(
        "llm_runner",
        llm_runner_component,
        event_bus=app.event_bus,
        model_path=model_path,  # Use the actual model path
        prompt_template=app.config.llm.prompt_template if hasattr(app.config.llm, 'prompt_template') else None,
        cache_enabled=app.config.llm.cache_enabled
    )

    # Create and register the model service
    from app.core.model_service import ModelService

    model_service = ModelService(
        event_bus=app.event_bus,
        model_manager=app.model_manager,
        default_model_id=os.path.basename(model_path),  # Use the basename as the ID
        max_models=app.config.llm.max_loaded_models if hasattr(app.config.llm, 'max_loaded_models') else 2
    )

    app.register_component(
        "model_service",
        model_service.initialize
    )

    app.register_component(
        "api_server",
        app.run_api_server,
        event_bus=app.event_bus,
        model_manager=app.model_manager,
        config=app.config,
        db_service=app.db_service
    )

    await app.startup()

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
