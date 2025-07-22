"""
Module Name: test_model_manager.py
Purpose   : Unit tests for the model manager component
Params    : None
History   :
    Date          Notes
    07.21.2025    Initial version
"""

import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock

# ===== functions =====

@pytest.mark.asyncio
async def test_model_manager_initialization():
    """Test that the model manager initializes correctly."""
    from app.core.model_manager import ModelManager

    with tempfile.TemporaryDirectory() as temp_dir:
        model_manager = ModelManager(models_dir=temp_dir)
        await model_manager.initialize()

        # Check that the model manager was initialized
        assert model_manager.initialized

        # Clean up
        await model_manager.close()


@pytest.mark.asyncio
async def test_model_detection():
    """Test that the model manager can detect models in the models directory."""
    from app.core.model_manager import ModelManager

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock model file
        model_path = os.path.join(temp_dir, "test_model.gguf")
        with open(model_path, "wb") as f:
            # Write some dummy data to the file
            f.write(b"GGUF")

        # Initialize the model manager with the test directory
        model_manager = ModelManager(models_dir=temp_dir)

        # Patch the model detection to return the test model
        with patch.object(model_manager, "_extract_model_metadata", return_value={
            "name": "test_model",
            "parameter_size": "7B",
            "quantization": "Q4_K_M",
            "path": model_path
        }):
            await model_manager.initialize()

            # Check that the model was detected
            assert len(model_manager.available_models) == 1
            assert model_manager.available_models[0]["name"] == "test_model"

            # Clean up
            await model_manager.close()


@pytest.mark.asyncio
async def test_model_selection():
    """Test that the model manager can select a model."""
    from app.core.model_manager import ModelManager

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock model file
        model_path = os.path.join(temp_dir, "test_model.gguf")
        with open(model_path, "wb") as f:
            # Write some dummy data to the file
            f.write(b"GGUF")

        # Initialize the model manager with the test directory
        model_manager = ModelManager(models_dir=temp_dir)

        # Patch the model detection to return the test model
        with patch.object(model_manager, "_extract_model_metadata", return_value={
            "name": "test_model",
            "parameter_size": "7B",
            "quantization": "Q4_K_M",
            "path": model_path
        }), patch.object(model_manager, "load_model", return_value=MagicMock()):
            await model_manager.initialize()

            # Select the test model
            model = await model_manager.select_model("test_model")

            # Check that the model was selected
            assert model is not None
            assert model_manager.current_model == "test_model"

            # Clean up
            await model_manager.close()
