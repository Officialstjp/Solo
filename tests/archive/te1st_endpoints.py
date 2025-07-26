"""
Module Name: tests/test_endpoints.py
Purpose   : Test utility for API endpoints
Params    : None
History   :
    Date            Notes
    07.20.2025      Created for testing API functionality
"""

import argparse
import asyncio
import json
import sys
import os
import random
import time
from pathlib import Path
import http.client
import urllib.parse
import uuid

# Add the parent directory to the path so we can import from app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.logger import get_logger

logger = get_logger(name="API_Tester", json_format=False)

# ===== Test functions =====

async def test_models_endpoint(host="localhost", port=8080):
    """Test the models endpoint to list available models"""
    logger.info("Testing models endpoint...")

    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/models/list")
    response = conn.getresponse()

    if response.status == 200:
        data = json.loads(response.read().decode())
        logger.info(f"Found {len(data)} models:")
        for model in data:
            logger.info(f"  - {model.get('name')} ({model.get('parameter_size')}, {model.get('quantization')})")
        return True
    else:
        logger.error(f"Failed to get models: {response.status} {response.reason}")
        logger.error(response.read().decode())
        return False

async def test_llm_generate(prompt="Tell me a joke about programming", host="localhost", port=8080):
    """Test the LLM generation endpoint"""
    logger.info(f"Testing LLM generation with prompt: '{prompt}'")

    headers = {"Content-type": "application/json"}
    data = json.dumps({
        "prompt": prompt,
        "parameters": {
            "max_tokens": 200,
            "temperature": 0.7
        }
    })

    conn = http.client.HTTPConnection(host, port)
    conn.request("POST", "/llm/generate", data, headers)
    response = conn.getresponse()

    if response.status == 200:
        result = json.loads(response.read().decode())
        logger.info("Generation successful!")
        logger.info("Response: " + result.get("response", "No response in payload"))
        if "metrics" in result:
            metrics = result["metrics"]
            logger.info(f"Tokens: {metrics.get('tokens_used', 0)}, " +
                      f"Time: {metrics.get('generation_time_ms', 0):.2f}ms, " +
                      f"Speed: {metrics.get('tokens_per_second', 0):.2f} tokens/sec")
        return True
    else:
        logger.error(f"Failed to generate text: {response.status} {response.reason}")
        logger.error(response.read().decode())
        return False

async def test_user_registration(username, email, password, host="localhost", port=8080):
    """Test user registration endpoint"""
    logger.info(f"Testing user registration for {username}...")

    headers = {"Content-type": "application/json"}
    data = json.dumps({
        "username": username,
        "email": email,
        "password": password,
        "full_name": f"Test User {username}"
    })

    conn = http.client.HTTPConnection(host, port)
    conn.request("POST", "/auth/register", data, headers)
    response = conn.getresponse()

    if response.status in [200, 201]:
        result = json.loads(response.read().decode())
        logger.info(f"User registration successful: {result.get('username')}")
        return result
    else:
        logger.error(f"Failed to register user: {response.status} {response.reason}")
        logger.error(response.read().decode())
        return None

async def test_user_login(username, password, host="localhost", port=8080):
    """Test user login endpoint"""
    logger.info(f"Testing user login for {username}...")

    headers = {"Content-type": "application/json"}
    data = json.dumps({
        "username": username,
        "password": password,
        "remember": True
    })

    conn = http.client.HTTPConnection(host, port)
    conn.request("POST", "/auth/login", data, headers)
    response = conn.getresponse()

    if response.status == 200:
        result = json.loads(response.read().decode())
        logger.info(f"Login successful: {result.get('username')}")
        logger.info(f"Access token: {result.get('access_token')[:10]}...")
        return result.get('access_token')
    else:
        logger.error(f"Failed to login: {response.status} {response.reason}")
        logger.error(response.read().decode())
        return None

async def test_create_conversation(token, title="Test Conversation", host="localhost", port=8080):
    """Test creating a conversation"""
    logger.info(f"Creating conversation: '{title}'...")

    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    data = json.dumps({
        "title": title
    })

    conn = http.client.HTTPConnection(host, port)
    conn.request("POST", "/conversations", data, headers)
    response = conn.getresponse()

    if response.status in [200, 201]:
        result = json.loads(response.read().decode())
        logger.info(f"Conversation created: {result.get('conversation_id')}")
        return result
    else:
        logger.error(f"Failed to create conversation: {response.status} {response.reason}")
        logger.error(response.read().decode())
        return None

