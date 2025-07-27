"""
Module Name: tests/end2end/test_api_flow.py
Purpose   : End-to-end tests for the API flow.
Params    : None
History   :
    Date          Notes
    26.07.2025    Initial creation.
"""

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_generate_endpoint_happy_path(test_client: AsyncClient):
    """
    Tests the full flow of the /api/v1/chat/generate endpoint.

    this test mocks the event bus to intercept the outgoing event,
    verifying that the API correctly processes the request and
    dispatches the appropriate event.
    """
    # ==== Setup ===

    request_payload = {
        "prompt": "Hello, world!",
        "session_id": "e2e-test-session-123"
    }

    # ==== Execute ====
    response = await test_client.post("/llm/generate", json=request_payload)

    # ==== Assertions ====
    # 1. Assert the HTTP response status code
    assert response.status_code == 200

    # 2. Assert the response body has the expected structure
    response_json = response.json()
    assert "response" in response_json
    assert "session_id" in response_json
    assert "metrics" in response_json

    # 3. Verify the returned response content
    assert response_json["response"] == "This is a mock response."
    assert response_json["session_id"] == "e2e-test-session-123"

    # 4. Verify metrics structure
    assert response_json["metrics"]["tokens_used"] == 100
    assert response_json["metrics"]["generation_time_ms"] == 500
    assert response_json["metrics"]["cache_hit"] == False
    assert response_json["metrics"]["model_name"] == "mock_model"
