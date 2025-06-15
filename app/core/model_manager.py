"""
Module Name: app/core/model_manager.py
Purpose   : Manages LLM model selection, validation, and metadata
Params    : None
History   :
    Date            Notes
    2025-06-15      Initial implementation
"""

import os
import json
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from enum import Enum
from dataclasses import dataclass

class ModelFormat(str, Enum):
    """Known model formats with their prompt templates"""
    MISTRAL = "mistral"
    MISTRAL_INSTRUCT = "mistral-instruct"
    LLAMA2 = "llama2"
    LLAMA3 = "llama3"
    TINYLLAMA = "tinyllama"
    PHI = "phi"
    PHI2 = "phi2"
    PHI3 = "phi3"
    PHI4 = "phi4"
    MIXTRAL = "mixtral"
    UNCATEGORIZED = "uncategorized"

@dataclass
class ModelInfo:
    """Information about a specific model"""
    path: str
    name: str
    format: ModelFormat
    context_length: int
    quantization: str
    parameter_size: str
    supported_features: List[str]
    metadata: Dict[str, Any]

    @property
    def file_size_mb(self) -> float:
        """Get the file size in MB"""
        try:
            return os.path.getsize(self.path) / (1024 * 1024)
        except (FileNotFoundError, OSError):
            return 0.0

    @property
    def short_description(self) -> str:
        """Get a short description of the model"""
        return f"{self.name} ({self.parameter_size}, {self.quantization}, {self.file_size_mb:.1f}MB)"

