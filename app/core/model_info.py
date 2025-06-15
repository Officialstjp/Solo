"""
Module Name: app/core/model_info.py
Purpose   : CLI utility to display information about available models
Params    : None
History   :
    Date            Notes
    2025-06-15      Initial implementation
"""

import argparse
import asyncio
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional

from core.model_manager import ModelManager, ModelInfo, ModelFormat
from utils.logger import setup_logger

def print_model_info(model_info: ModelInfo, verbose: bool = False):
    """Print information about a model

    Args:
        model_info: ModelInfo object
        verbose: Whether to print detailed information
    """
    print(f"\n{'=' * 60}")
    print(f"Model: {model_info.name}")
    print(f"{'=' * 60}")
    print(f"Format:         {model_info.format.value}")
    print(f"Size:           {model_info.parameter_size}")
    print(f"Quantization:   {model_info.quantization}")
    print(f"Context Length: {model_info.context_length}")
    print(f"File Size:      {model_info.file_size_mb:.2f} MB")
    print(f"Path:           {model_info.path}")

    if verbose:
        print(f"\nSupported Features:")
        for feature in model_info.supported_features:
            print(f"  - {feature}")

        print(f"\nMetadata:")
        for key, value in model_info.metadata.items():
            print(f"  {key}: {value}")

    print(f"\n{'=' * 60}")

async def main():
    """Main entry point for the model info CLI"""
    parser = argparse.ArgumentParser(description='Solo Model Information')
    parser.add_argument('--models-dir', type=str, help='Directory containing model files')
    parser.add_argument('--model', type=str, help='Specific model to show info for')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed information')
    args = parser.parse_args()

    logger = setup_logger(json_format=False)

    # Initialize model manager
    model_manager = ModelManager(models_dir=args.models_dir)

    # Scan for models
    models = model_manager.scan_models()

    if not models:
        print("No models found. Please check your models directory.")
        return

    print(f"Found {len(models)} models:")

    if args.model:
        # Show info for a specific model
        model_info = model_manager.get_model_info(args.model)
        if model_info:
            print_model_info(model_info, args.verbose)
        else:
            print(f"Model not found: {args.model}")
            print("\nAvailable models:")
            for path, info in models.items():
                print(f"  - {info.name} ({info.path})")
    else:
        # Show info for all models
        for i, (path, info) in enumerate(models.items()):
            print_model_info(info, args.verbose)

            if i < len(models) - 1 and not args.verbose:
                print("\n")

if __name__ == "__main__":
    asyncio.run(main())
