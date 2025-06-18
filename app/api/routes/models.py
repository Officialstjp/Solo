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
