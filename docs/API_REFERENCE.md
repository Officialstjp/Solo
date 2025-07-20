# Solo API Reference

## Overview

The Solo API provides programmatic access to the Solo AI Assistant's functionality, including LLM interactions, model management, user management, and system metrics. This document details all available endpoints, their parameters, and response structures.

## Base URL

All API paths are relative to the base URL:
dev: `http://localhost:8080/`
prod: '🤷‍♂️'

## Authentication

Most endpoints require authentication using JWT tokens. To authenticate:

1. Send a POST request to `/auth/login` with your credentials
2. Use the returned token in the `Authorization` header for subsequent requests:
   ```
   Authorization: Bearer YOUR_TOKEN
   ```

Public endpoints that don't require authentication:
- `/status`
- `/auth/login`
- `/auth/register`
- `/auth/forgot-password`
- `/auth/reset-password`
- `/metrics/*` (metrics endpoints are publicly accessible)

## Endpoints

### Authentication API

#### `POST /auth/login`

Authenticates a user and returns an access token.

**Request Body:**
```json
{
  "username": "string",
  "password": "string",
  "remember": boolean
}
```

**Response:**
```json
{
  "access_token": "string",
  "token_type": "string",
  "expires_in": integer,
  "user_id": "string",
  "username": "string"
}
```

#### `POST /auth/register`

Registers a new user.

**Request Body:**
```json
{
  "username": "string",
  "email": "string",
  "password": "string",
  "full_name": "string" (optional)
}
```

**Response:**
```json
{
  "user_id": "string",
  "username": "string",
  "email": "string",
  "full_name": "string" (if provided),
  "is_active": boolean
}
```

#### `POST /auth/forgot-password`

Initiates a password reset process.

**Request Body:**
```json
{
  "email": "string"
}
```

**Response:**
```json
{
  "status": "string",
  "message": "string"
}
```

#### `POST /auth/reset-password`

Completes a password reset process.

**Request Body:**
```json
{
  "token": "string",
  "new_password": "string"
}
```

**Response:**
```json
{
  "status": "string",
  "message": "string"
}
```

### User Management API

#### `GET /users/profile`

Retrieves the current user's profile information.

**Response:**
```json
{
  "user_id": "string",
  "username": "string",
  "email": "string",
  "full_name": "string",
  "is_active": boolean
}
```

#### `PUT /users/profile`

Updates the current user's profile information.

**Request Body:**
```json
{
  "full_name": "string" (optional),
  "email": "string" (optional),
  "preferences": {
    "theme": "string",
    "language": "string",
    "notifications_enabled": boolean,
    "custom_settings": object
  } (optional)
}
```

**Response:**
Updated user profile object.

#### `GET /users/preferences`

Retrieves the current user's preferences.

**Response:**
```json
{
  "theme": "string",
  "language": "string",
  "notifications_enabled": boolean,
  "custom_settings": object
}
```

#### `PUT /users/preferences`

Updates the current user's preferences.

**Request Body:**
```json
{
  "theme": "string" (optional),
  "language": "string" (optional),
  "notifications_enabled": boolean (optional),
  "custom_settings": object (optional)
}
```

**Response:**
Updated preferences object.

### LLM API

#### `POST /llm/generate`

Generates a response using the selected LLM.

**Request Body:**
```json
{
  "prompt": "string",
  "system_prompt": "string" (optional),
  "session_id": "string" (optional),
  "parameters": {
    "model_id": "string" (optional),
    "max_tokens": integer (default: 512),
    "temperature": float (default: 0.7),
    "top_p": float (default: 0.95),
    "maintain_history": boolean (default: true),
    "max_history": integer (default: 10),
    "template_id": "string" (optional)
  },
  "chat_history": [
    {
      "role": "string",
      "content": "string"
    }
  ] (optional),
  "conversation_id": "string" (optional),
  "user_id": "string" (optional)
}
```

**Response:**
```json
{
  "response": "string",
  "session_id": "string",
  "conversation_id": "string" (if provided),
  "metrics": {
    "tokens_used": integer,
    "generation_time_ms": float,
    "tokens_per_second": float,
    "cache_hit": boolean,
    "model_name": "string"
  }
}
```

#### `POST /llm/stream`

Stream-generates a response using the selected LLM.

**Request Body:**
Same as `/llm/generate`

**Response:**
SSE stream of response chunks.

#### `POST /llm/load-model`

Explicitly loads a model for use.

**Request Body:**
```json
{
  "model_id": "string",
  "priority": boolean (default: false)
}
```

**Response:**
```json
{
  "status": "string",
  "model_id": "string",
  "message": "string"
}
```

#### `GET /llm/status/{model_id}`

Checks the loading status of a model.

