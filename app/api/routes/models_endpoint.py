from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.api.server import model_manager, logger

router = APIRouter(prefix="/models", tags=["Models"])

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

# Endpoints
@router.get("/list", response_model=List[ModelInfo])
async def list_models():
    """ List all available models """

    if not model_manager:
        raise HTTPException(status_code=500, detail="Model manager not initialized")

    models = model_manager.list_available_models()

    result = []
    for model in models:
        result.append(ModelInfo(
            name=model.name,
            path=model.path,
            format=model.format.value,
            parameter_size=model.parameter_size,
            quantization=model.quantization,
            context_length=model.context_length,
            file_size_mb=model.file_size_mb
        ))

    return result

@router.get("/info/{model_name}", response_model=ModelResponse)
async def get_model_info(model_name: str):
    """ Get detailed information about a specific model"""
    if not model_manager:
        raise HTTPException(status_code=500, detail="Model manager not initialized")

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

@router.post("/select", response_model=ModelResponse)
async def select_model(request: ModelSelectionRequest):
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
