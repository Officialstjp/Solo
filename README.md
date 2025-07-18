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
- **STT** – real-time transcription using faster-whisper - ⏳ Planned
- **TTS** – voice output powered by Piper - ⏳ Planned
- **Memory** – Chroma vector database for retrieval‑augmented generation - ⏳ Planned
- **Agent Bus** – CrewAI orchestration for multi‑agent workflows - ⏳ Planned
- **Dashboard UI** - Streamlit metrics display - ⏳ Planned

## Implementation Status
The project has successfully implemented core LLM functionality:
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
- ✅ PostgreSQL database integration with time-based partitioning and metrics tracking
- ✅ Automated backup and restore tools for database management
- ⏳ Memory and RAG integration planned next
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
The PostgreSQL database provides robust data storage and metrics tracking:
- Docker-based deployment for easy setup and portability
- Logical schema organization (metrics, models, users, rag)
- Time-based partitioning for high-volume metrics tables
- Automated maintenance jobs with pg_cron
- PowerShell tools for backup, restore, and scheduled maintenance
- Vector storage for RAG functionality using pgvector
- Comprehensive security with role-based access control
- Detailed documentation for setup, maintenance, and common queries

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
