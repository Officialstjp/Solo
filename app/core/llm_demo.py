"""
Module: app/core/llm_demo.py
Purpose: Simple CLI demo for testing the LLM runner
Currently not functional due to the way imports handle
History:
    Date            Notes
    2025-06-08      Init
    2025-06-15      Updated to use enhanced model management
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path

from app.core.llm_runner import LlamaModel
from app.core.model_manager import ModelManager
from app.core.prompt_templates import PromptLibrary
from app.utils.logger import get_logger

async def main():
    """Simple CLI demo for testing the LLM directly"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='LLM Demo')
    parser.add_argument('--model', type=str, help='Path to the model file')
    parser.add_argument('--prompt', type=str, help='Prompt to send to the model')
    parser.add_argument('--system', type=str, help='System prompt')
    parser.add_argument('--interactive', action='store_true', help='Run in interactive mode')
    parser.add_argument('--template', type=str, help='Prompt template to use')
    parser.add_argument('--temperature', type=float, default=0.7, help='Temperature (default: 0.7)')
    parser.add_argument('--top-p', type=float, default=0.95, help='Top-p sampling (default: 0.95)')
    parser.add_argument('--max-tokens', type=int, default=512, help='Max tokens to generate (default: 512)')
    args = parser.parse_args()

    logger = get_logger(name = "LLM_demo", json_format=False)

    # Set up model manager and prompt library
    model_manager = ModelManager()
    prompt_library = PromptLibrary()

    # Determine model path
    model_path = args.model
    if not model_path:
        # Use default model if available
        default_model = model_manager.get_default_model()
        if default_model:
            model_path = default_model.path
            logger.info(f"Using default model: {default_model.name}")
        else:
            logger.error("No model specified and no default model found")
            print("Please specify a model with --model")
            return

    logger.info(f"Loading model from {model_path}")

    # Initialize the model
    try:
        model = LlamaModel(
            model_path=model_path,
            model_manager=model_manager,
            prompt_library=prompt_library,
            prompt_template=args.template,
            cache_enabled=True
        )
        logger.info("Model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {str(e)}")
        return

    if args.interactive:
        logger.info("Starting interactive mode (Ctrl+C to exit)")
        print("\nLLM Chat Demo - Type your message (Ctrl+C to exit)")
        print("Commands: 'exit' to quit, 'system' to change system prompt, 'params' to change parameters")

        # Initialize chat history
        chat_history = []
        system_prompt = args.system
        params = {
            "max_tokens": args.max_tokens,
            "temperature": args.temperature,
            "top_p": args.top_p
        }

        if system_prompt:
            print(f"Using system prompt: {system_prompt}")

        try:
            while True:
                prompt = input("\n> ")
                if prompt.lower() in ['exit', 'quit']:
                    break

                if prompt.lower() == 'system':
                    print(f"Current system prompt: {system_prompt or 'None'}")
                    new_prompt = input("Enter new system prompt (or press Enter to keep current): ")
                    if new_prompt.strip():
                        system_prompt = new_prompt
                        print("System prompt updated.")
                    continue

                if prompt.lower() == 'params':
                    print(f"Current parameters: max_tokens={params['max_tokens']}, "
                          f"temperature={params['temperature']}, top_p={params['top_p']}")

                    try:
                        new_max_tokens = input(f"max_tokens [{params['max_tokens']}]: ")
                        if new_max_tokens.strip():
                            params['max_tokens'] = int(new_max_tokens)

                        new_temp = input(f"temperature [{params['temperature']}]: ")
                        if new_temp.strip():
                            params['temperature'] = float(new_temp)

                        new_top_p = input(f"top_p [{params['top_p']}]: ")
                        if new_top_p.strip():
                            params['top_p'] = float(new_top_p)

                        print("Parameters updated.")
                    except ValueError:
                        print("Invalid value, keeping current parameters.")
                    continue

                print("Generating response...")

                # Add user message to history
                chat_history.append({"role": "user", "content": prompt})

                response, metrics = await model.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    chat_history=chat_history,
                    max_tokens=params["max_tokens"],
                    temperature=params["temperature"],
                    top_p=params["top_p"]
                )

                # Add assistant response to history
                chat_history.append({"role": "assistant", "content": response})

                # Limit history length (keep last 10 exchanges)
                if len(chat_history) > 20:
                    chat_history = chat_history[-20:]

                print(f"\nResponse: {response}")
                print(f"Generated {metrics['tokens_used']} tokens in {metrics['generation_time_ms']/1000:.2f}s")
                print(f"({metrics['tokens_per_second']:.2f} tokens/s)")

        except KeyboardInterrupt:
            print("\nExiting...")
    else:
        if not args.prompt:
            logger.error("Prompt is required in non-interactive mode")
            return

        response, metrics = await model.generate(
            prompt=args.prompt,
            system_prompt=args.system,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            top_p=args.top_p
        )

        print(f"\nResponse: {response}")
        print(f"Generated {metrics['tokens_used']} tokens in {metrics['generation_time_ms']/1000:.2f}s")
        print(f"({metrics['tokens_per_second']:.2f} tokens/s)")

if __name__ == "__main__":
    asyncio.run(main())
