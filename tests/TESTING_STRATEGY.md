# Solo Testing Strategy

This document outlines the comprehensive testing strategy for the Solo project, including API testing, database testing, and general application testing.

## 1. Testing Philosophy

The Solo testing strategy follows these key principles:

1. **Test Pyramid Approach**: Prioritize unit tests (fast, focused) over integration tests (slower, broader), with a small number of end-to-end tests.
2. **Test Isolation**: Each test should be independent, with no side effects that could affect other tests.
3. **Realistic Testing**: Tests should use realistic data and scenarios to validate actual use cases.
4. **Automation First**: Favor automated tests over manual verification whenever possible.
5. **Continuous Testing**: Tests should be run automatically on every code change.

## 2. Testing Categories

### 2.1 Unit Tests

Unit tests focus on testing individual components in isolation:

- **Core Logic Tests**: Test individual functions and methods with mocked dependencies.
- **Model Management Tests**: Verify model detection, metadata extraction, and selection.
- **Event System Tests**: Ensure events are properly emitted and received.
- **Prompt Template Tests**: Validate template formatting for different model families.

### 2.2 Integration Tests

Integration tests verify that components work together correctly:

- **API Endpoint Tests**: Verify that API endpoints return expected responses.
- **Database Service Tests**: Test database operations with actual database connections.
- **LLM Integration Tests**: Verify that the LLM runner works with the model manager.
- **Authentication Flow Tests**: Test the complete authentication process.

### 2.3 End-to-End Tests

End-to-end tests validate complete user scenarios:

- **Conversation Flow Tests**: Test the complete conversation flow from user input to response.
- **User Management Tests**: Test user registration, login, and profile management.
- **Model Selection Tests**: Test model selection and switching.
- **Security Tests**: Verify that authentication and authorization work as expected.

### 2.4 Performance Tests

Performance tests ensure the system meets performance requirements:

- **LLM Response Time Tests**: Measure the time it takes to generate responses.
- **Database Query Performance Tests**: Verify database query performance.
- **API Response Time Tests**: Measure API endpoint response times.
- **Concurrency Tests**: Test system behavior under concurrent load.

### 2.5 Security Tests

Security tests verify that the system is secure:

- **Authentication Tests**: Verify that authentication mechanisms work correctly.
- **Authorization Tests**: Ensure users can only access authorized resources.
- **Input Validation Tests**: Test handling of invalid or malicious input.
- **Rate Limiting Tests**: Verify that rate limiting protects against abuse.

## 3. Testing Tools

### 3.1 Unit and Integration Testing

- **pytest**: Primary testing framework for Python code.
- **unittest.mock**: For mocking dependencies in unit tests.
- **pytest-asyncio**: For testing asynchronous code.
- **pytest-cov**: For measuring test coverage.

### 3.2 API Testing

- **pytest with httpx**: For testing API endpoints.
- **requests**: For making HTTP requests in test scripts.
- **pytest-httpserver**: For mocking external HTTP services.
- **Postman/Newman**: For API test collections and automated test runs.

### 3.3 Database Testing

- **pytest-postgresql**: For testing with temporary PostgreSQL databases.
- **pytest with SQLAlchemy**: For testing database operations.
- **testcontainers**: For running isolated database containers in tests.

### 3.4 Performance Testing

- **locust**: For load testing API endpoints.
- **pytest-benchmark**: For benchmarking function performance.
- **psutil**: For monitoring system resource usage during tests.

### 3.5 Security Testing

- **bandit**: For static security analysis.
- **OWASP ZAP**: For dynamic security testing.
- **JWT testing tools**: For testing JWT authentication.

## 4. Test Implementation

### 4.1 Directory Structure

```
tests/
├─ unit/                  # Unit tests
│  ├─ test_model_manager.py
│  ├─ test_prompt_templates.py
│  ├─ test_events.py
│  └─ ...
├─ integration/           # Integration tests
│  ├─ test_api_endpoints.py
│  ├─ test_db_services.py
│  ├─ test_authentication.py
│  └─ ...
├─ e2e/                   # End-to-end tests
│  ├─ test_conversation_flow.py
│  ├─ test_user_management.py
│  └─ ...
├─ performance/           # Performance tests
│  ├─ test_llm_performance.py
│  ├─ test_api_performance.py
│  └─ ...
├─ security/              # Security tests
│  ├─ test_authentication_security.py
│  ├─ test_input_validation.py
│  └─ ...
├─ fixtures/              # Test fixtures
│  ├─ db_fixtures.py
│  ├─ api_fixtures.py
│  └─ ...
└─ conftest.py            # Shared test configuration
```

### 4.2 Test Fixtures

Define reusable test fixtures in `conftest.py`:

