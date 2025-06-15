"""
Module Name: app/core/model_cache.py
Purpose   : Caching mechanism for LLM responses
Params    : None
History   :
    Date            Notes
    2025-06-15      Initial implementation
"""

import time
import json
import hashlib
import os
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

class ResponseCache:
    """Cache for LLM responses to avoid repeated computation"""

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        max_entries: int = 1000,
        ttl_seconds: int = 86400,  # 24 hours
        enabled: bool = True
    ):
        """Initialize the response cache

        Args:
            cache_dir: Directory to store cache files (None for in-memory only)
            max_entries: Maximum number of entries to keep in memory
            ttl_seconds: Time-to-live for cache entries in seconds
            enabled: Whether caching is enabled
        """
        self.cache_dir = cache_dir
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled
        self.in_memory_cache: Dict[str, Dict[str, Any]] = {}

    def _compute_key(self, prompt: str, parameters: Dict[str, Any]) -> str:
        """Compute a cache key for a prompt and parameters

        Args:
            prompt: The prompt string
            parameters: Dictionary of generation parameters

        Returns:
            Cache key string
        """
        # Sort parameters to ensure consistent keys
        sorted_params = json.dumps(parameters, sort_keys=True)
        key_string = f"{prompt}|{sorted_params}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def get(self, prompt: str, parameters: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Get a cached response if available

        Args:
            prompt: The prompt string
            parameters: Dictionary of generation parameters

        Returns:
            Tuple of (response, metrics) or None if not cached
        """
        if not self.enabled:
            return None

        key = self._compute_key(prompt, parameters)

        # Check in-memory cache first
        if key in self.in_memory_cache:
            entry = self.in_memory_cache[key]
            # Check if entry is expired
            if time.time() - entry["timestamp"] <= self.ttl_seconds:
                return entry["response"], entry["metrics"]
            else:
                # Remove expired entry
                del self.in_memory_cache[key]

        # Check file cache if enabled
        if self.cache_dir:
            cache_file = os.path.join(self.cache_dir, f"{key}.json")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r') as f:
                        entry = json.load(f)

                    # Check if entry is expired
                    if time.time() - entry["timestamp"] <= self.ttl_seconds:
                        # Add to in-memory cache for faster access next time
                        self.in_memory_cache[key] = entry
                        return entry["response"], entry["metrics"]
                    else:
                        # Remove expired cache file
                        os.remove(cache_file)
                except (json.JSONDecodeError, KeyError, IOError):
                    # Invalid or corrupt cache file, ignore
                    pass

        return None

    def put(self, prompt: str, parameters: Dict[str, Any], response: str, metrics: Dict[str, Any]):
        """Store a response in the cache

        Args:
            prompt: The prompt string
            parameters: Dictionary of generation parameters
            response: The generated response
            metrics: Performance metrics
        """
        if not self.enabled:
            return

        key = self._compute_key(prompt, parameters)

        # Create cache entry
        entry = {
            "prompt": prompt,
            "parameters": parameters,
            "response": response,
            "metrics": metrics,
            "timestamp": time.time()
        }

        # Store in memory
        self.in_memory_cache[key] = entry

        # Enforce max entries limit
        if len(self.in_memory_cache) > self.max_entries:
            # Remove oldest entry
            oldest_key = min(
                self.in_memory_cache.keys(),
                key=lambda k: self.in_memory_cache[k]["timestamp"]
            )
            del self.in_memory_cache[oldest_key]

        # Store to file if enabled
        if self.cache_dir:
            cache_file = os.path.join(self.cache_dir, f"{key}.json")
            try:
                with open(cache_file, 'w') as f:
                    json.dump(entry, f)
            except IOError:
                # Failed to write cache file, ignore
                pass

    def clear(self):
        """Clear the entire cache"""
        self.in_memory_cache = {}

        if self.cache_dir and os.path.exists(self.cache_dir):
            for file in os.listdir(self.cache_dir):
                if file.endswith(".json"):
                    try:
                        os.remove(os.path.join(self.cache_dir, file))
                    except IOError:
                        pass

    def disable(self):
        """Disable caching"""
        self.enabled = False

    def enable(self):
        """Enable caching"""
        self.enabled = True
