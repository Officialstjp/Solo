"""
Module: app/core/llm_tester.py
Purpose: Interactive component for testing LLM via event bus
"""

import asyncio
import uuid
from datetime import datetime
import aioconsole

from utils.logger import setup_logger
from utils.events import EventBus, EventType, LLMRequestEvent, LLMResponseEvent

SETTINGS = {
    "system_prompt": """You are a helpful AI assistant called Solo.
Provide clear, accurate, and concise responses to questions.
If you don't know something, say so rather than making up information."""
}

async def llm_tester_component(event_bus: EventBus):
    """Interactive component to test LLM via the event bus"""

    logger = setup_logger()
    logger.info("Starting LLM tester component")

    active_requests = set()
    response_events = {}

    listener_task = asyncio.create_task(
        response_listener(event_bus, active_requests, response_events)
    )

    print("\n=== Default System Prompt ===")
    print(SETTINGS["system_prompt"])
    print("=============================\n")

    use_default = await aioconsole.ainput(f"Use default system prompt? (Y/n): ")
    system_prompt = SETTINGS["system_prompt"] if use_default.lower() in ('', 'y', 'yes') else None

    if use_default.lower() in ('', 'y', 'yes'):
        print("Using default system prompt.")
    else:
        system_prompt = await aioconsole.ainput("Enter custom system prompt: ")
        if not system_prompt.strip():
            system_prompt = None
            print("No system prompt will be used.")

    print("\nEnter a prompt (or 'exit' to quit, 'clear' to clear screen):")

    try:
        while True:
            has_responses = False
            for session_id in list(response_events.keys()):
                has_responses = True
                event = response_events.pop(session_id)
                print(f"\n--- Response (session {session_id[-6:]}) ---")
                print(f"{event.response}")
                print(f"Generated {event.tokens_used} tokens in {event.generation_time_ms/1000:.2f}s")
                print("-------------------------------------------\n")
                if session_id in active_requests:
                    active_requests.remove(session_id)

            if not active_requests:
                prompt = await aioconsole.ainput("> ")

                if prompt.lower() == 'exit':
                    break

                if prompt.lower() == 'clear':
                    print("\033c", end="")
                    continue

                if prompt.lower() == 'system':
                    print(f"\n=== Current system prompt ===\n{SETTINGS['system_prompt']}")
                    new_prompt = await aioconsole.ainput("\nEnter new system prompt (or press Enter to keep currenrt):")
                    if new_prompt.strip():
                        SETTINGS["system_prompt"] = new_prompt
                        print("- System prompt updated. -")

                if not prompt.strip():
                    continue

                session_id = str(uuid.uuid4())
                active_requests.add(session_id)

                request_event = LLMRequestEvent(
                    session_id=session_id,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    parameters={
                        "max_tokens": 512,
                        "temperature": 0.7,
                        "top_p": 0.95
                    }
                )

                logger.info(f"Sending LLM request: {session_id}")
                print(f"Request sent (session {session_id[-6:]}), waiting for response...")
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

    logger.info ("LLM Tester stopped")

async def response_listener(event_bus: EventBus, active_requests: set, response_events: dict):
    """ Listen for LLM responses and add them to the queue """
    logger = setup_logger()

    async for event in event_bus.subscribe(EventType.LLM_RESPONSE):
        if isinstance(event, LLMResponseEvent):
            logger.info(f"Received LLM response: session_id={event.session_id}")
            response_events[event.session_id] = event