async def test_list_conversations(token, host="localhost", port=8080):
    """Test listing conversations"""
    logger.info("Listing conversations...")

    headers = {
        "Authorization": f"Bearer {token}"
    }

    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/conversations", headers=headers)
    response = conn.getresponse()

    if response.status == 200:
        result = json.loads(response.read().decode())
        logger.info(f"Found {len(result)} conversations")
        for conv in result:
            logger.info(f"  - {conv.get('title')} ({conv.get('conversation_id')})")
        return result
    else:
        logger.error(f"Failed to list conversations: {response.status} {response.reason}")
        logger.error(response.read().decode())
        return None

async def test_add_message(token, conversation_id, content, host="localhost", port=8080):
    """Test adding a message to a conversation"""
    logger.info(f"Adding message to conversation {conversation_id}: '{content}'...")

    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    data = json.dumps({
        "content": content,
        "role": "user"
    })

    conn = http.client.HTTPConnection(host, port)
    conn.request("POST", f"/conversations/{conversation_id}/messages", data, headers)
    response = conn.getresponse()

    if response.status in [200, 201]:
        result = json.loads(response.read().decode())
        logger.info(f"Message added: {result.get('message_id')}")
        return result
    else:
        logger.error(f"Failed to add message: {response.status} {response.reason}")
        logger.error(response.read().decode())
        return None

async def test_get_conversation(token, conversation_id, host="localhost", port=8080):
    """Test getting a conversation with messages"""
    logger.info(f"Getting conversation {conversation_id}...")

    headers = {
        "Authorization": f"Bearer {token}"
    }

    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", f"/conversations/{conversation_id}", headers=headers)
    response = conn.getresponse()

    if response.status == 200:
        result = json.loads(response.read().decode())
        logger.info(f"Got conversation: {result.get('title')}")
        logger.info(f"Message count: {result.get('message_count', 0)}")
        if "messages" in result:
            for msg in result["messages"]:
                logger.info(f"  - [{msg.get('role')}]: {msg.get('content')[:30]}...")
        return result
    else:
        logger.error(f"Failed to get conversation: {response.status} {response.reason}")
        logger.error(response.read().decode())
        return None

async def test_update_conversation(token, conversation_id, new_title, host="localhost", port=8080):
    """Test updating a conversation"""
    logger.info(f"Updating conversation {conversation_id} title to '{new_title}'...")

    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    data = json.dumps({
        "title": new_title
    })

    conn = http.client.HTTPConnection(host, port)
    conn.request("PUT", f"/conversations/{conversation_id}", data, headers)
    response = conn.getresponse()

    if response.status == 200:
        result = json.loads(response.read().decode())
        logger.info(f"Conversation updated: {result.get('title')}")
        return result
    else:
        logger.error(f"Failed to update conversation: {response.status} {response.reason}")
        logger.error(response.read().decode())
        return None

async def test_llm_with_conversation(token, conversation_id, prompt, host="localhost", port=8080):
    """Test LLM generation with a conversation context"""
    logger.info(f"Testing LLM with conversation {conversation_id}, prompt: '{prompt}'...")

    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    data = json.dumps({
        "prompt": prompt,
        "conversation_id": conversation_id,
        "parameters": {
            "max_tokens": 200,
            "temperature": 0.7
        }
    })

    conn = http.client.HTTPConnection(host, port)
    conn.request("POST", "/llm/generate", data, headers)
    response = conn.getresponse()

    if response.status == 200:
        result = json.loads(response.read().decode())
        logger.info("Generation successful!")
        logger.info("Response: " + result.get("response", "No response in payload"))
        if "metrics" in result:
            metrics = result["metrics"]
            logger.info(f"Tokens: {metrics.get('tokens_used', 0)}, " +
                      f"Time: {metrics.get('generation_time_ms', 0):.2f}ms, " +
                      f"Speed: {metrics.get('tokens_per_second', 0):.2f} tokens/sec")
        return result
    else:
        logger.error(f"Failed to generate text: {response.status} {response.reason}")
        logger.error(response.read().decode())
        return None

async def test_delete_conversation(token, conversation_id, host="localhost", port=8080):
    """Test deleting a conversation"""
    logger.info(f"Deleting conversation {conversation_id}...")

    headers = {
        "Authorization": f"Bearer {token}"
    }

    conn = http.client.HTTPConnection(host, port)
    conn.request("DELETE", f"/conversations/{conversation_id}", headers=headers)
    response = conn.getresponse()

    if response.status == 200:
        result = json.loads(response.read().decode())
        logger.info(f"Conversation deleted: {result.get('message')}")
        return True
    else:
        logger.error(f"Failed to delete conversation: {response.status} {response.reason}")
        logger.error(response.read().decode())
        return False

