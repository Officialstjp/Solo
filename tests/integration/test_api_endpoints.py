"""
Module Name: test_api_endpoints.py
Purpose   : Integration tests for API endpoints
Params    : None
History   :
    Date          Notes
    07.21.2025    Initial version
"""

import pytest
from fastapi import status

# ===== functions =====

@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Test that the health endpoint returns a 200 status code."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_models_list_endpoint(client, model_manager):
    """Test that the models list endpoint returns a list of models."""
    response = client.get("/models/list")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_unauthorized_access(client):
    """Test that unauthorized access is properly rejected."""
    # Try to access a protected endpoint without authentication
    response = client.get("/conversations")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_authenticated_access(authenticated_client):
    """Test that authenticated access works correctly."""
    # Access a protected endpoint with authentication
    response = authenticated_client.get("/conversations")
    assert response.status_code == status.HTTP_200_OK
