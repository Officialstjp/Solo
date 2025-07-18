# app/api/routes/config_endpoint.py

"""
Module Name: app/api/routes/config_endpoint.py
Purpose   : API endpoints for configuration management
"""
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import json
import os

from app.config import AppConfig
from app.api.dependencies import get_config
from app.utils.logger import get_logger

logger = get_logger(name="Config_API", json_format=False)

class ConfigUpdateRequest(BaseModel):
    """Request model for updating configuration values"""
    path: str  # Dot notation path to the config property (e.g., "llm.temperature")
    value: Any  # New value to set

class ConfigSectionResponse(BaseModel):
    """Response model for a config section"""
    values: Dict[str, Any]
    description: Optional[str] = None

def create_router(app: FastAPI) -> APIRouter:
    """
    Create and configure the config router

    Args:
        app: The FastAPI application instance

    Returns:
        APIRouter: Configured router with config endpoints
    """
    router = APIRouter(prefix="/config", tags=["Config"])

    @router.get("/", response_model=Dict[str, Any])
    async def get_full_config(
        config: AppConfig = Depends(get_config)
    ):
        """
        Get the full application configuration
        """
        try:
            # Return a dict representation of the config
            # This assumes AppConfig has a method to convert to dict
            config_dict = config.to_dict()

            # Filter out sensitive information
            if "api_keys" in config_dict:
                config_dict["api_keys"] = {k: "***" for k in config_dict["api_keys"]}

            return config_dict
        except Exception as e:
            logger.error(f"Error retrieving config: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to retrieve config: {str(e)}")

    @router.get("/{section}", response_model=ConfigSectionResponse)
    async def get_config_section(
        section: str,
        config: AppConfig = Depends(get_config)
    ):
        """
        Get a specific section of the configuration
        """
        try:
            config_dict = config.to_dict()

            if section not in config_dict:
                raise HTTPException(status_code=404, detail=f"Config section '{section}' not found")

            section_data = config_dict[section]

            # If there's a description for this section, include it
            description = None
            if hasattr(config, f"{section}_description"):
                description = getattr(config, f"{section}_description")

            return ConfigSectionResponse(
                values=section_data,
                description=description
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving config section '{section}': {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to retrieve config section: {str(e)}")

    @router.post("/update", response_model=Dict[str, Any])
    async def update_config(
        request: ConfigUpdateRequest,
        config: AppConfig = Depends(get_config)
    ):
        """
        Update a specific configuration value
        """
        try:
            # Split the path into parts
            path_parts = request.path.split(".")

            # Navigate to the correct part of the config
            current = config.to_dict()
            parent = None
            last_key = None

            for i, part in enumerate(path_parts):
                if i == len(path_parts) - 1:
                    # We've reached the leaf node
                    parent = current
                    last_key = part
                    break

                if part not in current:
                    raise HTTPException(status_code=404, detail=f"Config path '{request.path}' not found")

                current = current[part]

            if parent is None or last_key is None:
                raise HTTPException(status_code=400, detail="Invalid config path")

            # Update the value
            old_value = parent.get(last_key)
            parent[last_key] = request.value

            # Save the updated config
            config.save()

            return {
                "status": "success",
                "path": request.path,
                "old_value": old_value,
                "new_value": request.value
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating config: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")

    @router.post("/reload", response_model=Dict[str, Any])
    async def reload_config(
        config: AppConfig = Depends(get_config)
    ):
        """
        Reload the configuration from disk
        """
        try:
            # Reload the config
            config.reload()

            return {
                "status": "success",
                "message": "Configuration reloaded successfully"
            }
        except Exception as e:
            logger.error(f"Error reloading config: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to reload config: {str(e)}")

    return router