async def test_get_metrics(host="localhost", port=8080):
    """Test getting system and LLM metrics"""
    logger.info("Getting metrics...")

    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/metrics")
    response = conn.getresponse()

    if response.status == 200:
        result = json.loads(response.read().decode())
        logger.info("Metrics retrieved successfully")

        if "system" in result:
            sys_metrics = result["system"]
            logger.info("System Metrics:")
            logger.info(f"  CPU: {sys_metrics.get('cpu_percent')}%, Memory: {sys_metrics.get('memory_percent')}%")
            logger.info(f"  App uptime: {sys_metrics.get('app_uptime_seconds')} seconds")

        if "llm" in result:
            llm_metrics = result["llm"]
            logger.info("LLM Metrics:")
            logger.info(f"  Total requests: {llm_metrics.get('total_requests')}")
            logger.info(f"  Tokens generated: {llm_metrics.get('total_tokens_generated')}")
            logger.info(f"  Cache hits/misses: {llm_metrics.get('cache_hits')}/{llm_metrics.get('cache_misses')}")

        return result
    else:
        logger.error(f"Failed to get metrics: {response.status} {response.reason}")
        logger.error(response.read().decode())
        return None

async def test_get_config(token, host="localhost", port=8080):
    """Test getting configuration"""
    logger.info("Getting configuration...")

    headers = {
        "Authorization": f"Bearer {token}"
    }

    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/config", headers=headers)
    response = conn.getresponse()

    if response.status == 200:
        result = json.loads(response.read().decode())
        logger.info("Configuration retrieved successfully")
        return result
    else:
        logger.error(f"Failed to get configuration: {response.status} {response.reason}")
        logger.error(response.read().decode())
        return None

async def test_user_profile(token, host="localhost", port=8080):
    """Test getting user profile"""
    logger.info("Getting user profile...")

    headers = {
        "Authorization": f"Bearer {token}"
    }

    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/users/profile", headers=headers)
    response = conn.getresponse()

    if response.status == 200:
        result = json.loads(response.read().decode())
        logger.info(f"Profile retrieved: {result.get('username')}, {result.get('email')}")
        return result
    else:
        logger.error(f"Failed to get profile: {response.status} {response.reason}")
        logger.error(response.read().decode())
        return None

async def test_user_preferences(token, host="localhost", port=8080):
    """Test getting and updating user preferences"""
    logger.info("Getting user preferences...")

    headers = {
        "Authorization": f"Bearer {token}"
    }

    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/users/preferences", headers=headers)
    response = conn.getresponse()

    if response.status == 200:
        result = json.loads(response.read().decode())
        logger.info(f"Preferences retrieved: {result}")

        # Now update preferences
        logger.info("Updating preferences...")
        headers["Content-type"] = "application/json"
        data = json.dumps({
            "theme": "dark",
            "language": "en",
            "notifications_enabled": True
        })

        conn = http.client.HTTPConnection(host, port)
        conn.request("PUT", "/users/preferences", data, headers)
        update_response = conn.getresponse()

        if update_response.status == 200:
            update_result = json.loads(update_response.read().decode())
            logger.info(f"Preferences updated: {update_result}")
            return update_result
        else:
            logger.error(f"Failed to update preferences: {update_response.status} {update_response.reason}")
            logger.error(update_response.read().decode())
            return None
    else:
        logger.error(f"Failed to get preferences: {response.status} {response.reason}")
        logger.error(response.read().decode())
        return None

# ===== End-to-end test functions =====

