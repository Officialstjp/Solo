# Solo System Architecture

This document details the architectural design of the Solo voice assistant, focusing on system components, their interactions, data flow, and design decisions.

## 1. High-Level Architecture

Solo follows a modular, event-driven architecture designed to be scalable, maintainable, and extensible. The system is built as a collection of loosely coupled microservices that communicate via an event bus, allowing for:

- **Component Independence**: Services can be developed, tested, and deployed independently
- **Flexible Scaling**: Individual components can be scaled based on demand
- **Fault Isolation**: Failures in one component don't cascade to others
- **Technology Flexibility**: Different components can use appropriate technologies

### 1.1 Folder & File Layout

```
Solo/
├─ app/                             # == runtime code
│  ├─ api/                          # === API layer
│  │   ├─ server.py                 # ---- Main file orchestrating API Init
│  │   ├─ factory.py                # ---- Factory for FastAPI Apps
│  │   ├─ dependencies.py           # ---- Dependency injection for the API
│  │   ├─ middleware/               # ---- Authentication middleware
│  │   └─ routes/                   # ---- API endpoint implementations
│  │
│  ├─ core/                         # === Core components
│  │   ├─ agent_bus.py              # ---- CrewAI/Autogen orchestration helpers
│  │   ├─ llm_runner.py             # ---- llama.cpp / Ollama wrapper + caching
│  │   ├─ llm_tester.py             # ---- CLI Testing utility for llms
│  │   ├─ memory.py                 # ---- Chroma vector-DB helper
│  │   ├─ model_cache.py            # ---- caching mechanism for llm responses
│  │   ├─ model_info.py             # ---- CLI utility to display model information
│  │   ├─ model_manager.py          # ---- Manages LLM model selection, validation
│  │   ├─ prompt_templates.py       # ---- prompt templates for different model formats
│  │   ├─ stt.py                    # ---- faster-whisper pipeline
│  │   ├─ tts.py                    # ---- piper voice synth
│  │   ├─ wake_word.py              # ---- Porcupine hot-key / wake-word
│  │
│  │   ├─ db/                       # ==== db_service components
│  │   │  ├─ big_brother.py         # ----- db security manager
│  │   │  ├─ cache_db.py            # ----- python wrapper for cache-db operations
│  │   │  ├─ connection.py          # ----- connection pool for db connections
│  │   │  ├─ metrics_db.py          # ----- python wrapper for metrics-db operations
│  │   │  ├─ models_db.py           # ----- python wrapper for models-db operations
│  │   │  ├─ rag_db.py              # ----- python wrapper for rag-db operations
│  │   │  ├─ users_db.py            # ----- python wrapper for rag-db operations
│  │
│  ├─ ui/                           # === User interface
│  │   └─ dashboard_app.py          # ---- Streamlit monitoring panel
│  │
│  ├─ utils/                        # === Shared utilities
│  │   ├─ logger.py                 # ---- struct-log setup
│  │   └─ events.py                 # ---- pydantic event schema, asyncio.Queue
│  │
│  ├─ main.py                       # --- CENTRAL MANAGER (launch & supervise coroutines)
│  ├─ config.py                     # --- pydantic-based settings loader (.env / CLI flags)
│  │
├─ scripts/                         # == Automation scripts
│  ├─ setup_dev.ps1                 # --- create venv, install deps, pre-commit
│  ├─ cleanup_dev.ps1               # --- uninstall & cleanup dependencies, env-vars...
│  ├─ run_agent.ps1                 # --- one-liner to start everything
│  ├─ quantize.bat                  # --- helper for gguf model conversion
│  │
│  ├─ db/                           # === database management scripts
│  │  ├─ backup-db.ps1              # ---- database backup
│  │  ├─ restore-db.ps1             # ---- restore database from a backup
│  │  ├─ run_DBContainer-db.ps1     # ---- run the DB docker instance
│  │  ├─ schedule-backups.ps1.ps1   # ---- schedule backups
│  │
│  ├─ DockerInit/                   # === database management scripts
│  │  ├─ 00-init-db.sh              # ---- docker initialization script
│  │
│  ├─ model/                        # === model utiltiy script
│  │  ├─ downl_model.ps1            # ---- download a model from a url
│  │  ├─ quantatize.bat             # ---- quantatize a model
│  │
├─ tests/                           # == Testing infrastructure
├─ docs/                            # == ocumentation
├─ cache/                           # == Cache storage
├─ backups/                         # == Database backups
```

### 1.2 Architectural Rationale

