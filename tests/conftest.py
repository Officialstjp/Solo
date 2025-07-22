"""
Module Name: conftest.py
Purpose   : Common test fixtures for all test categories
Params    : None
History   :
    Date          Notes
    07.21.2025    Initial version
"""

import os
import pytest
import asyncio
import shutil
from typing import AsyncGenerator, Dict, Any, List

# ===== helper functions =====

async def reset_test_database(db_service):
    """Reset the test database by truncating all tables."""
    try:
        # Get all tables except for migrations and system tables
        query = """
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        AND tablename NOT LIKE 'pg_%'
        AND tablename NOT LIKE 'sql_%';
        """
        result = await db_service.fetch_all(query)
        tables = [row['tablename'] for row in result]

        if tables:
            # Disable foreign key constraints temporarily
            await db_service.execute_query("SET session_replication_role = 'replica';")

            # Truncate all tables in a single transaction
            for table in tables:
                await db_service.execute_query(f'TRUNCATE TABLE "{table}" CASCADE;')

            # Re-enable foreign key constraints
            await db_service.execute_query("SET session_replication_role = 'origin';")
    except Exception as e:
        pytest.fail(f"Failed to reset test database: {str(e)}")

def clean_test_files(directory: str):
    """Clean up test files created during tests."""
    if os.path.exists(directory) and os.path.isdir(directory):
        try:
            for item in os.listdir(directory):
                if item.startswith('test_') and not item == 'test_model.gguf':
                    path = os.path.join(directory, item)
                    if os.path.isfile(path):
                        os.remove(path)
                    elif os.path.isdir(path):
                        shutil.rmtree(path)
        except Exception as e:
            pytest.fail(f"Failed to clean test files: {str(e)}")

# ===== fixtures ====

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def app():
    """Create a test FastAPI application."""
    from app.api.factory import create_app
    app = create_app()
    yield app


@pytest.fixture
async def client(app):
    """Create a test client for the FastAPI application."""
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        yield client


@pytest.fixture
async def db_service():
    """Create a test database service with a temporary test database."""
    from app.core.db_service import DatabaseService

    # Use environment variables with test database credentials
    db_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5433/test_solo"
    )

    db_service = DatabaseService(db_url)
    await db_service.initialize()

    # Setup - ensure tables are created
    await db_service.execute_query("SELECT 1")

    # Reset database to clean state before test
    await reset_test_database(db_service)

    yield db_service

    # Cleanup after tests
    await reset_test_database(db_service)
    await db_service.close()

@pytest.fixture
async def model_manager():
    """Create a test model manager with a temporary models directory."""
    from app.core.model_manager import ModelManager

    # Use a test models directory
    models_dir = os.environ.get("TEST_MODELS_DIR", "tests/fixtures/models")

    # Create the test models directory if it doesn't exist
    os.makedirs(models_dir, exist_ok=True)

    # Clean any previous test files
    clean_test_files(models_dir)

    model_manager = ModelManager(models_dir=models_dir)
    await model_manager.initialize()

    yield model_manager

    # Clean up after tests
    await model_manager.close()
    clean_test_files(models_dir)


@pytest.fixture
async def llm_runner(model_manager):
    """Create a test LLM runner with the test model manager."""
    from app.core.llm_runner import LLMRunner

    llm_runner = LLMRunner(model_manager=model_manager)
    await llm_runner.initialize()

    yield llm_runner

    await llm_runner.close()


@pytest.fixture
def test_user_data() -> Dict[str, Any]:
    """Return test user data."""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "securepassword123"
    }


@pytest.fixture
async def authenticated_client(client, test_user_data):
    """Return an authenticated client."""
    # First create a user
    response = client.post(
        "/auth/register",
        json=test_user_data
    )
    assert response.status_code == 201

    # Then login
    response = client.post(
        "/auth/login",
        data={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        }
    )
    assert response.status_code == 200
    token_data = response.json()

    # Create a client with authentication headers
    client.headers = {
        "Authorization": f"Bearer {token_data['access_token']}"
    }

    return client