async def test_conversation_flow(host="localhost", port=8080):
    """Test the complete conversation flow"""
    logger.info("Testing complete conversation flow...")

    # Generate unique user credentials for this test
    username = f"testuser_{int(time.time())}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    # 1. Register user
    reg_result = await test_user_registration(username, email, password, host, port)
    if not reg_result:
        # Try login directly (user might already exist)
        logger.warning("Registration failed, trying login directly...")

    # 2. Login
    token = await test_user_login(username, password, host, port)
    if not token:
        logger.error("Login failed, cannot continue test")
        return False

    # 3. Create a conversation
    conversation = await test_create_conversation(token, "Test Conversation Flow", host, port)
    if not conversation:
        logger.error("Failed to create conversation, cannot continue test")
        return False

    conversation_id = conversation.get("conversation_id")

    # 4. Add a message to the conversation
    message = await test_add_message(token, conversation_id, "Hello, how are you?", host, port)
    if not message:
        logger.error("Failed to add message, cannot continue test")
        return False

    # 5. Generate a response using the LLM
    llm_result = await test_llm_with_conversation(token, conversation_id, "Tell me about yourself", host, port)
    if not llm_result:
        logger.error("Failed to generate LLM response, cannot continue test")
        return False

    # 6. Get the conversation with messages
    conversation_detail = await test_get_conversation(token, conversation_id, host, port)
    if not conversation_detail:
        logger.error("Failed to get conversation details, cannot continue test")
        return False

    # 7. Update the conversation title
    updated_conversation = await test_update_conversation(token, conversation_id, "Updated Conversation Title", host, port)
    if not updated_conversation:
        logger.error("Failed to update conversation, cannot continue test")
        return False

    # 8. Get user profile
    profile = await test_user_profile(token, host, port)
    if not profile:
        logger.error("Failed to get user profile, cannot continue test")
        return False

    # 9. Get and update user preferences
    preferences = await test_user_preferences(token, host, port)
    if not preferences:
        logger.error("Failed to get/update preferences, cannot continue test")
        return False

    # 10. Clean up - delete the conversation
    delete_result = await test_delete_conversation(token, conversation_id, host, port)
    if not delete_result:
        logger.error("Failed to delete conversation")
        return False

    logger.info("Complete conversation flow test successful!")
    return True

# ===== Main function =====

async def main():
    parser = argparse.ArgumentParser(description="Test API endpoints for Solo application")
    parser.add_argument("--host", default="localhost", help="API host (default: localhost)")
    parser.add_argument("--port", type=int, default=8080, help="API port (default: 8080)")
    parser.add_argument("--prompt", default="Tell me a joke about programming", help="Test prompt for LLM generation")
    parser.add_argument("--test", choices=["models", "llm", "user", "conversation", "metrics", "config", "flow", "all"],
                        default="all", help="Test to run")
    parser.add_argument("--username", default=f"testuser_{int(time.time())}", help="Username for user registration/login tests")
    parser.add_argument("--email", default=None, help="Email for user registration test")
    parser.add_argument("--password", default="SecurePassword123!", help="Password for user registration/login tests")

    args = parser.parse_args()

    # Set default email based on username if not provided
    if not args.email:
        args.email = f"{args.username}@example.com"

    logger.info(f"Testing API endpoints on {args.host}:{args.port}")
    token = None

    if args.test in ["models", "all"]:
        await test_models_endpoint(args.host, args.port)

    if args.test in ["llm", "all"]:
        await test_llm_generate(args.prompt, args.host, args.port)

    if args.test in ["metrics", "all"]:
        await test_get_metrics(args.host, args.port)

    if args.test in ["user", "all", "conversation", "config", "flow"]:
        # Try user registration
        reg_result = await test_user_registration(args.username, args.email, args.password, args.host, args.port)

        # Try login regardless (might already exist)
        token = await test_user_login(args.username, args.password, args.host, args.port)

        if token:
            logger.info("Successfully authenticated with the API")
        else:
            logger.warning("Failed to authenticate with the API")
            if args.test in ["conversation", "config", "flow"]:
                logger.error("Cannot continue with conversation tests without authentication")
                return

    if args.test in ["conversation", "all"] and token:
        # Create a test conversation
        conversation = await test_create_conversation(token, f"Test Conversation {uuid.uuid4()}", args.host, args.port)
        if conversation:
            conversation_id = conversation.get("conversation_id")

            # List conversations
            await test_list_conversations(token, args.host, args.port)

            # Add a message
            await test_add_message(token, conversation_id, "Hello, this is a test message", args.host, args.port)

            # Get conversation details
            await test_get_conversation(token, conversation_id, args.host, args.port)

            # Update conversation
            await test_update_conversation(token, conversation_id, f"Updated Title {uuid.uuid4()}", args.host, args.port)

            # Use LLM with conversation
            await test_llm_with_conversation(token, conversation_id, "Tell me about the Solo project", args.host, args.port)

            # Clean up - delete conversation
            await test_delete_conversation(token, conversation_id, args.host, args.port)

    if args.test in ["config", "all"] and token:
        await test_get_config(token, args.host, args.port)
        await test_user_profile(token, args.host, args.port)
        await test_user_preferences(token, args.host, args.port)

    if args.test in ["flow", "all"] and token:
        await test_conversation_flow(args.host, args.port)

    logger.info("API testing complete")

if __name__ == "__main__":
    asyncio.run(main())