```python
# Example fixtures
@pytest.fixture
async def app():
    """Create a test FastAPI application."""
    from app.api.factory import create_app
    return create_app(db_service=None)

@pytest.fixture
async def client(app):
    """Create a test client for the FastAPI application."""
    from fastapi.testclient import TestClient
    return TestClient(app)

@pytest.fixture
async def db_service():
    """Create a test database service."""
    from app.core.db_service import DatabaseService
    return DatabaseService(connection_string="postgresql://test:test@localhost:5432/test_db")

@pytest.fixture
async def model_manager():
    """Create a test model manager."""
    from app.core.model_manager import ModelManager
    return ModelManager(models_dir="tests/fixtures/models")
```

### 4.3 API Testing

Use `httpx` and `FastAPI.TestClient` for API testing:

```python
# Example API test
async def test_models_endpoint(client):
    """Test the models endpoint."""
    response = client.get("/models/list")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    for model in data:
        assert "name" in model
        assert "parameter_size" in model
        assert "quantization" in model
```

### 4.4 Database Testing

Use `pytest-postgresql` for database testing:

```python
# Example database test
async def test_user_creation(db_service):
    """Test user creation in the database."""
    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "securepassword123"
    }
    user = await db_service.users.create_user(UserCreate(**user_data))
    assert user.username == user_data["username"]
    assert user.email == user_data["email"]

    # Verify the user was created
    retrieved_user = await db_service.users.get_user_by_username(user_data["username"])
    assert retrieved_user is not None
    assert retrieved_user.username == user_data["username"]
```

### 4.5 End-to-End Testing

Test complete user flows:

```python
# Example end-to-end test
async def test_conversation_flow(client):
    """Test the complete conversation flow."""
    # Login
    login_response = client.post(
        "/auth/login",
        json={"username": "testuser", "password": "securepassword123"}
    )
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data

    # Create a conversation
    headers = {"Authorization": f"Bearer {token_data['access_token']}"}
    conversation_response = client.post(
        "/conversations",
        json={"title": "Test Conversation"},
        headers=headers
    )
    assert conversation_response.status_code == 201
    conversation_data = conversation_response.json()
    assert "conversation_id" in conversation_data

    # Send a message
    message_response = client.post(
        f"/conversations/{conversation_data['conversation_id']}/messages",
        json={"content": "Hello, how are you?", "role": "user"},
        headers=headers
    )
    assert message_response.status_code == 201

    # Generate a response
    llm_response = client.post(
        "/llm/generate",
        json={
            "prompt": "Hello, how are you?",
            "conversation_id": conversation_data["conversation_id"]
        },
        headers=headers
    )
    assert llm_response.status_code == 200
    response_data = llm_response.json()
    assert "response" in response_data
    assert response_data["conversation_id"] == conversation_data["conversation_id"]
```

## 5. Test Automation

### 5.1 Continuous Integration

Configure GitHub Actions to run tests automatically:

```yaml
# .github/workflows/tests.yml
name: Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test_db
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-asyncio pytest-postgresql

    - name: Run tests
      run: |
        pytest --cov=app tests/

    - name: Upload coverage reports
      uses: codecov/codecov-action@v3
```

### 5.2 Pre-commit Hooks

Configure pre-commit hooks to run tests before committing:

```yaml
# .pre-commit-config.yaml
repos:
-   repo: local
    hooks:
    -   id: pytest-check
        name: pytest-check
        entry: pytest --cov=app tests/unit/
        language: system
        pass_filenames: false
        always_run: true
```

### 5.3 Test Coverage

Use `pytest-cov` to measure test coverage:

```bash
pytest --cov=app --cov-report=xml --cov-report=html tests/
```

Configure coverage thresholds in `pytest.ini`:

```ini
[pytest]
minversion = 7.0
testpaths = tests
python_files = test_*.py
addopts = --cov=app --cov-report=term-missing --cov-fail-under=80
```

## 6. Testing Specific Components

### 6.1 API Testing

Test the API endpoints with realistic scenarios:

```python
# Test creating a user
async def test_user_registration(client):
    """Test user registration endpoint."""
    user_data = {
        "username": f"testuser_{random.randint(1000, 9999)}",
        "email": f"test{random.randint(1000, 9999)}@example.com",
        "password": "SecurePassword123!",
        "full_name": "Test User"
    }
    response = client.post("/auth/register", json=user_data)
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == user_data["username"]
    assert data["email"] == user_data["email"]
    assert "user_id" in data
```

### 6.2 LLM Testing

Test LLM functionality with smaller models for speed:

```python
# Test LLM generation
async def test_llm_generation(client, test_model):
    """Test LLM generation endpoint."""
    prompt = "Tell me a joke about programming"
    response = client.post(
        "/llm/generate",
        json={
            "prompt": prompt,
            "parameters": {
                "model_id": test_model.model_id,
                "max_tokens": 100,
                "temperature": 0.7
            }
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert len(data["response"]) > 0
    assert "metrics" in data
    assert data["metrics"]["tokens_used"] > 0
```

### 6.3 Database Testing

Test database operations with transaction rollback:

