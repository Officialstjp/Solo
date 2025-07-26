"""
Module Name: app/core/db/test_db.py
Purpose   : Test utility for database functionality
Params    : None
History   :
    Date            Notes
    07.20.2025      Created for testing database functionality
"""

import argparse
import asyncio
import json
import os
from datetime import datetime, timedelta

from app.core.db_service import DatabaseService
from app.core.db.users_db import UserCreate
from app.utils.logger import get_logger

logger = get_logger(name="DB_Tester", json_format=False)

# ===== Test functions =====

async def test_database_connection(connection_string=None):
    """Test basic database connection"""
    logger.info("Testing database connection...")

    db_service = DatabaseService(connection_string=connection_string)
    result = await db_service.initialize()

    if result:
        logger.info("Database connection successful!")
        return db_service
    else:
        logger.error("Failed to connect to database")
        return None

async def test_users_db(db_service):
    """Test user database operations"""
    logger.info("Testing user database operations...")

    # Create a test user
    test_username = f"testuser_{int(datetime.now().timestamp())}"
    test_email = f"{test_username}@example.com"
    test_password = "TestPassword123!"

    user_create = UserCreate(
        username=test_username,
        email=test_email,
        password=test_password,
        full_name="Test User",
        preferences={"theme": "dark", "language": "en"}
    )

    logger.info(f"Creating test user: {test_username}")
    user = await db_service.users_db.create_user(user=user_create, password=test_password)

    if user:
        logger.info(f"User created successfully: {user.user_id}")

        # Test fetching user
        fetched_user = await db_service.users_db.get_user_by_username(test_username)
        if fetched_user and fetched_user.username == test_username:
            logger.info("User retrieval successful")
        else:
            logger.error("Failed to retrieve user")

        # Test authentication (via BigBrother)
        auth_result = await db_service.bigBrother.authenticate(
            username=test_username,
            password=test_password,
            ip_address="127.0.0.1",
            user_agent="DB-Tester"
        )

        if auth_result:
            logger.info("Authentication successful")
        else:
            logger.error("Authentication failed")

        return True
    else:
        logger.error("Failed to create user")
        return False

async def test_models_db(db_service):
    """Test models database operations"""
    logger.info("Testing models database operations...")

    # Try to list models
    models = await db_service.models_db.list_models()
    if models:
        logger.info(f"Found {len(models.models)} models in database")
        for model in models.models:
            logger.info(f"  - {model.name} ({model.parameter_size}, {model.quantization})")
    else:
        logger.info("No models found in database")

    # Try to register a test model
    from app.core.db.models_db import ModelCreate
    import uuid

    test_model_id = f"test-model-{uuid.uuid4().hex[:8]}"
    test_model = ModelCreate(
        model_id=test_model_id,
        name=f"Test Model {test_model_id}",
        path="/path/to/test/model.gguf",
        format="gguf",
        parameter_size="7B",
        quantization="Q4_0",
        context_length=4096,
        file_size_mb=4000,
        metadata={"family": "test", "version": "1.0"}
    )

    logger.info(f"Registering test model: {test_model_id}")
    success = await db_service.models_db.register_model(test_model)

    if success:
        logger.info("Model registered successfully")

        # Try to retrieve the model
        model = await db_service.models_db.get_model(test_model_id)
        if model and model.model_id == test_model_id:
            logger.info("Model retrieval successful")
        else:
            logger.error("Failed to retrieve model")

        return True
    else:
        logger.error("Failed to register model")
        return False

async def test_metrics_db(db_service):
    """Test metrics database operations"""
    logger.info("Testing metrics database operations...")

    # Record a test system metric
    system_metric = {
        "cpu_percent": 25.5,
        "memory_percent": 40.2,
        "gpu_percent": 15.3,
        "gpu_temperature": 65.0,
        "vram_percent": 30.1,
        "app_uptime_seconds": 3600
    }

    logger.info("Recording test system metric")
    success = await db_service.metrics_db.record_system_metrics(system_metric)

    if success:
        logger.info("System metric recorded successfully")
    else:
        logger.error("Failed to record system metric")

    # Record a test LLM metric
    llm_metric = {
        "model_id": "test-model-123",
        "session_id": "test-session-456",
        "request_id": "test-request-789",
        "tokens_generated": 150,
        "generation_time_ms": 2500,
        "prompt_tokens": 50,
        "total_tokens": 200,
        "cache_hit": False,
        "parameters": {"temperature": 0.7, "max_tokens": 200}
    }

    logger.info("Recording test LLM metric")
    success = await db_service.metrics_db.record_llm_metrics(llm_metric)

    if success:
        logger.info("LLM metric recorded successfully")
    else:
        logger.error("Failed to record LLM metric")

    return success

# ===== Main function =====

async def main():
    parser = argparse.ArgumentParser(description="Test database functionality for Solo application")
    parser.add_argument("--connection", help="Database connection string (default: from environment)")
    parser.add_argument("--test", choices=["connection", "users", "models", "metrics", "all"], default="all", help="Test to run")

    args = parser.parse_args()

    # Start with connection test
    db_service = await test_database_connection(args.connection)
    if not db_service:
        logger.error("Cannot proceed with other tests due to connection failure")
        return

    try:
        if args.test in ["users", "all"]:
            await test_users_db(db_service)

        if args.test in ["models", "all"]:
            await test_models_db(db_service)

        if args.test in ["metrics", "all"]:
            await test_metrics_db(db_service)
    finally:
        # Clean up
        if db_service:
            await db_service.close()
            logger.info("Database connection closed")

    logger.info("Database testing complete")

if __name__ == "__main__":
    asyncio.run(main())
