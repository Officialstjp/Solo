# Python Database Integration Examples

This document provides code examples for integrating the Solo application with PostgreSQL.

## Basic Connection Setup

```python
"""
Module Name: db_connector.py
Purpose   : Establishes and manages database connections for the Solo application
Params    : None
History   :
    Date          Notes
    07.05.2025    Initial implementation
"""

import os
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager

# Database connection parameters
DB_PARAMS = {
    'dbname': os.environ.get('POSTGRES_DB', 'solo'),
    'user': os.environ.get('POSTGRES_USER', 'solo_app'),
    'password': os.environ.get('POSTGRES_PASSWORD', 'changeme'),
    'host': os.environ.get('POSTGRES_HOST', 'localhost'),
    'port': os.environ.get('POSTGRES_PORT', '5432')
}

# Create a connection pool
min_conn = 1
max_conn = 10
connection_pool = ThreadedConnectionPool(
    min_conn,
    max_conn,
    **DB_PARAMS
)

@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    Automatically returns connections to the pool after use.
    """
    connection = None
    try:
        connection = connection_pool.getconn()
        yield connection
    finally:
        if connection:
            connection_pool.putconn(connection)

@contextmanager
def get_db_cursor(commit=False):
    """
    Context manager for database cursors.
    Automatically commits and closes cursors after use.
    """
    with get_db_connection() as connection:
        cursor = connection.cursor()
        try:
            yield cursor
            if commit:
                connection.commit()
        finally:
            cursor.close()
```

## Metrics Logging Functions

```python
"""
Module Name: metrics_logger.py
Purpose   : Logs metrics data to PostgreSQL database
Params    : None
History   :
    Date          Notes
    07.05.2025    Initial implementation
"""

from app.utils.db_connector import get_db_cursor
import json
import uuid

def log_llm_call(model_id, prompt_tokens, completion_tokens, latency_ms, user_id=None, session_id=None):
    """
    Log LLM call metrics to the database.

    Args:
        model_id (str): Identifier of the model used
        prompt_tokens (int): Number of tokens in the prompt
        completion_tokens (int): Number of tokens in the completion
        latency_ms (int): Latency in milliseconds
        user_id (str, optional): User identifier
        session_id (str, optional): Session identifier
    """
    total_tokens = prompt_tokens + completion_tokens
    request_id = str(uuid.uuid4())

    with get_db_cursor(commit=True) as cursor:
        cursor.execute("""
            INSERT INTO metrics.llm_calls
            (model_id, prompt_tokens, completion_tokens, total_tokens, latency_ms, request_id, user_id, session_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (model_id, prompt_tokens, completion_tokens, total_tokens, latency_ms, request_id, user_id, session_id))

    return request_id

def log_cache_hit(cache_key, model_id, user_id=None):
    """
    Log a cache hit to the database.

    Args:
        cache_key (str): The cache key that was hit
        model_id (str): Model identifier
        user_id (str, optional): User identifier
    """
    with get_db_cursor(commit=True) as cursor:
        cursor.execute("""
            INSERT INTO metrics.cache_hits
            (cache_key, model_id, user_id)
            VALUES (%s, %s, %s)
        """, (cache_key, model_id, user_id))
```

## Model Management Functions

```python
"""
Module Name: model_registry.py
Purpose   : Manages model registrations and lookups
Params    : None
History   :
    Date          Notes
    07.05.2025    Initial implementation
"""

from app.utils.db_connector import get_db_cursor
import json

def register_model(model_id, display_name, model_type, file_path, parameters, context_length, metadata=None):
    """
    Register a new model in the database.

    Args:
        model_id (str): Unique identifier for the model
        display_name (str): Human-readable name
        model_type (str): Type of model (e.g., 'llama.cpp')
        file_path (str): Path to the model file
        parameters (int): Number of parameters
        context_length (int): Maximum context length
        metadata (dict, optional): Additional metadata as JSON

    Returns:
        int: ID of the newly registered model
    """
    with get_db_cursor(commit=True) as cursor:
        cursor.execute("""
            INSERT INTO models.model_registry
            (model_id, display_name, model_type, file_path, parameters, context_length, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (model_id, display_name, model_type, file_path, parameters, context_length,
              json.dumps(metadata) if metadata else None))
        return cursor.fetchone()[0]

def get_available_models(active_only=True):
    """
    Get a list of available models.

    Args:
        active_only (bool): Whether to return only active models

    Returns:
        list: List of model dictionaries
    """
    with get_db_cursor() as cursor:
        query = """
            SELECT
                id, model_id, display_name, model_type, file_path,
                parameters, context_length, active, created_at, updated_at, metadata
            FROM models.model_registry
        """

        if active_only:
            query += " WHERE active = TRUE"

        query += " ORDER BY parameters DESC, display_name"

        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
```

## User Data Functions

