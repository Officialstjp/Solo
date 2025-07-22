"""
Module Name: test_llm_performance.py
Purpose   : Performance tests for the LLM
Params    : None
History   :
    Date          Notes
    07.21.2025    Initial version
"""

import pytest
import asyncio
import time
import psutil
import os

# ===== functions =====

@pytest.mark.benchmark
def test_llm_response_time(benchmark, llm_runner):
    """Benchmark the LLM response time."""
    # Define the benchmark function
    def run_llm():
        return asyncio.run(llm_runner.generate_response("Hello, how are you today?"))

    # Run the benchmark
    result = benchmark(run_llm)

    # Assert that the result is not None
    assert result is not None


@pytest.mark.asyncio
async def test_llm_memory_usage(llm_runner):
    """Test the memory usage of the LLM during generation."""
    # Get the current process
    process = psutil.Process(os.getpid())

    # Get the memory usage before generation
    memory_before = process.memory_info().rss / 1024 / 1024  # in MB

    # Generate a response
    start_time = time.time()
    response = await llm_runner.generate_response(
        "Explain the theory of relativity in simple terms."
    )
    end_time = time.time()

    # Get the memory usage after generation
    memory_after = process.memory_info().rss / 1024 / 1024  # in MB

    # Calculate the memory increase
    memory_increase = memory_after - memory_before

    # Calculate the generation time
    generation_time = end_time - start_time

    # Log the results
    print(f"Memory before: {memory_before:.2f} MB")
    print(f"Memory after: {memory_after:.2f} MB")
    print(f"Memory increase: {memory_increase:.2f} MB")
    print(f"Generation time: {generation_time:.2f} seconds")

    # Assert that the response was generated
    assert response is not None

    # No strict assertions on memory usage, as it depends on the model size
    # This test is mainly for logging and manual review
