"""
Module Name: tests/conftest.py
Purpose   : Pytest configuration and shared fixtures.
Params    : None
History   :
    Date          Notes
    26.07.2025    Initial creation.
"""

from unittest.mock import AsyncMock
import pytest
from httpx import AsyncClient

from app.api.factory import create_app
from app.api.dependencies import get_model_service, get_event_bus, get_db_service

@pytest.fixture(scope="function")
def mock_model_service() -> AsyncMock:
    """A mock for the ModelService."""
    return AsyncMock()

@pytest.fixture(scope="function")
def mock_event_bus() -> AsyncMock:
    """A mock for the EventBus."""
    return AsyncMock()

@pytest.fixture(scope="function")
def mock_db_service() -> AsyncMock:
    """A mock for the DatabaseService."""
    return AsyncMock()

@pytest.fixture(scope="function")
async def test_client():
    """
    Creates a test client for API testing.

    This fixture sets up a FastAPI application instance for testing and
    overrides the real dependencies (like database or model services)
    with mocks. This allows for fast, isolated API tests.
    """
    print("Creating test client")

    # Create proper mocks that can be awaited
    mock_model_service = AsyncMock()
    mock_event_bus = AsyncMock()
    mock_db_service = AsyncMock()

    # Create a mock model manager - list_available_models is NOT async in the real implementation
    mock_model_manager = AsyncMock()

    # Create a class with the expected attributes for model objects
    class MockModel:
        def __init__(self, path):
            self.path = path
            self.name = "mock_model"

    # Create a list of mock models for testing
    mock_models = [MockModel("mock_model_path")]

    # IMPORTANT: list_available_models is not an async method in the real implementation
    # So we need to configure it as a normal method, not a coroutine
    mock_model_manager.list_available_models = lambda: mock_models

    # Configure event_bus.publish to be awaitable
    # In the real implementation, publish takes a type and an event, not just an event
    mock_event_bus.publish = AsyncMock()

    # Create a properly structured metrics object to match llm_endpoint.py expectations
    # Note: cache_misses should be an integer, not a list
    mock_metrics = {
        "total_requests": 0,
        "total_tokens_generated": 0,
        "cache_hits": 0,
        "cache_misses": 0,  # Changed from [] to 0 to match endpoint expectations
        "tokens_per_second": [],
        "response_times": []
    }

    # Set up properly structured response from wait_for_response
    # Creating a class that matches the expected structure
    class MockLLMResponse:
        def __init__(self):
            self.tokens = 100
            self.generation_time = 500
            self.cache_hit = False
            self.model_id = "mock_model"
            self.response = "This is a mock response."

    # Configure wait_for_response to return our mock response
    mock_model_service.wait_for_response.return_value = MockLLMResponse()

    app = create_app(
        db_service=mock_db_service,
        existing_model_service=mock_model_service,
        existing_event_bus=mock_event_bus,
        existing_model_manager=mock_model_manager
    )

    # Override the dependency injection functions with FACTORIES that return our mocks
    # This is crucial - dependency injection expects a callable that returns the dependency
    app.dependency_overrides[get_db_service] = lambda: mock_db_service
    app.dependency_overrides[get_model_service] = lambda: mock_model_service
    app.dependency_overrides[get_event_bus] = lambda: mock_event_bus

    # Add override for metrics as well
    from app.api.dependencies import get_metrics
    app.dependency_overrides[get_metrics] = lambda: mock_metrics

    # yield an async client for the test to use
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    # cleanup: clear the overrides
    app.dependency_overrides.clear()
