"""
Module Name: test_db_services.py
Purpose   : Integration tests for database services
Params    : None
History   :
    Date          Notes
    07.21.2025    Initial version
"""

import pytest
import asyncio

# ===== functions =====

@pytest.mark.asyncio
async def test_db_connection(db_service):
    """Test that the database connection works correctly."""
    # Verify that the database service is initialized
    assert db_service.initialized

    # Test a simple query
    result = await db_service.execute_query("SELECT 1 as test")
    assert result[0]["test"] == 1


@pytest.mark.asyncio
async def test_user_creation(db_service, test_user_data):
    """Test user creation in the database."""
    # Create a user
    user = await db_service.create_user(
        username=test_user_data["username"],
        email=test_user_data["email"],
        password=test_user_data["password"]
    )

    # Verify the user was created
    assert user is not None
    assert user["username"] == test_user_data["username"]
    assert user["email"] == test_user_data["email"]

    # Verify the user can be retrieved
    retrieved_user = await db_service.get_user_by_username(test_user_data["username"])
    assert retrieved_user is not None
    assert retrieved_user["username"] == test_user_data["username"]


@pytest.mark.asyncio
async def test_conversation_creation(db_service, test_user_data):
    """Test conversation creation in the database."""
    # First create a user
    user = await db_service.create_user(
        username=test_user_data["username"],
        email=test_user_data["email"],
        password=test_user_data["password"]
    )

    # Create a conversation
    conversation = await db_service.create_conversation(
        user_id=user["id"],
        title="Test Conversation"
    )

    # Verify the conversation was created
    assert conversation is not None
    assert conversation["title"] == "Test Conversation"
    assert conversation["user_id"] == user["id"]

    # Verify the conversation can be retrieved
    conversations = await db_service.get_user_conversations(user["id"])
    assert len(conversations) == 1
    assert conversations[0]["id"] == conversation["id"]
