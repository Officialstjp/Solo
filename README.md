# Solo

Solo is a local-first voice assistant that combines speech recognition, text-to-speech and a lightweight large language model. The application is organised as a set of micro‑services under the `app/` folder with `main.py` acting as an async supervisor. A FastAPI server exposes REST and WebSocket endpoints while a Streamlit dashboard provides runtime metrics.

## Key Components
- **LLM Runner** – llama.cpp backend with GPU support - ✅ Enhanced implementation
- **Model Manager** - Dynamic model detection and selection - ✅ Implemented
- **Prompt Templates** - Model-specific prompt formatting - ✅ Implemented
- **Response Cache** - Performance optimization with caching - ✅ Implemented
- **Event Bus** - Asynchronous event-based communication between components - ✅ Implemented
- **CLI Tester** - Interactive testing interface for LLM functionality - ✅ Implemented
- **PostgreSQL Database** - Production-ready data storage with partitioning - ✅ Implemented
- **Database Services** - Specialized services for users, models, metrics, and security - ✅ Implemented
- **User Management** - User database with sessions and conversation history - ✅ Implemented
- **Security Service** - Authentication, authorization, and rate limiting - ✅ Implemented
- **API Layer** - FastAPI server with endpoint routes - ⏳ In Progress
- **Memory / RAG** - Vector database integration - ⏳ In Progress
- **STT** – real-time transcription using faster-whisper - ⏳ Planned
- **TTS** – voice output powered by Piper - ⏳ Planned
- **Agent Bus** – CrewAI orchestration for multi‑agent workflows - ⏳ Planned
- **Dashboard UI** - Streamlit metrics display - ⏳ Planned

## Implementation Status
The project has successfully implemented core LLM functionality and database services:
- ✅ Event bus architecture for component communication
- ✅ LLM runner with llama.cpp integration and GPU acceleration
- ✅ Model management system with auto-detection and metadata extraction
- ✅ Prompt template system for different model formats
- ✅ Response caching for performance optimization
- ✅ Enhanced configuration with validation and smart defaults
- ✅ Conversation history tracking for stateful interactions
- ✅ Support for multiple model formats (Mistral, Llama, TinyLlama, Phi, Mixtral)
- ✅ Response sanitization and formatting for clean outputs
- ✅ Interactive testing CLI with parameter customization
- ✅ Model inspection tools for analyzing available models
- ✅ PostgreSQL database with time-based partitioning and metrics tracking
- ✅ Comprehensive database services for users, models, metrics, and security
- ✅ User management with session tracking and conversation history
- ✅ Security service with authentication, authorization, and rate limiting
- ✅ Automated backup and restore tools for database management
- ⏳ API integration with database services in progress
- ⏳ Memory and RAG integration with pgvector in progress
- ⏳ Speech components (STT/TTS) and additional features to follow

## Setup
1. Install Python 3.11 or later (supports up to 3.13).
2. Run `scripts/setup-dev.ps1` (PowerShell) to create a virtual environment and install dependencies.
3. Download a compatible GGUF instruction-tuned model to the `models/` directory (auto-detected).
4. Configure the model path in `app/config.py` or via environment variables.
5. For database functionality, install Docker and Docker Compose.
6. Create a `.env` file with database credentials (see `.env.example`).
7. Start the PostgreSQL database with `docker-compose up -d db`.
8. Start the assistant with `pwsh scripts/run_agent.ps1` or run `python app/main.py` directly.

## Development
- Use the interactive LLM tester to try out prompts: `python -m app.main`
- For a simpler demo: `python -m app.core.llm_demo --model "[model_path]" --interactive`
- To list and inspect available models: `python -m app.core.model_info --verbose`
- To back up the database: `pwsh scripts/db/backup-db.ps1`
- To set up scheduled database backups: `pwsh scripts/db/schedule-backups.ps1`

See the detailed guide in [docs/USING_LLM_FEATURES.md](docs/USING_LLM_FEATURES.md) for more information on using these features.
For database setup and management, refer to [docs/POSTGRES_SETUP.md](docs/POSTGRES_SETUP.md) and [docs/DATABASE_MANAGEMENT.md](docs/DATABASE_MANAGEMENT.md).

## Features in Detail

### Model Management
The `ModelManager` provides automatic model discovery and metadata extraction:
- Auto-detects GGUF models in the `models/` directory
- Extracts metadata including parameter size, quantization level, and model family
- Supports multiple model families (Mistral, Llama, Phi, Mixtral, TinyLlama)
- Provides a clean interface for model selection and validation

### Prompt Templates
The prompt template system ensures consistent formatting across different models:
- Model-specific templates for various families (Mistral, Llama, Phi, etc.)
- Customizable system prompts for different use cases
- Response sanitization to remove artifacts and ensure clean outputs
- Support for conversation history and context

### Response Caching
The caching system improves performance by avoiding redundant computation:
- In-memory cache for frequent queries
- File-based persistence for long-term storage
- TTL-based expiration policy
- Cache management utilities for clearing and refreshing

### PostgreSQL Database
The PostgreSQL database provides robust data storage with specialized services:
- Central `DatabaseService` coordinating all database operations
- Dedicated services for metrics, models, users, RAG, and caching
- Security service (`BigBrother`) provides strong security features:
  - Secure password handling with Argon2 hashing
  - Rate limiting for sensitive operations
  - TOTP-based multi-factor authentication
  - Account lockout after failed attempts
  - security event logging
  - Password policy enforcement
  - Password history tracking
- User management with session tracking and conversation history
- Time-based partitioning for high-volume metrics tables
- Automated maintenance with pg_cron
- PowerShell tools for backup, restore, and scheduled maintenance
- Vector storage for RAG functionality using pgvector
- Comprehensive security with role-based access control

For database setup and management, refer to the documentation in the `docs/DB/` directory:
- [POSTGRES_SETUP.md](docs/DB/POSTGRES_SETUP.md): Detailed guide for setting up PostgreSQL
- [DATABASE_DESIGN.md](docs/DB/DATABASE_DESIGN.md): Schema design and data structures
integration
- [COMMON_QUERIES.md](docs/DB/COMMON_QUERIES.md): Reference for commonly used SQL queries
- [SQL cheatsheet.md](docs/DB/SQL%20cheatsheet.md): SQL syntax reference for database operations

### Configuration
Enhanced configuration system with validation and smart defaults:
- Nested Pydantic models for different component configs
- Environment variable override support
- Runtime parameter validation
- Sensible defaults for quick setup

### CLI Tools
Several command-line tools are available for testing and debugging:
- **LLM Tester**: Interactive CLI for testing LLM functionality
- **LLM Demo**: Simplified demo for quick testing
- **Model Info**: Tool for inspecting available models and their metadata

Refer to `docs/Solo - System Architecture Concept.md` for detailed architecture information and the development roadmap.
