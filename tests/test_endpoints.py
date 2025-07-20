"""
Module Name: app/api/test_endpoints.py
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
from pathlib import Path
import http.client
import urllib.parse

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
        "max_tokens": 200,
        "temperature": 0.7
    })

    conn = http.client.HTTPConnection(host, port)
    conn.request("POST", "/llm/generate", data, headers)
    response = conn.getresponse()

    if response.status == 200:
        result = json.loads(response.read().decode())
        logger.info("Generation successful!")
        logger.info("Response: " + result.get("response", "No response in payload"))
        logger.info(f"Tokens: {result.get('tokens_generated', 0)}, " +
                  f"Time: {result.get('generation_time_ms', 0):.2f}ms, " +
                  f"Speed: {result.get('tokens_per_second', 0):.2f} tokens/sec")
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
        return True
    else:
        logger.error(f"Failed to register user: {response.status} {response.reason}")
        logger.error(response.read().decode())
        return False

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

# ===== Main function =====

async def main():
    parser = argparse.ArgumentParser(description="Test API endpoints for Solo application")
    parser.add_argument("--host", default="localhost", help="API host (default: localhost)")
    parser.add_argument("--port", type=int, default=8080, help="API port (default: 8080)")
    parser.add_argument("--prompt", default="Tell me a joke about programming", help="Test prompt for LLM generation")
    parser.add_argument("--test", choices=["models", "llm", "user", "all"], default="all", help="Test to run")
    parser.add_argument("--username", default="testuser", help="Username for user registration/login tests")
    parser.add_argument("--email", default="test@example.com", help="Email for user registration test")
    parser.add_argument("--password", default="Password123!", help="Password for user registration/login tests")

    args = parser.parse_args()

    logger.info(f"Testing API endpoints on {args.host}:{args.port}")

    if args.test in ["models", "all"]:
        await test_models_endpoint(args.host, args.port)

    if args.test in ["llm", "all"]:
        await test_llm_generate(args.prompt, args.host, args.port)

    if args.test in ["user", "all"]:
        # Try user registration
        reg_success = await test_user_registration(args.username, args.email, args.password, args.host, args.port)

        # Try login regardless (might already exist)
        token = await test_user_login(args.username, args.password, args.host, args.port)

        if token:
            logger.info("Successfully authenticated with the API")
        else:
            logger.warning("Failed to authenticate with the API")

    logger.info("API testing complete")

if __name__ == "__main__":
    asyncio.run(main())
