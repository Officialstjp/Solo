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
from utils.logger import get_logger
from typing import Optional, Dict, List, Any
import os
import json
from pathlib import Path
from dotenv import load_dotenv


logger = get_logger("main")

_config_instance = None

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

    @classmethod
    def from_json(cls, json_path: str) -> 'AppConfig':
        """ Create AppConfig from JSON file """
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            return cls(**data)
        except Exception as e:
            logger = get_logger("config")
            logger.error(f"Failed to load config from JSON: {str(e)}")
            return cls()

    def get_models_dir(self) -> str:
        """Get the absolute path to the models directory"""
        if os.path.isabs(self.models_dir):
            return self.models_dir

        # Resolve relative to project root
        base_dir = Path(__file__).resolve().parent.parent
        return str(base_dir / self.models_dir)

def get_config(config_path: str = None, force_reload: bool = False):
    """
    Get application configuration

    Args:
        config_path: Optional path to configuration file
        force_reload: Force relaod configuration even if cached
    Returns:
        AppConfig instance with loaded configuration
    """
    global _config_instance

    if _config_instance is not None and not force_reload:
        return _config_instance

    logger = get_logger("main")
    logger.debug(f"Loading configuration, poath: '{config_path}', force: {force_reload}")

    if not config_path:
        config_path = _discover_config_file()
        if config_path:
            logger.info(f"Discovered config file: {config_path}")

    try:
        _config_instance = AppConfig(config_path=config_path)
        logger.info("Configuration loaded successfully")

        logger.debug(f"Loaded config: model_path={_config_instance.llm.model_path}, "
                     f"models_dir={_config_instance.models_dir}, "
                     f"log_level={_config_instance.log_level}")

        return _config_instance
    except Exception as e:
        logger.error(f"Failed to load configuration: {str(e)}")
        logger.warning("Using default configuration")
        _config_instance = AppConfig()
        return _config_instance

def _discover_config_file() -> Optional[str]:
    """
    Discover configuration file in standard locations.
    Locations checked (in order):
    1. SOLO_CONFIG_PATH environment variable ---> currently, this variable is set nowhere
    2. .env in current directory
    3. config.json in current directory
    4. .env in user's home directory
    5. config/solo.json in user's home directory

    Returns:
        Paht to discovered configuration file or None
    """
    # check env var
    env_config_path = os.environ.get("SOLO_CONFIG_PATH")
    if env_config_path and os.path.exists(env_config_path):
        logger.debug(f"Discovered configuration '{path}' in environment variable.")
        return env_config_path

    #check current working directory
    cwd = os.getcwd()
    for filename in [".env", "config.json", "solo.json"]:
        path = os.path.join(cwd, filename)
        logger.debug(f"Discovered configuration '{path}' in current working directory.")
        if os.path.exists(path):
            return path

    # check project root
    project_root = Path(__file__).resolve().parent.parent
    for filename in [".env", "config.json", "solo.json"]:
        path = project_root / filename
        if path.exists():
            logger.debug(f"Discovered configuration '{path}' in project root.")
            return str(path)

    # check home dir
    home_dir = Path.home()
    for filename in [".env", "config.json", "solo.json"]:
        path = home_dir / filename
        if path.exists():
            logger.debug(f"Discovered configuration '{path}' in home directory.")
            return str(path)

    # check .config / solo directory in users home
    config_dir = home_dir / ".config" / "solo"
    if config_dir.exists():
        for filename in [".env", "config.json", "solo.json"]:
            path = config_dir / filename
            if path.exists():
                logger.debug(f"Discovered configuration '{path}' in home directory's .config/solo.")
                return str(path)

    return None

def update_config(config_updates: Dict[str, Any] = None, save_path: str = None,
                  **kwargs) -> AppConfig:
    """
    Update application configuration with new values

    Args:
        config_updates: Dictionary of configuration update (can include nested paths like llm.model_path)
        save_path: Optional path to save updated configuration (JSON format)
        **kwargs: keyword arguments for config fiels

    Returns:
        Updated AppConfig instance

    Examples:
        # update with dictionay
        update_config({'llm': {'model_path': /path/to/model.gguf}})

        # update with kwargs
        update_config(log_level="DEBUG", models_dir="/path/to/models")

        # update nested fiels
        update_config({'llm.model_path': '/path/to/model.gguf'})

        # save to file
        update_config({'log_level': 'INFO'}, save_path='config.json')
    """

    global _config_instance

    logger = get_logger("config")

    if _config_instance is None:
        _config_instance = get_config()

    current_config = _config_instance.dict()

    # kwargs first
    if kwargs:
        _update_config_dict(current_config, kwargs)

    if config_updates:
        for key, value in config_updates.items():
            # handle nested paths
            if '.' in key:
                parts = key.split('.')
                target = current_config
                for part in parts[:-1]:
                    if part not in target:
                        target[part] = {}
                    target = target[part]
                target[parts[-1]] = value
            else:
                # direct field update
                current_config[key] = value

    updated_config = AppConfig(**current_config)
    _config_instance = update_config

    logger.info("Configuration updated")

    if save_path:
        save_config_to_file(updated_config, save_path)
        logger.info(f"Configuraiton saved to {save_path}")

    return updated_config

def _update_config_dict(target: Dict[str, Any], updates: Dict[str, Any]) -> None:
    """
    Deep update a nested dictionary with another dictionary
    Args:
        target: Target dictionary to update
        updates: Dictionary with updates
    """
    for key, value in updates.items():
        if isinstance(value, dict) and key in target and isinstance(target[key], dict):
            # recursively update nested dictionaries
            _update_config_dict(target[key], value)
        else:
            # direct update for non-dict values
            target[key] = value

def save_config_to_file(config: AppConfig, file_path: str) -> bool:
    """
    Save configuartion to a file

    Args:
        config: AppConfig instance to save
        file_path: Path to save configuration to

    Returns:
        True if successful, False otherwise
    """
    try:
        # make parent directories if thewy don't exist
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

        # determine file format
        if file_path.endswith('.json'):
            with open(file_path, 'w') as f:
                json.dump(config.dict(exclude_unset=True), f, indent=2)
        elif file_path.endswith('.env'):
            with open(file_path, 'w') as f:
                for key, value in _flatten_config(config).items():
                    f.write(f"{key}={value}\n")
        else:
            file_path = f"{file_path}.json"
            with open(file_path, 'w') as f:
                json.dump(config.dict(exclude_unset=True), f, indent=2)

        return True
    except Exception as e:
        logger = get_logger("main")
        logger.error(f"Failed to save config: {str(e)}")
        return False

def _flatten_config(config: AppConfig, prefix: str = "SOLO_") -> Dict[str, str]:
    """
    Flatten configuration to environment variable format.

    Args:
        config: AppConfig instance
        prefix: Prefix for enviroment variables

    Returns:
        Dictionary of flattened configuration
    """
    result = {}
    config_dict = config.dict()

    def _flatten(d, parent_key=""):
        for key, value in d.items():
            if isinstance(value, dict):
                _flatten(value, f"{parent_key}{key}.")
            else:
                if value is not None:
                    env_key = f"{prefix}{parent_key.upper()}{key.upper()}"
                    result[env_key] = str(value)

    _flatten(config_dict)
    return result

def load_config_from_json(file_path: str) -> Dict[str, Any]:
    """
    Load configuration from JSON file.

    Args:
        file_path: Path to JSON configuration file

    Returns:
        Dictionary with configuration values
    """
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger = get_logger("main")
        logger.error(f"Error loading configuration from json: {str(e)}")
        return {}
