# Solo

Solo is a (planned) local-first voice assistant that combines speech recognition, text-to-speech and a lightweight large language model. The application is organised as a set of micro‑services under the `app/` folder with `main.py` acting as an async supervisor. A FastAPI server exposes REST and WebSocket endpoints while a Streamlit dashboard provides runtime metrics.

This project's purpose is learning to and actually designing a server-based application up to modern standard.
Development for this project is currently on hold.

## Key Features (currently)

- **Local-First Architecture**: Privacy-focused design that keeps data and processing on the device
- **Modern LLM Integration**: Seamless support for various GGUF models (Mistral, Llama, Phi, Mixtral)
- **Event-Driven Design**: Asynchronous communication between components for responsive performance
- **API-First Approach**: RESTful API for easy integration with other systems
- **Database Integration**: PostgreSQL with time-based partitioning for efficient data storage
- **User Management**: Complete user authentication and session management

## Documentation

- [System Architecture](docs/Solo%20-%20System%20Architecture%20Concept.md): Detailed explanation of system design and component interactions
- [Development Status](docs/DEVELOPMENT_STATUS.md): Current implementation status and development timeline
- [API Reference](docs/API_REFERENCE.md): Comprehensive documentation of all API endpoints
- [Testing Strategy](docs/TESTING_STRATEGY.md): Testing methodology and tools

## Setup
1. Install Python 3.11 or later (supports up to 3.13).
2. Run `scripts/setup-dev.ps1` (PowerShell) to create a virtual environment and install dependencies.
3. Download a compatible GGUF instruction-tuned model to the `models/` directory (auto-detected).
4. Configure the model path in `app/config.py` or via environment variables.
5. For database functionality, install Docker and Docker Compose.
6. Create a `.env` file with database credentials (see `.env.example`).
7. Start the PostgreSQL database with `docker-compose up -d db`.
8. Start the assistant with `python -m app.main`.

## Development
- Use the interactive LLM tester: `python -m app.core.llm_tester`
- For a simpler demo: `python -m app.core.llm_demo --model "[model_path]" --interactive`
- To list and inspect available models: `python -m app.core.model_info --verbose`
- To back up the database: `pwsh scripts/db/backup-db.ps1`
- To set up scheduled database backups: `pwsh scripts/db/schedule-backups.ps1`

See the detailed guide in [docs/cheatsheets/USING_LLM_FEATURES.md](docs/cheatsheets/USING_LLM_FEATURES.md) for more information on using these features.
For database setup and management, refer to [docs/DB/POSTGRES_SETUP.md](docs/DB/POSTGRES_SETUP.md).

## Key Components

### API Layer
The RESTful API provides programmatic access to all Solo functionality:
- FastAPI-based implementation with modern async features
- Comprehensive endpoint routes for all core services
- Authentication middleware for securing routes
- Detailed API documentation available at `/docs` when running

### Model Management
The `ModelManager` provides automatic model discovery and metadata extraction:
- Auto-detects GGUF models in the `models/` directory
- Extracts metadata including parameter size, quantization level, and model family
- Supports multiple model families (Mistral, Llama, Phi, Mixtral, TinyLlama)

### Database Services
The PostgreSQL database provides robust data storage:
- Central `DatabaseService` coordinating all database operations
- Dedicated services for metrics, models, users, and security
- User management with session tracking and conversation history
- Time-based partitioning for high-volume metrics tables
- PowerShell tools for backup, restore, and scheduled maintenance

For detailed information about specific components, architecture decisions, and implementation status, please refer to the documentation in the `docs/` directory.
