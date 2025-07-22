# Solo Testing Framework

This document provides an overview of the Solo testing framework and instructions on how to use it.

## Testing Structure

The testing framework is organized as follows:

```
tests/
├─ unit/                  # Unit tests
│  ├─ test_model_manager.py
│  ├─ test_events.py
│  └─ ...
├─ integration/           # Integration tests
│  ├─ test_api_endpoints.py
│  ├─ test_db_services.py
│  └─ ...
├─ e2e/                   # End-to-end tests
│  └─ ...
├─ performance/           # Performance tests
│  ├─ test_llm_performance.py
│  ├─ test_api_performance.py
│  └─ ...
├─ security/              # Security tests
│  ├─ test_authentication_security.py
│  └─ ...
├─ fixtures/              # Test fixtures
│  └─ models/             # Test model files
├─ conftest.py            # Shared test configuration and fixtures
└─ run_tests.py           # Test runner script
```

## Setup

Before running tests for the first time, you need to set up the test environment:

1. Install required test dependencies:

```powershell
poetry add pytest pytest-asyncio pytest-cov pytest-httpserver pytest-benchmark testcontainers psutil locust bandit --group dev
```

2. Run the test environment setup script:

```powershell
.\scripts\setup\setup-test-env.ps1
```

This script will:
- Verify all required test dependencies are installed
- Set up a test database container using Docker
- Create necessary test fixtures
- Set up the `.env.test` file with test environment variables

## Running Tests

You can run tests using the provided test runner script:

```powershell
# Run all tests
poetry run python -m tests.run_tests

# Run only unit tests
poetry run python -m tests.run_tests --unit

# Run integration tests
poetry run python -m tests.run_tests --integration

# Run tests with coverage
poetry run python -m tests.run_tests --coverage

# Run tests with coverage and generate HTML report
poetry run python -m tests.run_tests --coverage --html

# Run specific tests with verbosity
poetry run python -m tests.run_tests --unit --verbose
```

Alternatively, you can use pytest directly:

```powershell
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app

# Run with specific markers
poetry run pytest -m "not slow"
```

## Security Testing

You can run security tests using Bandit:

```powershell
# Run bandit with default settings
poetry run bandit -r app/

# Run bandit with configured settings
poetry run bandit -r app/ -ll
```

The `.bandit` configuration file specifies rules for security testing.

## Performance Testing

### Benchmark Tests

Run benchmark tests using pytest-benchmark:

```powershell
# Run all benchmark tests
poetry run pytest tests/performance/ -v

# Run specific benchmark tests
poetry run pytest tests/performance/test_llm_performance.py -v
```

### Load Testing with Locust

For load testing API endpoints:

1. Start the application in one terminal:

```powershell
poetry run python -m app.main
```

2. Start Locust in another terminal:

```powershell
# Start Locust with the Solo API User class
poetry run locust -f tests/performance/test_api_performance.py SoloAPIUser

# Open http://localhost:8089 in your browser to access the Locust web UI
```

## Test Coverage

To generate a test coverage report:

```powershell
# Generate coverage report
poetry run python -m tests.run_tests --coverage --html

# Open the HTML report
start htmlcov/index.html
```

## Continuous Integration

The tests are automatically run in CI pipeline as defined in `.github/workflows/ci.yml`. The CI pipeline:

1. Runs all tests
2. Checks test coverage (fails if below 80%)
3. Runs security tests (fails on medium or higher severity issues)

## Writing New Tests

When writing new tests:

1. Follow the existing structure
2. Use appropriate fixtures from `conftest.py`
3. Add necessary new fixtures in the appropriate test files
4. Follow the naming convention: `test_*.py` for files and `test_*` for functions
5. Add docstrings and comments to explain test purpose and behavior

## Testing Modules

### Unit Tests

Unit tests focus on testing individual components in isolation, with dependencies mocked.

### Integration Tests

Integration tests verify that components work together correctly, using actual implementations instead of mocks.

### End-to-End Tests

End-to-end tests validate complete user scenarios, testing the entire application stack.

### Performance Tests

Performance tests ensure the system meets performance requirements.

### Security Tests

Security tests verify that the system is secure against common vulnerabilities.
