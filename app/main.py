"""
Module Name: app/main.py
Purpose   : Entry point for the Solo application.
Params    : None
History   :
    Date            Notes
    2025-06-08      Init
    2025-06-15      Updated to use enhanced model management

"""

import asyncio
import signal
import sys
from typing import Dict, List, Callable, Coroutine, Any
import os
from pathlib import Path
import uvicorn

from app.utils.logger import get_logger
from app.core.llm_service import llm_runner_component
from app.core.llm_tester import llm_tester_component
from app.core.model_manager import ModelManager
from app.core.prompt_templates import PromptLibrary
from app.core.db_service import DatabaseService
from app.utils.events import EventBus, EventType
from app.config import AppConfig

class SoloApp:
    """ Main application for Solo """

    def __init__(self, config_path: str = None):
        """ Initialize application """
        self.config = AppConfig(config_path)

        # Explicitly set log file for all loggers
        default_log_file = os.path.join("logs", "solo.log")
        self.config.log_file = default_log_file

        # Setup logger
        self.logger = get_logger(
            name="main",
            log_level=self.config.log_level,
            json_format=self.config.json_logs
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

        # Initialize database service (but dont connect yet)
        database_url = os.environ.get("DATABASE_URL")
        self.db_service = DatabaseService(connection_string=database_url)

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

        try:
            coro = self.components[name]()
            task = asyncio.create_task(coro)
            task.set_name(name)
            self.tasks.append(task)
            self.logger.info(f"Component started: {name}")
        except Exception as e:
            self.logger.error(f"Failed to start component {name}: {str(e)}")
            # We'll still try to start it again in the monitor_tasks method

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
        try:
            # Import FastAPI app factory correctly
            # The 'app' module is relative to the current file's location
            import sys
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            parent_dir = os.path.dirname(current_dir)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)

            from api.factory import create_app
            import uvicorn
            import asyncio

            logger = get_logger("APIServer")
            logger.info(f"Starting API server on port {config.api_port}")

            # Create the FastAPI app using the factory
            app = create_app(
                db_service=db_service,
                existing_model_service=self.model_service,
                existing_event_bus=event_bus,
                existing_model_manager=self.model_manager
            )

            # Configure uvicorn server
            uvicorn_config = uvicorn.Config(
                app=app,
                host="0.0.0.0",
                port=config.api_port,
                log_level="info"
            )
            server = uvicorn.Server(uvicorn_config)

            # This should run indefinitely until server is shut down
            await server.serve() # girlboss

            # If server.serve() returns, we'll add a wait to prevent task completion
            logger.info("API server returned unexpectedly, keeping task alive")
            stop_event = asyncio.Event()
            await stop_event.wait()
        except Exception as e:
            logger = get_logger("APIServer")
            logger.error(f"Failed to start API server: {str(e)}")
            raise

    async def run_db_service(self):
        """ Initialize and run the database service"""
        self.logger.info("Initializing database service...")

        connection_successful = await self.db_service.initialize()
        if connection_successful:
            self.logger.info("Database connection successful")
        else:
            self.logger.warning("Database connection failed, some features may be unavailable")

        # Keep this component running indefinitely
        try:
            # Use an event to wait forever unless cancelled
            stop_event = asyncio.Event()
            await stop_event.wait()
        except asyncio.CancelledError:
            self.logger.info("Database service cancelled")
            raise

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
            # Try to use any available model
            available_models = app.model_manager.list_available_models()
            if available_models:
                model_path = available_models[0].path
                app.logger.warning(f"No default model specified. Using first available model: {available_models[0].name}")
            else:
                app.logger.error("No model specified and no models found. Cannot continue.")
                return

    # Verify the model file exists
    if model_path and not os.path.exists(model_path):
        app.logger.warning(f"Specified model file does not exist: {model_path}")
        # Try to find any available model
        available_models = [m for m in app.model_manager.list_available_models() if os.path.exists(m.path)]
        if available_models:
            model_path = available_models[0].path
            app.logger.warning(f"Using alternative model: {available_models[0].name}")
        else:
            app.logger.error("No valid model files found. Cannot continue.")
            return

    # --- register components ---
    app.register_component(
        "db_service",
        app.run_db_service
    )

    # Create and register the model service
    from app.core.llm_service import ModelService

    model_service = ModelService(
        event_bus=app.event_bus,
        model_manager=app.model_manager,
        default_model_id=os.path.basename(model_path),  # Use the basename as the ID
        max_models=app.config.llm.max_loaded_models if hasattr(app.config.llm, 'max_loaded_models') else 2
    )

    app.model_service = model_service

    app.register_component(
        "model_service",
        model_service.initialize
    )

    app.register_component(
        "llm_runner",
        llm_runner_component,
        event_bus=app.event_bus,
        model_service=app.model_service,
        default_model_id=os.path.basename(model_path),
        cache_enabled=app.config.llm.cache_enabled,
        cache_dir=app.config.llm.cache_dir if hasattr(app.config.llm, 'cache_dir') else None
    )

    app.register_component(
        "api_server",
        app.run_api_server,
        event_bus=app.event_bus,
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