```python
# Test with transaction rollback
@pytest.mark.asyncio
async def test_conversation_crud(db_service):
    """Test conversation CRUD operations."""
    # Create a test user
    user = await db_service.users.create_user(
        UserCreate(
            username="conversation_test_user",
            email="conversation_test@example.com",
            password="SecurePassword123!"
        )
    )

    # Create a conversation
    conversation = await db_service.users.create_conversation(
        ConversationCreate(
            title="Test Conversation",
            user_id=user.user_id
        )
    )
    assert conversation.title == "Test Conversation"
    assert conversation.user_id == user.user_id

    # Get the conversation
    retrieved = await db_service.users.get_conversation(conversation.conversation_id)
    assert retrieved is not None
    assert retrieved.conversation_id == conversation.conversation_id

    # Update the conversation
    updated = await db_service.users.update_conversation(
        conversation.conversation_id,
        {"title": "Updated Title"}
    )
    assert updated.title == "Updated Title"

    # Delete the conversation
    result = await db_service.users.delete_conversation(conversation.conversation_id)
    assert result is True

    # Verify it's gone
    deleted = await db_service.users.get_conversation(conversation.conversation_id)
    assert deleted is None
```

## 7. Performance Testing

### 7.1 LLM Performance

Measure LLM performance metrics:

```python
# Test LLM performance
@pytest.mark.benchmark
async def test_llm_performance(benchmark, llm_runner, test_model):
    """Benchmark LLM generation performance."""
    prompt = "Explain quantum computing in simple terms"

    def generate():
        return llm_runner.generate(
            prompt=prompt,
            model_id=test_model.model_id,
            max_tokens=100
        )

    result = benchmark(generate)
    assert result is not None
    assert len(result.response) > 0
    assert result.metrics.tokens_per_second > 0
```

### 7.2 API Performance

Measure API response times:

```python
# Test API performance
@pytest.mark.benchmark
async def test_api_performance(benchmark, client):
    """Benchmark API performance."""
    def get_models():
        return client.get("/models/list")

    result = benchmark(get_models)
    assert result.status_code == 200
    assert len(result.json()) > 0
```

## 8. Security Testing

### 8.1 Authentication Testing

Test authentication security:

```python
# Test authentication security
async def test_auth_security(client):
    """Test authentication security features."""
    # Test invalid credentials
    response = client.post(
        "/auth/login",
        json={"username": "invalid", "password": "invalid"}
    )
    assert response.status_code == 401

    # Test rate limiting
    for _ in range(10):
        client.post(
            "/auth/login",
            json={"username": "invalid", "password": "invalid"}
        )

    response = client.post(
        "/auth/login",
        json={"username": "invalid", "password": "invalid"}
    )
    assert response.status_code == 429  # Too many requests

    # Test accessing protected endpoint without token
    response = client.get("/users/profile")
    assert response.status_code == 401

    # Test with invalid token
    response = client.get(
        "/users/profile",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401
```

### 8.2 Input Validation Testing

Test input validation security:

```python
# Test input validation
async def test_input_validation(client):
    """Test input validation security."""
    # Test SQL injection attempt
    response = client.post(
        "/auth/login",
        json={"username": "'; DROP TABLE users; --", "password": "password"}
    )
    assert response.status_code == 422  # Validation error

    # Test XSS attempt
    response = client.post(
        "/conversations",
        json={"title": "<script>alert('XSS')</script>"},
        headers={"Authorization": "Bearer valid_token"}
    )
    assert response.status_code == 422  # Validation error
```

## 9. Test Reporting

### 9.1 HTML Reports

Generate HTML test reports with pytest-html:

```bash
pytest --html=report.html --self-contained-html
```

### 9.2 JUnit Reports

Generate JUnit XML reports for CI integration:

```bash
pytest --junitxml=junit.xml
```

### 9.3 Coverage Reports

Generate coverage reports:

```bash
pytest --cov=app --cov-report=xml --cov-report=html
```

## 10. Testing Schedule

Implement a regular testing schedule:

1. **Unit Tests**: Run on every commit
2. **Integration Tests**: Run on every pull request
3. **End-to-End Tests**: Run daily and before releases
4. **Performance Tests**: Run weekly
5. **Security Tests**: Run weekly and before releases

## 11. Best Practices

1. **Write Tests First**: Consider test-driven development (TDD) for new features
2. **Keep Tests Simple**: Each test should verify one specific thing
3. **Use Descriptive Names**: Test names should describe what they're testing
4. **Avoid Test Interdependence**: Tests should not depend on other tests
5. **Clean Up After Tests**: Tests should clean up any resources they create
6. **Mock External Dependencies**: Use mocks for external services and APIs
7. **Test Edge Cases**: Include tests for edge cases and error conditions
8. **Document Tests**: Include docstrings that explain what each test is verifying
9. **Maintain Tests**: Update tests when the code changes
10. **Review Test Coverage**: Regularly review and improve test coverage
