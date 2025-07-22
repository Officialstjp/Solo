"""
Module Name: test_api_performance.py
Purpose   : Performance tests for API endpoints
Params    : None
History   :
    Date          Notes
    07.21.2025    Initial version
"""

import pytest
import time
from locust import HttpUser, task, between

# ===== functions =====

# Locust load testing class
class SoloAPIUser(HttpUser):
    """Locust user for load testing the Solo API."""

    wait_time = between(1, 3)  # Wait between 1-3 seconds between tasks

    def on_start(self):
        """Setup before starting tests."""
        # Login to get a token
        response = self.client.post(
            "/auth/login",
            json={
                "username": "testuser",
                "password": "securepassword123"
            }
        )
        if response.status_code == 200:
            token = response.json()["access_token"]
            self.client.headers = {"Authorization": f"Bearer {token}"}

    @task(1)
    def get_models(self):
        """Test the models endpoint."""
        self.client.get("/models/list")

    @task(2)
    def get_conversations(self):
        """Test the conversations endpoint."""
        self.client.get("/conversations")

    @task(3)
    def create_message(self):
        """Test creating a message."""
        # First get a conversation
        conversations = self.client.get("/conversations").json()
        if conversations:
            conversation_id = conversations[0]["id"]
            self.client.post(
                f"/conversations/{conversation_id}/messages",
                json={"content": "Hello, how are you?"}
            )


# PyTest benchmark tests
@pytest.mark.benchmark
def test_health_endpoint_performance(benchmark, client):
    """Benchmark the health endpoint."""
    def run_request():
        return client.get("/health")

    # Run the benchmark
    response = benchmark(run_request)

    # Assert that the response is OK
    assert response.status_code == 200


@pytest.mark.benchmark
def test_models_endpoint_performance(benchmark, client):
    """Benchmark the models endpoint."""
    def run_request():
        return client.get("/models/list")

    # Run the benchmark
    response = benchmark(run_request)

    # Assert that the response is OK
    assert response.status_code == 200
