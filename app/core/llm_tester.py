"""
Module: app/core/llm_tester.py
Purpose: Interactive component for testing LLM via event bus
History:
    Date            Notes
    2025-06-08      Init
    2025-06-15      Updated to work with enhanced model management
"""

import asyncio
import uuid
from datetime import datetime
import aioconsole
import os

from utils.logger import get_logger
from utils.events import EventBus, EventType, LLMRequestEvent, LLMResponseEvent

DEFAULT_SYSTEM_PROMPT = """You are an advanced research assistant, named Solo. Your task is to support, advise and teach the user in any task they come across.
Always speak in a natural tone, act like an absolute professional in the task at hand and speak as such.
Refrain from report-like breakdowns, in favor of natural conversational tone.
You currently reside in a local experimental Python environment, to be expanded into a full ecosystem.

Below is the Users request, treat it as holy and always do your best to achieve it, but point out if you are not able to.
"""

async def llm_tester_component(event_bus: EventBus, default_system_prompt: str = None):
    """Interactive component to test LLM via the event bus"""

    logger = get_logger("main")
    logger.info("Starting LLM tester component")

    active_requests = set()
    response_events = {}
    session_id = str(uuid.uuid4())  # Use one session ID for the entire conversation

    listener_task = asyncio.create_task(
        response_listener(event_bus, active_requests, response_events)
    )

    # Use provided default system prompt or fallback
    system_prompt = default_system_prompt or DEFAULT_SYSTEM_PROMPT

    print("\n=== Default System Prompt ===")
    print(system_prompt)
    print("=============================\n")

    use_default = await aioconsole.ainput(f"Use default system prompt? (Y/n): ")
    if use_default.lower() in ('', 'y', 'yes'):
        print("Using default system prompt.")
    else:
        new_prompt = await aioconsole.ainput("Enter custom system prompt: ")
        if new_prompt.strip():
            system_prompt = new_prompt
            print("Custom system prompt set.")
        else:
            print("No system prompt will be used.")
            system_prompt = None

    print("\nEnter a prompt (or type a command):")
    print("Commands: 'exit' to quit, 'clear' to clear screen, 'system' to edit system prompt")
    print("          'params' to adjust parameters, 'history' to view/clear conversation")

    # Default parameters
    params = {
        "max_tokens": 512,
        "temperature": 0.7,
        "top_p": 0.95,
        "maintain_history": True,
        "use_cache": True
    }

    try:
        while True:
            has_responses = False
            for req_session_id in list(response_events.keys()):
                has_responses = True
                event = response_events.pop(req_session_id)
                print(f"\n--- Response ---")
                print(f"{event.response}")
                print(f"Generated {event.tokens_used} tokens in {event.generation_time_ms/1000:.2f}s")
                print(f"Model: {event.model_name}")
                print("-------------------------------------------\n")
                if req_session_id in active_requests:
                    active_requests.remove(req_session_id)

            if not active_requests:
                prompt = await aioconsole.ainput("> ")

                if prompt.lower() == 'exit':
                    break

                if prompt.lower() == 'clear':
                    print("\033c", end="")
                    continue

                if prompt.lower() == 'system':
                    print(f"\n=== Current system prompt ===\n{system_prompt or 'None'}")
                    new_prompt = await aioconsole.ainput("\nEnter new system prompt (or press Enter to keep current):")
                    if new_prompt.strip():
                        system_prompt = new_prompt
                        print("- System prompt updated. -")
                    continue

                if prompt.lower() == 'params':
                    print(f"\n=== Current parameters ===")
                    for k, v in params.items():
                        print(f"{k}: {v}")

                    print("\nEnter new parameters (press Enter to keep current):")

                    new_max_tokens = await aioconsole.ainput(f"max_tokens [{params['max_tokens']}]: ")
                    if new_max_tokens.strip():
                        try:
                            params['max_tokens'] = int(new_max_tokens)
                        except ValueError:
                            print("Invalid value, keeping current.")

                    new_temp = await aioconsole.ainput(f"temperature [{params['temperature']}]: ")
                    if new_temp.strip():
                        try:
                            params['temperature'] = float(new_temp)
                        except ValueError:
                            print("Invalid value, keeping current.")

                    new_top_p = await aioconsole.ainput(f"top_p [{params['top_p']}]: ")
                    if new_top_p.strip():
                        try:
                            params['top_p'] = float(new_top_p)
                        except ValueError:
                            print("Invalid value, keeping current.")

                    new_history = await aioconsole.ainput(f"maintain_history [{params['maintain_history']}]: ")
                    if new_history.strip():
                        params['maintain_history'] = new_history.lower() in ('true', 'yes', 'y', '1')

                    new_cache = await aioconsole.ainput(f"use_cache [{params['use_cache']}]: ")
                    if new_cache.strip():
                        params['use_cache'] = new_cache.lower() in ('true', 'yes', 'y', '1')

                    print("- Parameters updated. -")
                    continue

                if prompt.lower() == 'history':
                    print("\n=== Conversation History ===")
                    if params['maintain_history']:
                        print("History is being maintained.")
                        clear_history = await aioconsole.ainput("Clear history? (y/N): ")
                        if clear_history.lower() in ('y', 'yes'):
                            # Create a new session ID to reset history
                            session_id = str(uuid.uuid4())
                            print("- History cleared. -")
                    else:
                        print("History is not being maintained.")
                        enable_history = await aioconsole.ainput("Enable history? (y/N): ")
                        if enable_history.lower() in ('y', 'yes'):
                            params['maintain_history'] = True
                            print("- History enabled. -")
                    continue

                if not prompt.strip():
                    continue

                active_requests.add(session_id)

                # Create the request event
                request_event = LLMRequestEvent(
                    session_id=session_id,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    parameters=params
                )

                logger.info(f"Sending LLM request: {session_id}")
                print(f"Request sent, waiting for response...")
                await event_bus.publish(request_event)

                await asyncio.sleep(0.2)
            else:
                await asyncio.sleep(0.2)

    except asyncio.CancelledError:
        logger.info("LLM tester cancelled")
    finally:
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass

    logger.info("LLM Tester stopped")

async def response_listener(event_bus: EventBus, active_requests: set, response_events: dict):
    """ Listen for LLM responses and add them to the queue """
    logger = get_logger("main")

    async for event in event_bus.subscribe(EventType.LLM_RESPONSE):
        if isinstance(event, LLMResponseEvent):
            logger.info(f"Received LLM response: session_id={event.session_id}")
            response_events[event.session_id] = event
