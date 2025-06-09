"""
Module: app/core/llm_demo.py
Purpose: Simple CLI demo for testing the LLM runner
"""

import asyncio
import argparse
import sys
import os

from app.core.llm_runner import LlamaModel
from app.utils.logger import setup_logger

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='LLM Demo')
    parser.add_argument('--model', type=str, required=True, help='Path to the GGUF model file')
    parser.add_argument('--prompt', type=str, help='Prompt to send to the model')
    parser.add_argument('--system', type=str, help='System prompt')
    parser.add_argument('--interactive', action='store_true', help='Run in interactive mode')
    args = parser.parse_args

    logger = setup_logger(json_format=False)
    logger.info(f"Loading model from {args.model}")

    # Initialize the model
    try:
        model = LLamaModel(model_path=args.model)
        logger.info("Model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {str(e)}")
        return

    if args.interactive:
        logger.info("Starting interactive mode (Ctrl+C to exit)")
        print("\nLLM Chat Demo - Type your message (Ctrl+C to exit)")

        try:
            while True:
                prompt = input("\n> ")
                if prompt.lower() in ['exit', 'quit']:
                    break

                print("Generating respone...")
                response, metrics = await model.generate(prompt=prompt, system_prompt=args.system)

                print(f"\nResponse: {response}")
                print(f"Generated {metrics['tokens_used']} tokens in {metrics['generate_time_ms']/1000:.2f}s")
        except KeyboardInterrupt:
            print("\nExiting...")
    else:
        if not args.prompt:
            logger.error("Prompt is required in non-interactive mode")
            return

        response, metrics = await model.generate(prompt=args.prompt, system_prompt=args.system)

        print(f"\nResponse: {response}")
        print(f"Generated {metrics['tokens_used']} tokens in {metrics['generation_time_ms']/1000:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())
