"""
Module Name: app/utils/events.py
Purpose   : Event handling utilities for the application.
Params    : None
History   :
    Date            Notes
    2025-06-08      Init


"""
import asyncio
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union, Callable
from dataclasses import dataclass
from enum import Enum, auto
from datetime import datetime
import uuid

class EventType(str, Enum):
    STT = "speech_to_text"
    TTS = "text_to_speech"

    LLM_REQUEST = auto()
    LLM_RESPONSE = auto()

    MODEL_LOAD_REQUEST = auto()
    MODEL_LOADED = auto()
    MODEL_UNLOADED = auto()
    MODEL_LOADING_ERROR = auto()

    SESSION_CLEAR = auto()
    SESSION_LIST = auto()

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
    status: Dict[str, Any] = Field(default_factory=dict)

class LLMRequestEvent(BaseEvent):
    """ Request to LLM """
    event_type: EventType = EventType.LLM_REQUEST
    prompt: str
    system_prompt: Optional[str] = None
    session_id: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    chat_history: Optional[List[Dict[str, str]]] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}
        if self.session_id is None:
            self.session_id = str(uuid.uuid4())

class LLMResponseEvent(BaseEvent):
    """ Response from LLM """
    event_type: EventType = EventType.LLM_RESPONSE
    response: str
    session_id: str
    tokens_used: int
    generation_time_ms: float
    model_name: str
    cached: bool = False

@dataclass
class ModelLoadRequestEvent(BaseEvent):
    event_type: EventType = EventType.MODEL_LOAD_REQUEST
    model_id: str
    priority: bool = False

@dataclass
class ModelLoadedEvent(BaseEvent):
    event_type: EventType = EventType.MODEL_LOADED
    model_id: str
    success: bool
    error_message: Optional[str] = None
    model_info: Optional[Dict[str, Any]] = None

@dataclass
class ModelUnloadedEvent(BaseEvent):
    event_type: EventType = EventType.MODEL_UNLOADED
    model_id: str
    reason: str  # e.g., "manual", "lru", "error"

@dataclass
class SessionClearEvent(BaseEvent):
    event_type: EventType = EventType.SESSION_CLEAR
    session_id: str

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
            self.queues[event_type].task_done()

    async def subscribe_with_handler(self, event_type: EventType, handler: Callable):
        """
        Subscribe to events of a specific type with a handler function

        Args:
            event_type: The type of event to subscribe to
            handler: A function that takes an event and returns True if it handled it
                    and should be unsubscribed, False otherwise
        Returns:
            str: Subscription ID
        """
        subscription_id = str(uuid.uuid4())
        self.subscriptions[event_type][subscription_id] = handler
        return subscription_id

    async def unsubscribe(self, subscription_id: str):
        """Unsubscribe from events using a subscription ID"""
        for event_type in self.subscriptions:
            if subscription_id in self.subscriptions[event_type]:
                del self.subscriptions[event_type][subscription_id]
                return True
        return False
