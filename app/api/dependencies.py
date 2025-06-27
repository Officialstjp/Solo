"""
Moduele Name: app/api/dependencies.py
Purpose     : Dependecy injection functions for FastAPI routes
"""
from fastapi import Depends, Request
from app.utils.events import EventBus
from app.core.model_manager import ModelManager
from app.core.prompt_templates import PromptLibrary
from app.config import AppConfig

async def get_config(request: Request) -> AppConfig:
    return request.app.state.config

async def get_event_bus(request: Request) -> EventBus:
    return request.app.state.event_bus

async def get_model_manager(request: Request) -> ModelManager:
    return request.app.state.model_manager

async def get_prompt_library(request: Request) -> PromptLibrary:
    return request.app.state.prompt_library

async def get_metrics(request: Request) -> dict:
    return request.app.state.metrics
