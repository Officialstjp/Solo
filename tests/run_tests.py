# ===== Test Runner Script =====
#
# Run this script to execute all tests in the project
# Usage: python -m tests.run_tests [options]
#
# Options:
#   --unit         Run only unit tests
#   --integration  Run only integration tests
#   --e2e          Run only end-to-end tests
#   --performance  Run only performance tests
#   --security     Run only security tests
#   --coverage     Run tests with coverage
#   --html         Generate HTML report (with --coverage)
#   --verbose      Run tests in verbose mode
#
# Examples:
#   python -m tests.run_tests                  # Run all tests
#   python -m tests.run_tests --unit           # Run only unit tests
#   python -m tests.run_tests --coverage       # Run all tests with coverage
#   python -m tests.run_tests --unit --coverage --html  # Run unit tests with coverage and HTML report

import sys
import os
import argparse
import pytest

def main():
    """Main function to run tests."""
    parser = argparse.ArgumentParser(description="Run tests for the Solo project")
    parser.add_argument("--unit", action="store_true", help="Run only unit tests")
    parser.add_argument("--integration", action="store_true", help="Run only integration tests")
    parser.add_argument("--e2e", action="store_true", help="Run only end-to-end tests")
    parser.add_argument("--performance", action="store_true", help="Run only performance tests")
    parser.add_argument("--security", action="store_true", help="Run only security tests")
    parser.add_argument("--coverage", action="store_true", help="Run tests with coverage")
    parser.add_argument("--html", action="store_true", help="Generate HTML coverage report")
    parser.add_argument("--verbose", action="store_true", help="Run tests in verbose mode")

    args = parser.parse_args()

    # Determine which tests to run
    test_paths = []
    if args.unit:
        test_paths.append("tests/unit")
    if args.integration:
        test_paths.append("tests/integration")
    if args.e2e:
        test_paths.append("tests/e2e")
    if args.performance:
        test_paths.append("tests/performance")
    if args.security:
        test_paths.append("tests/security")

    # If no specific test type is specified, run all tests
    if not test_paths:
        test_paths = ["tests"]

    # Build the pytest arguments
    pytest_args = []

    # Add verbosity if specified
    if args.verbose:
        pytest_args.append("-v")

    # Add coverage if specified
    if args.coverage:
        pytest_args.extend(["--cov=app", "--cov-report=term"])
        if args.html:
            pytest_args.append("--cov-report=html")

    # Add the test paths
    pytest_args.extend(test_paths)

    # Run the tests
    print(f"Running tests with args: {pytest_args}")
    sys.exit(pytest.main(pytest_args))

if __name__ == "__main__":
    main()
