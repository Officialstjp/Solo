from fastapi import APIRouter, HTTPException, Depends, FastAPI
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.core.model_manager import ModelManager
from app.api.dependencies import get_model_manager, get_db_service
from app.utils.logger import get_logger

class ModelInfo(BaseModel):
    name: str
    path: str
    format: str
    parameter_size: str
    quantization: str
    context_length: str
    file_size_mb: str

class ModelSelectionRequest(BaseModel):
    model_path: str

class ModelResponse(BaseModel):
    status: str
    message: str
    model: Optional[ModelInfo] = None


logger = get_logger(name="Models_API", json_format=False)

def create_router(app: FastAPI) -> APIRouter:
    """
    Create and configure the models router
    Args:
        App: the FastAPI application instance
    Returns:
        APIRouter: Configured router with model endpoints
    """
    router = APIRouter(prefix="/models", tags=["Models"])

    """ list all models """
    @router.get("/list", response_model=List[Dict[str, Any]])
    async def list_models(
        model_manager: ModelManager = Depends(get_model_manager)
    ):
        try:
            models = model_manager.get_models()
            return models
        except Exception as e:
            logger.error(f"Error listing models")
            raise HTTPException(status_code=500, detail=(f"Failed to list models: {str(e)}"))

    """ Get a model """
    @router.get("/{model_id}")
    async def get_model(
        model_id: str,
        model_manager: ModelManager = Depends(get_model_manager)
    ):
        try:
            model = model_manager.get_model(model_id)
            if not model:
                raise HTTPException(status_code=404, detail=(f"Model {model_id} not found"))
            return model
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting model {model_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get model: {str(e)}")

    """ Get detailed information about a specific model"""
    @router.get("/info/{model_name}", response_model=ModelResponse)
    async def get_model_info(
        model_name: str,
        model_manager: ModelManager = Depends(get_model_manager)
    ):
        if not model_manager:
            raise HTTPException(status_code=500, detail="Model manager not initialized")
        try:
            models = model_manager.list_available_models()
            selected_model = None

            for model in models:
                if model.name == model_name:
                    selected_model = model
                    break

            if not selected_model:
                raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")

            return ModelResponse(
                status="success",
                message=f"Found model: {model_name}",
                model=ModelInfo(
                    name=selected_model.name,
                    path=selected_model.path,
                    format=selected_model.format.value,
                    parameter_size=selected_model.parameter_size,
                    quantization=selected_model.quantization,
                    context_length=selected_model.context_length,
                    file_size_mb=selected_model.file_size_mb
                )
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting model info for model")
            raise HTTPException(status_code=500, detail=f"Failed to get model info: {str(e)}")

    @router.post("/select", response_model=ModelResponse)
    async def select_model(
        request: ModelSelectionRequest,
        model_manager: ModelManager = Depends(get_model_manager)
    ):
        """ Select a model to use """
        if not model_manager:
            raise HTTPException(status_code=500, detail="Model Manager not initialized")

        model_info = model_manager.get_model_info(request.model_path)
        if not model_info:
            raise HTTPException(status_code=404, detail=f"Model at path '{request.model_path} not found")

        success = model_manager.set_default_model(request.model_path)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to set default model")

        # LLM needs to be reloaded, send event to the LLM Runner to reload

        logger.info(f"Selected model: {model_info.name} ({request.model_path})")

        return ModelResponse(
            status="success",
            message=f"Selected model: {model_info.name}",
            model=ModelInfo(
                name=model_info.name,
                path=model_info.path,
                format=model_info.format.value,
                parameter_size=model_info.parameter_size,
                quantization=model_info.quantization,
                context_length=model_info.context_length,
                file_size_mb=model_info.file_size_mb
            )
        )

    """
    Add other endpoints as needed
    @router.get("/[keyword]/[Keyword]", response_model=[defined response model])
    @router.post("/... ", ...)
    async def [function name](
            dependency: [Class] = Depends([func]) # <- funcs defined in dependencies.py
            )

    """

    return router
