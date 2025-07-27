"""
Module Name: tests/integration/test_event_bus_llm_runner.py
Purpose   : Integration tests for the event bus and LLM runner functionality.
Params    : None
History   :
    Date          Notes
    26.07.2025    Init
"""
import asyncio
import logging
from unittest.mock import AsyncMock, patch

import pytest
from app.core.llm_service import llm_runner_component, LLMRunner
from app.utils.events import EventBus, LLMRequestEvent

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio

async def test_llm_runner_recieves_event(caplog):
    """
    Tests that the llm_runner_component correctly subscribes to the event bus
    and receives an LLMRequestEvent.
    """

    caplog.set_level(logging.DEBUG)

    # ==== Setup ====
    # Create a mock for _process_llm_request
    mock_process_llm_request = AsyncMock()

    # 3. Create a real EventBus instance for components to communicate
    event_bus = EventBus()

    # 4. Create a mock model service to pass to the llm_runner_component
    mock_model_service = AsyncMock()

    # 5. Create a sample event to publish
    test_event = LLMRequestEvent(
        prompt="This is a test prompt",
        system_prompt="This is a system prompt",
        session_id="session-456",
        parameters={"temperature": 0.7},
        chat_history=[],
    )

    with patch("app.core.llm_service.LLMRunner._process_llm_request", new=mock_process_llm_request):
        runner_task = asyncio.create_task(
            llm_runner_component(
                event_bus=event_bus,
                model_service=mock_model_service,
                default_model_id="test-model",
            )
        )
        await event_bus.publish(test_event)
        await asyncio.sleep(0.1)  # Allow some time for the event to be processed
        mock_process_llm_request.assert_awaited_once_with(test_event)
        runner_task.cancel()
        try:
            await runner_task
        except asyncio.CancelledError:
            pass