- **app/** is a **monorepo of micro-services** that can later be reused or split into docker images; the interface boundaries sit on the folder edges
- **main.py** owns the async event loop, starts each module in a asyncio.create_task, watches for crashes, and exposes health metrics
- The UI is a separate Streamlit process so it never blocks inference threads

## 2. Core Components

### 2.1 Event Bus

The Event Bus is the central communication mechanism that allows components to interact without direct dependencies:

- **events.py** defines Pydantic models for strongly-typed events
- An **asyncio.Queue** provides the pub/sub mechanism
- Components can publish events and subscribe to event types
- This approach keeps cross-module coupling near zero

### 2.2 Model Manager

The Model Manager provides a layer of abstraction for working with LLM models:

- Discovers GGUF models in the configured directory
- Extracts metadata (parameter size, quantization, context length)
- Validates models for compatibility
- Provides a clean interface for model selection

### 2.3 LLM Runner

The LLM Runner handles the actual text generation:

- Integrates with llama.cpp using Python bindings
- Supports GPU acceleration via cuBLAS
- Manages model loading and unloading
- Implements streaming generation
- Handles error recovery and fallbacks

### 2.4 Prompt Templates

The Prompt Template system ensures consistent formatting:

- Provides model-family-specific templates (Mistral, Llama, Phi)
- Manages system prompts and instruction formatting
- Handles chat history formatting
- Sanitizes responses to remove artifacts

### 2.5 Response Cache

The Response Cache improves performance and reduces resource usage:

- Uses an in-memory LRU cache for frequent queries
- Implements file-based persistence for long-term storage
- Provides TTL-based expiration
- Includes management utilities for clearing and refreshing

### 2.6 Database Service

The Database Service provides data persistence with specialized sub-services:

- Central coordination through DatabaseService
- Connection pooling and transaction management
- Specialized services for metrics, models, users, and security
- Supports time-based partitioning for high-volume tables

### 2.7 API Layer

The API Layer exposes system functionality via HTTP:

- FastAPI-based implementation with async support
- OpenAPI documentation and interactive UI
- Authentication middleware for security
- Endpoint routes for all core services

### 2.8 Speech Components (Planned)

The speech components will provide voice interaction:

- STT using faster-whisper for transcription
- TTS using Piper for voice synthesis
- Wake word detection with Porcupine

### 2.9 Agent Bus (Planned)

The Agent Bus will orchestrate multiple AI agents:

- CrewAI integration for agent workflows
- Specialized agents for different tasks
- Tool usage and reasoning capabilities

## 3. Data Flow & Component Interactions

### 3.1 Main Request-Response Flow

1. **User Input** → Entered via API or converted from speech via STT
2. **API Layer** → Validates request and publishes LLMRequestEvent
3. **LLM Runner** → Receives request, checks cache, generates response
4. **Model Manager** → Provides model for generation
5. **Prompt Templates** → Formats prompt for selected model
6. **Response Cache** → Stores response for future use
7. **LLM Runner** → Publishes LLMResponseEvent
8. **API Layer** → Returns response to user or forwards to TTS

### 3.2 Event Types & Communication Patterns

- **LLMRequestEvent**: Request for text generation
- **LLMResponseEvent**: Generated text response
- **ModelLoadRequestEvent**: Request to load a specific model
- **ModelLoadedEvent**: Notification that a model has been loaded
- **SessionClearEvent**: Request to clear a session's history
- **TTSRequestEvent**: Request for speech synthesis (planned)
- **STTEvent**: Speech transcription result (planned)
- **MetricsEvent**: System and performance metrics

Components subscribe to relevant event types and process them asynchronously, publishing new events as needed.

## 4. Database Schema

The database uses PostgreSQL with the following core tables:

- **users**: User accounts and authentication
- **sessions**: User sessions and authentication tokens
- **conversations**: User conversation tracking
- **messages**: Individual messages within conversations
- **models**: LLM model metadata and configurations
- **metrics**: System and performance metrics (time-partitioned)
- **vectors**: Document embeddings for RAG (using pgvector)

## 5. Security Architecture

Security is implemented at multiple levels:

- **Authentication**: JWT-based authentication with refresh tokens
- **Password Security**: Argon2 hashing for password storage
- **Authorization**: Role-based access control for API endpoints
- **Rate Limiting**: Protection against brute force and DoS attacks
- **Logging**: Security event logging for audit purposes

## 6. Configuration System

The configuration system uses Pydantic models for validation:

- Environment variables for runtime configuration
- Command-line arguments for overrides
- Default values for quick setup
- Nested configuration for component-specific settings

## 7. Testing Architecture

The testing infrastructure includes:

- Unit tests for individual components
- Integration tests for component interactions
- API tests for endpoint validation
- Database tests with transaction rollback

## 8. Deployment Model

Solo is designed for flexible deployment:

- **Local-First**: Primary deployment is on the user's local machine
- **Containerization**: Components can be containerized for cloud deployment
- **Scaling**: Components can be scaled independently based on load

## 9. Design Decisions & Rationale

### 9.1 Why Event-Driven Architecture?

Event-driven architecture was chosen to:
- Decouple components for independent development
- Support async processing for better resource utilization
- Allow for flexible scaling of individual components
- Simplify adding new components without modifying existing ones

### 9.2 Why PostgreSQL?

PostgreSQL was chosen over other databases because:
- It supports advanced features like time-based partitioning
- The pgvector extension provides vector search capabilities
- It offers strong ACID compliance for data integrity
- It provides robust security features
- It has excellent performance for the expected workload

### 9.3 Why FastAPI?

FastAPI was selected as the API framework because:
- It provides native async support for non-blocking operations
- It includes automatic OpenAPI documentation
- It has built-in request validation with Pydantic
- It offers excellent performance compared to alternatives

### 9.4 Why llama.cpp?

llama.cpp was chosen for LLM integration because:
- It provides efficient inference on consumer hardware
- It supports GPU acceleration via cuBLAS
- It works with a wide range of GGUF models
- It offers flexible generation parameters
- It has a small footprint and low overhead

## 10. Future Architectural Extensions

Planned architectural extensions include:

- **Distributed Deployment**: Support for running components on different machines
- **Horizontal Scaling**: Load balancing for high-demand components
- **Federated Learning**: Collaborative model improvement across instances
- **Multi-Modal Support**: Integration with image and audio understanding
- **Plugin System**: Extensibility through standardized plugins

Total time spent on this project (inlucding doc-work):
 -  **156h**

last updated 27.07.25 13:30, daily time at time of note: 1:30
