"""
Module Name: app/config.py
Purpose   : Application configuration settings.
Params    : None
History   :
    Date            Notes
    2025-06-08      Init
    2025-06-15      Enhanced with model configuration options

"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List, Any
import os
from pathlib import Path
from dotenv import load_dotenv

class LLMConfig(BaseModel):
    """ Configuration for LLM models """

    backend: str = Field(default="llama.cpp")  # or "ollama"
    model_path: Optional[str] = None
    prompt_template: Optional[str] = None
    n_ctx: int = Field(default=8192)
    n_batch: int = Field(default=512)
    n_threads: int = Field(default=12)
    n_threads_batch: int = Field(default=12)
    n_gpu_layers: int = Field(default=35)
    cache_enabled: bool = Field(default=True)
    model_params: Dict[str, Any] = Field(default_factory=dict)

    @validator('model_path')
    def validate_model_path(cls, v):
        if v and not os.path.exists(v):
            # Try to find in models directory
            base_dir = Path(__file__).resolve().parent.parent
            models_dir = base_dir / "models"
            potential_path = models_dir / v

            if os.path.exists(potential_path):
                return str(potential_path)

            # Also check with .gguf extension
            if not v.endswith('.gguf') and os.path.exists(f"{potential_path}.gguf"):
                return f"{str(potential_path)}.gguf"

        return v

class AppConfig(BaseModel):
    """ Configuration for Solo """

    # App name and version
    app_name: str = Field(default="Solo")
    app_version: str = Field(default="0.1.0")

    # Logging configuration
    log_level: str = Field(default="DEBUG") # DEBUG
    json_logs: bool = Field(default=True)
    log_file: Optional[str] = None

    # LLM configuration
    llm: LLMConfig = Field(default_factory=LLMConfig)
    default_system_prompt: str = Field(
        default="""You are an advanced research assistant, named Solo. Your task is to support, advise and teach the user in any task they come across.
        Always speak in a natural tone, act like an absolute professional in the task at hand and speak as such.
        Refrain from report-like breakdowns, in favor of natural conversational tone.
        You currently reside in a local experimental Python environment, to be expanded into a full ecosystem.
        """
    )

    # STT/TTS configuration
    stt_model: str = Field(default="faster-whisper-small")
    tts_voice: str = Field(default="en_us/vctk_low/p303")

    # API configuration
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8080)

    # Dashboard configuration
    dashboard_host: str = Field(default="0.0.0.0")
    dashboard_port: int = Field(default=8501)

    # Memory configuration
    memory_enabled: bool = Field(default=False)
    memory_db_path: Optional[str] = None

    # Models directory
    models_dir: str = Field(default="D:\data\models")

    def __init__(self, config_path: str = None, **data):
        """ Initialize configuration from environment variables or .env file """
        # load from .env if provided
        if config_path:
            load_dotenv(config_path)
        else:
            load_dotenv()

        # Override with env variables
        env_vars = {
            "log_level": os.getenv("SOLO_LOG_LEVEL"),
            "json_logs": os.getenv("SOLO_JSON_LOGS"),
            "log_file": os.getenv("SOLO_LOG_FILE"),
            "llm.backend": os.getenv("SOLO_LLM_BACKEND"),
            "llm.model_path": os.getenv("SOLO_MODEL_PATH"),
            "llm.prompt_template": os.getenv("SOLO_PROMPT_TEMPLATE"),
            "llm.n_ctx": os.getenv("SOLO_MODEL_CTX"),
            "llm.n_gpu_layers": os.getenv("SOLO_GPU_LAYERS"),
            "llm.cache_enabled": os.getenv("SOLO_CACHE_ENABLED"),
            "default_system_prompt": os.getenv("SOLO_SYSTEM_PROMPT"),
            "stt_model": os.getenv("SOLO_STT_MODEL"),
            "tts_voice": os.getenv("SOLO_TTS_VOICE"),
            "api_host": os.getenv("SOLO_API_HOST"),
            "api_port": os.getenv("SOLO_API_PORT"),
            "dashboard_host": os.getenv("SOLO_DASHBOARD_HOST"),
            "dashboard_port": os.getenv("SOLO_DASHBOARD_PORT"),
            "memory_enabled": os.getenv("SOLO_MEMORY_ENABLED"),
            "memory_db_path": os.getenv("SOLO_MEMORY_DB_PATH"),
            "models_dir": os.getenv("SOLO_MODELS_DIR"),
        }

        # filter out None values
        env_vars = {k: v for k, v in env_vars.items() if v is not None}

        # Process nested config (llm.*)
        llm_config = {}
        for key in list(env_vars.keys()):
            if key.startswith("llm."):
                _, param = key.split(".", 1)
                llm_config[param] = env_vars.pop(key)

        if llm_config:
            env_vars["llm"] = llm_config

        # Convert string booleans
        for key in ["json_logs", "llm.cache_enabled", "memory_enabled"]:
            parts = key.split(".")
            if len(parts) == 1 and key in env_vars and isinstance(env_vars[key], str):
                env_vars[key] = env_vars[key].lower() == "true"
            elif len(parts) == 2 and parts[0] in env_vars and parts[1] in env_vars[parts[0]]:
                if isinstance(env_vars[parts[0]][parts[1]], str):
                    env_vars[parts[0]][parts[1]] = env_vars[parts[0]][parts[1]].lower() == "true"

        # Convert numeric values
        for key in ["api_port", "dashboard_port", "llm.n_ctx", "llm.n_gpu_layers", "llm.n_batch", "llm.n_threads"]:
            parts = key.split(".")
            if len(parts) == 1 and key in env_vars and isinstance(env_vars[key], str):
                try:
                    env_vars[key] = int(env_vars[key])
                except ValueError:
                    pass
            elif len(parts) == 2 and parts[0] in env_vars and parts[1] in env_vars[parts[0]]:
                if isinstance(env_vars[parts[0]][parts[1]], str):
                    try:
                        env_vars[parts[0]][parts[1]] = int(env_vars[parts[0]][parts[1]])
                    except ValueError:
                        pass

        # Merge with provided data
        merged_data = {**data, **env_vars}

        super().__init__(**merged_data)

    @property
    def model_path(self) -> Optional[str]:
        """Get the model path (for backwards compatibility)"""
        return self.llm.model_path

    @property
    def llm_backend(self) -> str:
        """Get the LLM backend (for backwards compatibility)"""
        return self.llm.backend

    def get_models_dir(self) -> str:
        """Get the absolute path to the models directory"""
        if os.path.isabs(self.models_dir):
            return self.models_dir

        # Resolve relative to project root
        base_dir = Path(__file__).resolve().parent.parent
        return str(base_dir / self.models_dir)
