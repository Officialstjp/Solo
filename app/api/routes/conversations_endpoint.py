"""
Module Name: app/api/routes/conversations_endpoint.py
Purpose   : Endpoint for managing conversations.
Params    : None
History   :
    Date            Notes
    20.07.2025      Init
"""

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import uuid
import time

from app.core.db_service import DatabaseService
from app.core.db.users_db import Conversation, ConversationCreate, Message, MessageCreate
from app.api.dependencies import get_db_service
from app.utils.logger import get_logger

logger = get_logger(name="Conversations_API", json_format=False)

# ----- Request / Response Models -----
class ConversationResponse(BaseModel):
    converstaion_id: str
    title: str
    created_at: str
    updaeted_at: str
    message_count: int

class ConversationDetailResponse(ConversationResponse):
    messages: List[Dict[str, Any]]

class ConversationCreateRequest(BaseModel):
    title: str
    session_id: Optional[str] = None

class ConversationUpdateRequest(BaseModel):
    title: str

class MessageResponse(BaseModel):
    message_id: str
    conversation_id: str
    role: str
    content: str
    created_at: str
    model_id: Optional[str] = None
    tokens: Optional[int] = None

class MessageCreateRequest(BaseModel):
    content: str
    role: str = "user" # Default to user, server will create assistant response
    model_id: Optional[str] = None
    request_id: Optional[str] = None

def create_router(app: FastAPI) -> APIRouter:
    """
    Create and configure the conversations router

    Args:
        app: (FastAPI): The FastAPI application instance

    Returns:
        APIRouter: Configured router with conversation endpoints
    """
    router = APIRouter(prefix="/conversations", tags=["Conversations"])

    @router.get("/", response_model=List[ConversationResponse])
    async def list_user_conversations(
        request: Request,
        skip: int = 0,
        limit: int = 20,
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """ Get all conversations for the current user """
        try:
            user = request.state.user

            conversations = await db_service.users.list_user_conversations(
                user_id=user.user_id,
                skip=skip,
                limit=limit
            )

            # format
            response = []
            for conv in conversations:
                # get message count
                message_count = await db_service.users.get_conversation_message_count(
                    user_id=user.user_id,
                    conversation_id=conv.conversation_id
                )

                response.append({
                    "conversation_id": conv.conversation_id,
                    "title": conv.title,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                    "message_count": message_count
                })

            return response

        except Exception as e:
            logger.error(f"Failed to list user conversations: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.post("/", response_model=Conversation)
    async def create_conversation(
        request: Request,
        conversation: ConversationCreateRequest,
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """ Create a new conversation """
        try:
            user = request.state.user

            # create session ID if not provided
            session_id = conversation.session_id or f"session_{uuid.uuid4().hex}"

            # create conversation object
            conversation_create = ConversationCreate(
                session_id=session_id,
                title=conversation.title
            )

            new_conversation = await db_service.users.create_conversation(
                user_id=user.user_id,
                conversation_create=conversation_create
            )

            if not new_conversation:
                raise HTTPException(status_code=400, detail="Failed to create conversation")

            return new_conversation

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create conversation: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.get("/{conversation_id}", response_model=ConversationDetailResponse)
    async def get_conversation(
        conversation_id: str,
        request: Request,
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """ Get a conversation by ID with messages """
        try:
            user = request.state.user

            conversation = await db_service.users.get_conversation(
                user_id=user.user_id,
                conversation_id=conversation_id
            )

            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # Get messages for the conversation
            messages = await db_service.users.get_conversation_messages(
                user_id=user.user_id,
                conversation_id=conversation_id
            )

            # format messages
            formatted_messages = []
            for msg in messages:
                formatted_messages.append({
                    "message_id": msg.message_id,
                    "conversation_id": msg.conversation_id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat() if hasattr(msg, "created_at") and msg.created_at else None,
                    "model_id": msg.model_id,
                    "tokens": msg.tokens
                })

            # format the response
            response = {
                "conversation_id": conversation.conversation_id,
                "title": conversation.title,
                "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
                "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
                "message_count": len(formatted_messages),
                "messages": formatted_messages
            }

            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get conversation: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.put("/{conversation_id}", response_model=Conversation)
    async def update_conversation(
        conversation_id: str,
        request: Request,
        conversation: ConversationUpdateRequest,
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """ Update a conversation """
        try:
            user = request.state.user

            # check if conversation exists
            existing = await db_service.users.get_conversation(
                user_id=user.user_id,
                conversation_id=conversation_id
            )

            if not existing:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # update conversation
            updated = await db_service.users.update_conversation(
                user_id=user.user_id,
                conversation_id=conversation_id,
                conversation_update=conversation
            )

            if not updated:
                raise HTTPException(status_code=400, detail="Failed to update conversation")

            return updated

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to update conversation: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.delete("/{conversation_id}", response_model=Dict[str, str])
    async def delete_conversation(
        conversation_id: str,
        request: Request,
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """ Delete a conversation by ID """
        try:
            user = request.state.user

            # check if conversation exists
            existing = await db_service.users.get_conversation(
                user_id=user.user_id,
                conversation_id=conversation_id
            )

            if not existing:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # delete conversation
            success = await db_service.users.delete_conversation(
                user_id=user.user_id,
                conversation_id=conversation_id
            )

            if not success:
                raise HTTPException(status_code=400, detail="Failed to delete conversation")

            return {"message": "Conversation deleted successfully"}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete conversation: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @router.post("/{conversation_id}/messages", response_model=Message)
    async def create_message(
        conversation_id: str,
        request: Request,
        message: MessageCreateRequest,
        db_service: DatabaseService = Depends(get_db_service)
    ):
        """ Create a new message in a conversation """
        try:
            user = request.state.user

            # check if conversation exists
            existing = await db_service.users.get_conversation(
                user_id=user.user_id,
                conversation_id=conversation_id
            )

            if not existing:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # create message
            request_id = message.request_id or f"req_{uuid.uuid4().hex}"

            message_create = MessageCreate(
                conversation_id=conversation_id,
                role=message.role,
                content=message.content,
                model_id=message.model_id,
                request_id=request_id
            )

            new_message = await db_service.users.create_message(
                user_id=user.user_id,
                message=message_create
            )

            if not new_message:
                raise HTTPException(status_code=400, detail="Failed to create message")

            return new_message

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create message: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    return router
