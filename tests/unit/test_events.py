"""
Module Name: test_events.py
Purpose   : Unit tests for the event system
Params    : None
History   :
    Date          Notes
    07.21.2025    Initial version
"""

import pytest
import asyncio
from unittest.mock import MagicMock

# ===== functions =====

@pytest.mark.asyncio
async def test_event_emitter():
    """Test that events can be emitted and received."""
    from app.utils.events import EventEmitter

    # Create an event emitter
    emitter = EventEmitter()

    # Create a mock handler
    handler = MagicMock()

    # Register the handler
    emitter.on("test_event", handler)

    # Emit an event
    await emitter.emit("test_event", {"data": "test"})

    # Check that the handler was called
    handler.assert_called_once_with({"data": "test"})


@pytest.mark.asyncio
async def test_event_once():
    """Test that events registered with once are only triggered once."""
    from app.utils.events import EventEmitter

    # Create an event emitter
    emitter = EventEmitter()

    # Create a mock handler
    handler = MagicMock()

    # Register the handler to be called only once
    emitter.once("test_event", handler)

    # Emit the event twice
    await emitter.emit("test_event", {"data": "test1"})
    await emitter.emit("test_event", {"data": "test2"})

    # Check that the handler was called only once with the first event
    handler.assert_called_once_with({"data": "test1"})


@pytest.mark.asyncio
async def test_event_off():
    """Test that event handlers can be removed."""
    from app.utils.events import EventEmitter

    # Create an event emitter
    emitter = EventEmitter()

    # Create a mock handler
    handler = MagicMock()

    # Register the handler
    emitter.on("test_event", handler)

    # Emit an event
    await emitter.emit("test_event", {"data": "test1"})

    # Remove the handler
    emitter.off("test_event", handler)

    # Emit another event
    await emitter.emit("test_event", {"data": "test2"})

    # Check that the handler was called only once with the first event
    handler.assert_called_once_with({"data": "test1"})
