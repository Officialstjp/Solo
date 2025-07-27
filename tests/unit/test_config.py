"""
Module Name: tests/test_config.py
Purpose   : Tests for the application configuration.
Params    : None
History   :
    Date          Notes
    26.07.2025    Initial creation.
"""
import os
from app.config import AppConfig, get_config

def test_app_config_defaults():
    """
    Tests that the AppConfig loads with default values when no environment
    variables are set.
    """
    config = AppConfig()
    assert config.app_name == "Solo"
    assert config.log_level == "DEBUG"
    assert config.llm.backend == "llama.cpp"
    assert config.llm.n_ctx == 8192

def test_app_config_env_override(monkeypatch):
    """
    Tests that AppConfig correctly loads settings from environment variables.
    """
    monkeypatch.setenv("SOLO_APP_NAME", "SoloTest")
    monkeypatch.setenv("SOLO_LOG_LEVEL", "INFO")
    monkeypatch.setenv("SOLO_LLM_BACKEND", "ollama")
    monkeypatch.setenv("SOLO_MODEL_CTX", "4096")

    config = AppConfig()

    assert config.app_name == "SoloTest"
    assert config.log_level == "INFO"
    assert config.llm.backend == "ollama"
    assert config.llm.n_ctx == 4096

def test_get_config_singleton():
    """
    Tests that get_config returns a singleton instance.
    """
    config1 = get_config(force_reload=True)
    config2 = get_config()
    assert config1 is config2

def test_get_config_force_reload():
    """
    Tests that get_config can be forced to reload the configuration.
    """
    config1 = get_config(force_reload=True)
    config1.app_name = "FirstInstance"

    config2 = get_config(force_reload=True)
    assert config2.app_name != "FirstInstance"
    assert config2.app_name == "Solo"
