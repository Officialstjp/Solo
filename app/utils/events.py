"""
Module Name: app/utils/events.py
Purpose   : Event handling utilities for the application.
Params    : None
History   :
    Date            Notes
    2025-06-08      Init


"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from enum import Enum
import asyncio
from datetime import datetime

class EventType(str, Enum):
    STT = "speech_to_text"
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    TTS = "text_to_speech"
    ACTION = "action_request"
    STATUS = "status_update"

class BaseEvent(BaseModel):
    """ Base event class for all events in the system """
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = None

class STTEvent(BaseEvent):
    """ Speech to text event """
    event_type: EventType = EventType.STT
    text: str
    confidence: float
    audio_duration_ms: Optional[int] = None

class LLMRequestEvent(BaseEvent):
    """ Request to LLM """
    event_type: EventType = EventType.LLM_REQUEST
    prompt: str
    system_prompt: Optional[str] = None
    parameters: Dict[str, Any] = {}

class LLMResponse(BaseEvent):
    """ Response from LLM """
    event_type: EventType = EventType.LLM_RESPONSE
    response: str
    tokens_used: int
    generation_time_ms: int
    model_name: str

class TTSEvent(BaseEvent):
    """ Text to speech event """
    event_type: EventType = EventType.TTS
    text: str
    voice_id: str

class ActionRequestEvent(BaseEvent):
    """ Request for an action to be performed """
    event_type: EventType = EventType.ACTION
    action_type: str
    parameters: Dict[str, Any] = {}

class StatusUpdateEvent(BaseEvent):
    """ Status update from any component """
    event_type: EventType = EventType.STATUS
    component: str
    status: Dict[str, Any] = {}

# Event Queue
class EventBus:
    """ Central event bus for pub/sub communication """

    def __init__(self):
        self.queues: Dict[EventType, asyncio.Queue] = {
            event_type: asyncio.Queue() for event_type in EventType
        }

    async def publish(self, event: BaseEvent):
        """ Pusblish an Event to its corresponding queue """
        await self.queues[event.event_type].put(event)

    async def subscribe(self, event_type: EventType):
        """ Subscribe to events of a specific type """
        while True:
            event = await self.queues[event_type].get()
            yield event
            self.queues[event_type].task_done