class ModelManager:
    """Manages LLM models, their detection, validation and metadata"""

    def __init__(self, models_dir: str = None, default_model: str = None):
        """Initialize the model manager

        Args:
            models_dir: Directory containing model files
            default_model: Path to the default model to use
        """
        self.models_dir = models_dir if models_dir else self._get_default_models_dir()
        self.models_cache: Dict[str, ModelInfo] = {}
        self.default_model_path = default_model
        self.scan_models()

    def _get_default_models_dir(self) -> str:
        """Get the default models directory"""
        # Try environment variable first
        if os.environ.get("SOLO_MODELS_DIR"):
            return os.environ.get("SOLO_MODELS_DIR")

        # Try to find models directory relative to the project
        base_dir = Path(__file__).resolve().parent.parent.parent
        models_dir = base_dir / "models"
        if models_dir.exists():
            return str(models_dir)

        # Default to current directory
        return "models"

    def scan_models(self) -> Dict[str, ModelInfo]:
        """Scan the models directory for compatible models

        Returns:
            Dictionary mapping model paths to ModelInfo objects
        """
        self.models_cache = {}

        if not os.path.exists(self.models_dir):
            return self.models_cache

        # Look for model files with supported extensions
        for root, _, files in os.walk(self.models_dir):
            for file in files:
                if file.endswith((".gguf", ".bin", ".ggml")):
                    model_path = os.path.join(root, file)
                    try:
                        model_info = self.analyze_model(model_path)
                        self.models_cache[model_path] = model_info
                    except Exception as e:
                        # Skip models that can't be analyzed
                        print(f"Error analyzing model {model_path}: {str(e)}")

        return self.models_cache

    def analyze_model(self, model_path: str) -> ModelInfo:
        """Analyze a model file to extract information

        Args:
            model_path: Path to the model file

        Returns:
            ModelInfo object with model metadata
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        # Extract basic info from filename
        filename = os.path.basename(model_path)
        name = filename.split('.')[0]

        # Determine model format based on filename
        model_format = self._detect_model_format(filename)

        # Determine quantization based on filename
        quantization = self._detect_quantization(filename)

        # Determine parameter size based on filename
        parameter_size = self._detect_parameter_size(filename)

        # Default context length
        context_length = 4096

        # Default supported features
        supported_features = ["text-generation"]

        # Additional metadata
        metadata = {
            "file_path": model_path,
            "last_modified": os.path.getmtime(model_path),
        }

        return ModelInfo(
            path=model_path,
            name=name,
            format=model_format,
            context_length=context_length,
            quantization=quantization,
            parameter_size=parameter_size,
            supported_features=supported_features,
            metadata=metadata
        )

    def _detect_model_format(self, filename: str) -> ModelFormat:
        """Detect the model format based on filename

        Args:
            filename: Model filename

        Returns:
            ModelFormat enum value
        """
        filename_lower = filename.lower()

        if "mistral" in filename_lower:
            if "instruct" in filename_lower:
                return ModelFormat.MISTRAL_INSTRUCT
            return ModelFormat.MISTRAL
        elif "llama-3" in filename_lower or "llama3" in filename_lower:
            return ModelFormat.LLAMA3
        elif "llama-2" in filename_lower or "llama2" in filename_lower:
            return ModelFormat.LLAMA2
        elif "tinyllama" in filename_lower:
            return ModelFormat.TINYLLAMA
        elif "phi-4" in filename_lower:
            return ModelFormat.PHI4
        elif "phi-3" in filename_lower:
            return ModelFormat.PHI3
        elif "phi-2" in filename_lower:
            return ModelFormat.PHI2
        elif "phi-" in filename_lower:
            return ModelFormat.PHI
        elif "mixtral" in filename_lower:
            return ModelFormat.MIXTRAL

        return ModelFormat.UNCATEGORIZED

    def _detect_quantization(self, filename: str) -> str:
        """Detect the quantization format from filename

        Args:
            filename: Model filename

        Returns:
            Quantization format string
        """
        filename_lower = filename.lower()

        if "q4_0" in filename_lower:
            return "Q4_0"
        elif "q4_k_m" in filename_lower:
            return "Q4_K_M"
        elif "q5_k_m" in filename_lower:
            return "Q5_K_M"
        elif "q5_0" in filename_lower:
            return "Q5_0"
        elif "q6_k" in filename_lower:
            return "Q6_K"
        elif "q8_0" in filename_lower:
            return "Q8_0"
        elif "f16" in filename_lower:
            return "F16"

        return "unknown"

    def _detect_parameter_size(self, filename: str) -> str:
        """Detect the parameter size from filename

        Args:
            filename: Model filename

        Returns:
            Parameter size string (e.g., "7B", "13B")
        """
        filename_lower = filename.lower()

        if "1.1b" in filename_lower:
            return "1.1B"
        elif "1b" in filename_lower:
            return "1B"
        elif "3b" in filename_lower:
            return "3B"
        elif "7b" in filename_lower:
            return "7B"
        elif "8b" in filename_lower:
            return "8B"
        elif "13b" in filename_lower:
            return "13B"
        elif "70b" in filename_lower:
            return "70B"

        return "unknown"

    def get_model_info(self, model_path: str) -> Optional[ModelInfo]:
        """Get information about a specific model

        Args:
            model_path: Path to the model file

        Returns:
            ModelInfo object or None if model not found
        """
        # If it's in the cache, return from cache
        if model_path in self.models_cache:
            return self.models_cache[model_path]

        # If file exists but not in cache, analyze it
        if os.path.exists(model_path):
            try:
                model_info = self.analyze_model(model_path)
                self.models_cache[model_path] = model_info
                return model_info
            except Exception:
                return None

        return None

    def get_default_model(self) -> Optional[ModelInfo]:
        """Get the default model

        Returns:
            ModelInfo for the default model or None if not set/found
        """
        if not self.default_model_path:
            # If no default is set but we have models, use the first one
            if self.models_cache:
                self.default_model_path = next(iter(self.models_cache.keys()))
            else:
                return None

        return self.get_model_info(self.default_model_path)

    def set_default_model(self, model_path: str) -> bool:
        """Set the default model

        Args:
            model_path: Path to the model file

        Returns:
            True if successful, False otherwise
        """
        if not os.path.exists(model_path):
            return False

        self.default_model_path = model_path

        # Ensure it's in the cache
        if model_path not in self.models_cache:
            try:
                self.models_cache[model_path] = self.analyze_model(model_path)
            except Exception:
                return False

        return True

    def list_available_models(self) -> List[ModelInfo]:
        """List all available models

        Returns:
            List of ModelInfo objects
        """
        return list(self.models_cache.values())

    def validate_model_compatibility(self, model_path: str) -> Tuple[bool, str]:
        """Check if a model is compatible with the system

        Args:
            model_path: Path to the model file

        Returns:
            Tuple of (is_compatible, reason)
        """
        if not os.path.exists(model_path):
            return False, "Model file not found"

        # Check file extension
        if not model_path.endswith((".gguf", ".bin", ".ggml")):
            return False, "Unsupported model format (only GGUF, BIN, GGML supported)"

        # Check file size
        try:
            file_size_mb = os.path.getsize(model_path) / (1024 * 1024)
            if file_size_mb < 1:  # Less than 1MB is probably not a valid model
                return False, f"Model file too small: {file_size_mb:.2f}MB"
        except OSError:
            return False, "Cannot determine model file size"
        return True, "Model appears compatible"
