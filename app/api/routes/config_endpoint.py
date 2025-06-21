from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional, Any

from app.api.server import config, logger
from app.config import get_config, update_config

router = APIRouter(prefix="\config", tags=["Configuration"])

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

@router.get("", response_model=ConfigResponse)
async def get_config():
    """ Get the current configuration """
    config_dict = config.dict()

    return ConfigResponse(config=config_dict)

@router.post("/update", response_model=ConfigUpdateResponse)
async def update_configuration(request: ConfigUpdateRequest):
    """ Update system configuration """

    # simplified for now, this needs to be expanded on and handled more carefully

    updated_config = config.dict()

    if request.llm:
        updated_config["llm"].update(request.llm)

    if request.log_level:
        updated_config["log_level"] = request.log_level

    if request.api_port:
        updated_config["api_port"] = request.api_port

    try:
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