```python
"""
Module Name: user_data.py
Purpose   : Manages user profiles and conversation history
Params    : None
History   :
    Date          Notes
    07.05.2025    Initial implementation
"""

from app.utils.db_connector import get_db_cursor
import json
import uuid

def create_user_profile(username, preferences=None):
    """
    Create a new user profile.

    Args:
        username (str): Username
        preferences (dict, optional): User preferences

    Returns:
        str: Unique user ID
    """
    user_id = str(uuid.uuid4())

    with get_db_cursor(commit=True) as cursor:
        cursor.execute("""
            INSERT INTO users.user_profiles
            (user_id, username, preferences)
            VALUES (%s, %s, %s)
        """, (user_id, username, json.dumps(preferences) if preferences else None))

    return user_id

def start_conversation(user_id, title=None):
    """
    Start a new conversation.

    Args:
        user_id (str): User ID
        title (str, optional): Conversation title

    Returns:
        str: Unique conversation ID
    """
    conversation_id = str(uuid.uuid4())

    with get_db_cursor(commit=True) as cursor:
        cursor.execute("""
            INSERT INTO users.conversations
            (conversation_id, user_id, title)
            VALUES (%s, %s, %s)
        """, (conversation_id, user_id, title))

    return conversation_id

def save_message(conversation_id, user_id, role, content, metadata=None):
    """
    Save a message in a conversation.

    Args:
        conversation_id (str): Conversation ID
        user_id (str): User ID
        role (str): Message role ('user', 'assistant', or 'system')
        content (str): Message content
        metadata (dict, optional): Additional metadata

    Returns:
        str: Unique message ID
    """
    message_id = str(uuid.uuid4())

    with get_db_cursor(commit=True) as cursor:
        cursor.execute("""
            INSERT INTO users.messages
            (message_id, conversation_id, user_id, role, content, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (message_id, conversation_id, user_id, role, content,
              json.dumps(metadata) if metadata else None))

    return message_id

def get_conversation_history(conversation_id):
    """
    Get the full history of a conversation.

    Args:
        conversation_id (str): Conversation ID

    Returns:
        list: List of message dictionaries
    """
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT
                message_id, role, content, timestamp, metadata
            FROM users.messages
            WHERE conversation_id = %s
            ORDER BY timestamp
        """, (conversation_id,))

        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
```

## Integration with Solo Components

### Integration with Model Cache

```python
"""
Module Name: model_cache.py
Purpose   : Caches LLM responses with database tracking
Params    : None
History   :
    Date          Notes
    07.05.2025    Enhanced with database tracking
"""

from app.utils.metrics_logger import log_cache_hit
import hashlib
import json
import os

class ResponseCache:
    def __init__(self, cache_dir="./cache/llm_responses"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _get_cache_key(self, model_id, prompt, params):
        """Generate a unique cache key based on model, prompt and parameters"""
        hash_input = f"{model_id}|{prompt}|{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(hash_input.encode()).hexdigest()

    def get(self, model_id, prompt, params, user_id=None):
        """Get response from cache if it exists"""
        cache_key = self._get_cache_key(model_id, prompt, params)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cached_response = json.load(f)

            # Log the cache hit to the database
            log_cache_hit(cache_key, model_id, user_id)

            return cached_response

        return None

    def put(self, model_id, prompt, params, response):
        """Store response in cache"""
        cache_key = self._get_cache_key(model_id, prompt, params)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        with open(cache_file, 'w') as f:
            json.dump(response, f)

        return cache_key
```

### Integration with LLM Runner

```python
"""
Module Name: llm_runner.py
Purpose   : Runs LLM inference with metrics tracking
Params    : None
History   :
    Date          Notes
    07.05.2025    Enhanced with database metrics
"""

import time
from app.utils.metrics_logger import log_llm_call
from app.core.model_cache import ResponseCache
from app.core.model_service import get_model

class LLMRunner:
    def __init__(self):
        self.cache = ResponseCache()

    def generate(self, model_id, prompt, params=None, user_id=None, session_id=None, use_cache=True):
        """
        Generate text using an LLM with metrics tracking.

        Args:
            model_id (str): ID of the model to use
            prompt (str): Input prompt
            params (dict, optional): Generation parameters
            user_id (str, optional): User ID for tracking
            session_id (str, optional): Session ID for tracking
            use_cache (bool): Whether to use caching

        Returns:
            dict: Generated response
        """
        params = params or {}

        # Try cache first if enabled
        if use_cache:
            cached_response = self.cache.get(model_id, prompt, params, user_id)
            if cached_response:
                return cached_response

        # Get the model
        model = get_model(model_id)

        # Track metrics
        start_time = time.time()
        prompt_tokens = model.count_tokens(prompt)

        # Generate response
        response = model.generate(prompt, **params)

        # Calculate metrics
        end_time = time.time()
        latency_ms = int((end_time - start_time) * 1000)
        completion_tokens = model.count_tokens(response['text'])

        # Log metrics to database
        log_llm_call(
            model_id=model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            user_id=user_id,
            session_id=session_id
        )

        # Cache the response if enabled
        if use_cache:
            self.cache.put(model_id, prompt, params, response)

        return response
```