**Response:**
```json
{
  "model_id": "string",
  "loaded": boolean,
  "status": "string",
  "last_used": float (optional),
  "error": "string" (optional)
}
```

#### `POST /llm/clear-session`

Clears the conversation history for a session.

**Request Body:**
```json
{
  "session_id": "string"
}
```

**Response:**
```json
{
  "status": "string",
  "message": "string"
}
```

### Models API

#### `GET /models/list`

Lists all available models.

**Response:**
Array of model information objects.

#### `GET /models/{model_id}`

Gets information about a specific model.

**Response:**
Model information object.

#### `GET /models/info/{model_name}`

Gets detailed information about a specific model.

**Response:**
```json
{
  "status": "string",
  "message": "string",
  "model": {
    "name": "string",
    "path": "string",
    "format": "string",
    "parameter_size": "string",
    "quantization": "string",
    "context_length": "string",
    "file_size_mb": "string"
  }
}
```

#### `POST /models/select`

Selects a model to use.

**Request Body:**
```json
{
  "model_path": "string"
}
```

**Response:**
```json
{
  "status": "string",
  "message": "string",
  "model": {
    "name": "string",
    "path": "string",
    "format": "string",
    "parameter_size": "string",
    "quantization": "string",
    "context_length": "string",
    "file_size_mb": "string"
  }
}
```

### Conversations API

#### `GET /conversations`

Lists all conversations for the current user.

**Query Parameters:**
- `skip` (integer, default: 0): Number of conversations to skip
- `limit` (integer, default: 20): Maximum number of conversations to return

**Response:**
Array of conversation objects.

#### `POST /conversations`

Creates a new conversation.

**Request Body:**
```json
{
  "title": "string",
  "session_id": "string" (optional)
}
```

**Response:**
Created conversation object.

#### `GET /conversations/{conversation_id}`

Gets details of a specific conversation.

**Response:**
```json
{
  "conversation_id": "string",
  "title": "string",
  "created_at": "string",
  "updated_at": "string",
  "message_count": integer,
  "messages": [
    {
      "message_id": "string",
      "conversation_id": "string",
      "role": "string",
      "content": "string",
      "created_at": "string",
      "model_id": "string" (optional),
      "tokens": integer (optional)
    }
  ]
}
```

#### `PUT /conversations/{conversation_id}`

Updates a conversation.

**Request Body:**
```json
{
  "title": "string"
}
```

**Response:**
Updated conversation object.

#### `DELETE /conversations/{conversation_id}`

Deletes a conversation.

**Response:**
```json
{
  "status": "string",
  "message": "string"
}
```

#### `POST /conversations/{conversation_id}/messages`

Adds a message to a conversation.

**Request Body:**
```json
{
  "content": "string",
  "role": "string" (default: "user"),
  "model_id": "string" (optional),
  "request_id": "string" (optional)
}
```

**Response:**
Created message object.

### Configuration API

#### `GET /config`

Gets the full application configuration.

**Response:**
Complete configuration object.

#### `GET /config/{section}`

Gets a specific section of the configuration.

**Response:**
```json
{
  "values": object,
  "description": "string" (optional)
}
```

#### `POST /config/update`

Updates a specific configuration value.

**Request Body:**
```json
{
  "path": "string",
  "value": any
}
```

**Response:**
Updated configuration object.

#### `POST /config/reload`

Reloads the configuration from disk.

**Response:**
Reloaded configuration object.

### Metrics API

#### `GET /metrics`

Gets all system and LLM metrics.

**Query Parameters:**
- `include_history` (boolean, default: false): Whether to include historical metrics

**Response:**
```json
{
  "system": {
    "cpu_percent": float,
    "cpu_temperature": float,
    "memory_percent": float,
    "memory_used_mb": float,
    "memory_temperature": float,
    "gpu_percent": float,
    "gpu_fans_rpm": float,
    "gpu_watt": float,
    "vram_percent": float,
    "vram_used_mb": float,
    "system_uptime_seconds": float,
    "app_uptime_seconds": float
  },
  "llm": {
    "total_requests": integer,
    "total_tokens_generated": integer,
    "cache_hits": integer,
    "cache_misses": integer,
    "avg_tokens_per_second": float,
    "avg_response_time_ms": float
  },
  "tokens_per_second_history": array (if include_history is true),
  "response_times_history": array (if include_history is true)
}
```

#### `GET /metrics/system`

Gets system metrics only.

**Response:**
System metrics object.

#### `GET /metrics/llm`

Gets LLM metrics only.

**Response:**
LLM metrics object.

## Error Responses

All endpoints return standard HTTP status codes:

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Authentication required or failed
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

Error responses have the following structure:

```json
{
  "detail": "string" or {
    "msg": "string",
    "type": "string",
    "loc": ["string", ...]
  }
}
```
