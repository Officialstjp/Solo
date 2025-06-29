from fastapi import APIRouter, HTTPException, Depends, FastAPI
from pydantic import BaseModel
from typing import Dict, Optional, Any

from app.config import get_config, update_config
from app.api.dependencies import get_config
from app.utils.logger import get_logger

logger = get_logger(name="API_Server", json_format=False)

class ConfigResponse(BaseModel):
    config: Dict[str, Any]

class ConfigUpdateRequest(BaseModel):
    llm: Optional[Dict[str, Any]] = None
    log_level: Optional[str] = None
    api_port: Optional[str] = None
    # add other configurables as needed...

class ConfigUpdateResponse(BaseModel):
    status: str
    message: str

def creata_router(app: FastAPI) -> APIRouter:
    """
    Create and configure the configuration router
    Args:
        app (FastAPI): The FastAPI application instance
    Returns:
        APIRouter: Configured router for configuration endpoints
    """
    router = APIRouter(prefix="/config", tags=["Configuration"])

    @router.get("", response_model=ConfigResponse)
    async def get_configuration(
        config = Depends(get_config)
    ):
        """ Get the current configuration """
        try:
            config_dict = config.dict()
            return ConfigResponse(config=config_dict)
        except Exception as e:
            logger.error(f"Failed to retrieve configuration: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to retrieve configuration: {str(e)}")

    @router.post("/update", response_model=ConfigUpdateResponse)
    async def update_configuration(
        request: ConfigUpdateRequest,
        config = Depends(get_config)
    ):
        """ Update system configuration """
        try:
            # simplified for now, this needs to be expanded on and handled more carefully

            updated_config = config.dict()

            if request.llm:
                updated_config["llm"].update(request.llm)

            if request.log_level:
                updated_config["log_level"] = request.log_level

            if request.api_port:
                updated_config["api_port"] = request.api_port

            # apply updates
            # NOTE: this needs proper config validation, aswell as a
            # mechanism to apply changes to running components.
            logger.info(f"Updating configuration: {updated_config}")

            return ConfigUpdateResponse(
                status="success",
                message="Configuration updated successfully"
            )

        except Exception as e:
            logger.error(f"Failed to update configuration: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to update configuration: {str(e)}")

    return router
