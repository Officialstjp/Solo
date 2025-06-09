"""
Module Name: app/config.py
Purpose   : Application configuration settings.
Params    : None
History   :
    Date            Notes
    2025-06-08      Init

"""

from pydantic import BaseModel, Field
from typing import Optional
import os
from dotenv import load_dotenv

class AppConfig(BaseModel):
    """ Configuration for Solo """

    # Logging configuration
    log_level: str= Field(default="INFO")
    json_logs: bool = Field(default=True)
    log_file: Optional[str] = None

    # LLM configuration
    llm_backend: str = Field(default="llama.cpp") # or "ollama"
    model_path: Optional[str] = None

    # STT/TTS configuration
    stt_model: str = Field(default="faster-whisper-small")
    tts_voice: str = Field(default="en_us/vctk_low/p303")

    # API configuration
    api_host: str = Field(default="0.0.0.0")
    api_port: str = Field(default=8080)

    # Dashboard configuration
    dashboard_host: str = Field(default="0.0.0.0")
    dashboard_port: str = Field(default=8501)

    def __init__(self, config_path: str = None, **data):
        """ Initialize configuration from environment variables or .env file """
        # load from .env if provided
        if config_path:
            load_dotenv(config_path)
        else:
            load_dotenv

        # Override with env variables
        env_vars = {
            "log_level": os.getenv("SOLO_LOG_LEVEL"),
            "json_logs": os.getenv("SOLO_JSON_LOGS"),
            "log_file": os.getenv("SOLO_LOG_FILE"),
            "llm_backend": os.getenv("SOLO_LLM_BACKEND"),
            "model_path": os.getenv("SOLO_MODEL_PATH"),
            "stt_model": os.getenv("SOLO_STT_MODEL"),
            "tts_voice": os.getenv("SOLO_TTS_VOICE"),
            "api_host": os.getenv("SOLO_API_HOST"),
            "api_port": os.getenv("SOLO_API_PORT"),
            "dashboard_host": os.getenv("SOLO_DASHBOARD_HOST"),
            "dashboard_port": os.getenv("SOLO_DASHBOARD_PORT"),
        }
        # filter out None values
        env_vars = {k: v for k, v in env_vars.items() if v is not None}

        # Convert string booleans
        if  "json_logs" in env_vars and isinstance(env_vars["json_logs"], str):
            env_vars["json_logs"] = env_vars["json_logs"].lower() == "true"

        # Convert numeric values
        for key in ["api_port", "dashboard_port"]:
            if key in env_vars and isinstance(env_vars[key], str):
                try:
                    env_vars[key] = int(env_vars[key])
                except ValueError:
                    pass


        # Merge with provided data
        merged_data = {**data, **env_vars}

        super().__init__(**merged_data)
