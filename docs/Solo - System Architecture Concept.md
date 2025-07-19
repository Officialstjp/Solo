## 1. Folder & File Layout

``` Text
Solo/
├─ app/                    # runtime code
│  ├─ api/
│  │   ├─ server.py        # Main file orchestrating API Init
│  │   ├─ factory.py       # Factory for FastAPI Apps
│  │   ├─ dependencies.py  # Dependy injection for the API
│  │   └─ routes/…
│  │   │   ├─ models_endpoint.py
│  │   │   ├─ metrics_endpoint.py
│  │   │   ├─ config_endpoint.py
│  │   │   ├─ llm_endpoint.py
│  ├─ core/
│  │   ├─ agent_bus.py     # CrewAI/Autogen orchestration helpers
│  │   ├─ llm_runner.py    # llama.cpp / Ollama wrapper + caching
│  │   ├─ llm_tester.py    # CLI Testing utility for llms
│  │   ├─ memory.py        # Chroma vector-DB helper
│  │   ├─ model_cache.py   # caching mechanism for llm responses
│  │   ├─ model_info.py    # CLI utility to display model information
│  │   ├─ model_manager.py # Manages LLM model selection, validation
│  │   ├─ prompt_templates.py # prompt templates for different model formats
│  │   ├─ stt.py           # faster-whisper pipeline
│  │   ├─ tts.py           # piper voice synth
│  │   └─ wake_word.py     # Porcupine hot-key / wake-word
│  ├─ ui/
│  │   └─ dashboard_app.py # Streamlit monitoring panel
│  ├─ utils/
│  │   ├─ logger.py        # struct-log setup
│  │   └─ events.py        # pydantic event schema, asyncio.Queue
│  ├─ main.py              # CENTRAL MANAGER (launch & supervise coroutines)
│  ├─ config.py            # pydantic-based settings loader (.env / CLI flags)
├─ scripts/
│  ├─ setup_dev.ps1        # create venv, install deps, pre-commit
│  ├─ cleanup_dev.ps1    # uninstall & cleanup dependencies, env-vars...
│  ├─ run_agent.ps1        # one-liner to start everything
│  ├─ quantize.bat         # helper for gguf model conversion
│  ├─ db/                  # database management scripts
│  │   ├─ backup-db.ps1    # database backup utility
│  │   ├─ restore-db.ps1   # database restore utility
│  │   └─ schedule-backups.ps1 # scheduled backup configuration
│  └─ postgresql/          # PostgreSQL initialization scripts
│      └─ init-scripts/    # database initialization SQL scripts
├─ tests/                  # pytest unit + integration tests
│  └─ …
├─ cache/                  # response cache storage
│  └─ llm_responses/
├─ backups/                # database backup storage
│  └─ …
├─ docs/                   # project documentation
│  ├─ POSTGRES_SETUP.md    # database setup guide
│  ├─ DATABASE_MANAGEMENT.md # database management guide
│  ├─ COMMON_QUERIES.md    # common SQL queries reference
│  ├─ DATABASE_INTEGRATION.md # Python database integration examples
│  └─ …
├─ requirements.txt / pyproject.toml
├─ .env.example            # sample secrets
└─ .github/
   └─ workflows/ci.yml     # pytest + lint GitHub Actiongitgit
```


**Why?**
- ***app/*** is a **monorepo of micro-services** that can later be reused or split into docker images; the interface boundaries sit on the folder edges.
- ***main.py*** owns the asnyc event loop, starts each module in a asyncio.create_task,
	watches for crashes, and exposes health metrics through the FastAPI **/status** route
- The UI is a separate Streamlit process so it never blocks inference threads.

---

## 2. Module Interfaces & Data-Flow

- **Event Bus** – **events.py** defines small pydantic models (**STTEvent**, **LLMRequestEvent**, **LLMResponseEvent**). All long-running services push / subscribe via an **asyncio.Queue**; this keeps cross-module coupling near zero.

- **Model Manager** – **model_manager.py** discovers and catalogs GGUF models in the models directory, extracts metadata (size, quantization, format), and provides a clean interface for model selection and validation.

- **Prompt Templates** – **prompt_templates.py** defines format-specific templates for different model families (Mistral, Llama, Phi, etc.), manages system prompts, and ensures consistent formatting and response sanitization.

- **Response Cache** – **model_cache.py** provides in-memory and file-based caching for LLM responses to avoid redundant computation, with TTL-based expiration and cache management utilities.

- **Speech I/O** – **stt.py** will wrap _faster-whisper_ in **CTranslate2** for real-time transcription; **tts.py** will call _Piper_ for local, low-latency TTS voices on Windows.

- **Wake Word** – start with a PowerShell hot-key; later enable _Porcupine_ for always-on detection (lightweight, 7 kB RAM/core).

- **LLM Runner** – **llm_runner.py** now provides:
    1. Integration with **llama.cpp** with cuBLAS GPU acceleration
    2. Conversation history tracking for multi-turn interactions
    3. Proper prompt formatting via the template system
    4. Response caching for improved performance
    5. Improved error handling and parameter management

- **Memory / RAG** – memory.py will embed text → vectors and store them in **Chroma** (runs embedded SQLite by default; zero-ops).

- **Database** – PostgreSQL with Docker Compose provides persistent storage for metrics, model information, user data, and vector embeddings for production use. Key features:
  - Time-based partitioning for high-volume metrics tables
  - Automated maintenance with pg_cron
  - Vector storage with pgvector extension
  - Logical schema organization
  - PowerShell tools for backup and restore

- **Database Services** – Comprehensive database services for all application data:
  - Central DatabaseService as the main entry point for database access
  - Specialized services for metrics, models, users, RAG, and caching
  - Security service (BigBrother) for authentication, authorization, and rate limiting
  - User database with session tracking and conversation history
  - Connection pooling for efficient database access
  - Proper error handling and logging

- **Agent Layer** – agent_bus.py will wrap **CrewAI** to create multi-agent workflows (planning, critique, tool-use).

- **API** – server.py will be a **FastAPI** instance; REST routes will hand off work to main.py via the event bus, and long jobs will run in BackgroundTask helpers.

- **Dashboard** – **dashboard_app.py** will use **Streamlit** to consume **/status** JSON and render live tokens-per-second, GPU memory, & recent dialogues.

## 3. Technology Stack


| Layer                  | Tool                                   | Notes                                   |
| ---------------------- | -------------------------------------- | --------------------------------------- |
| Lang runtime           | Python 3.11 (pyenv-win)                | Fast async, typing, mature ML libs      |
| Centralized supervisor | asyncio + anyio, uvloop optional       | Lightweight process mgmt                |
| Model Management       | Custom ModelManager + PromptLibrary    | Auto-detection, metadata extraction     |
| Response Caching       | In-memory + file-based cache           | Performance optimization                |
| Database               | PostgreSQL + pgvector + pg_cron        | Metrics, models, user data, vectors     |
| STT                    | faster-whisper CUDA                    | GPU-accelerated Whisper model          |
| TTS                    | Piper                                  | Local voices, 50ms start latency        |
| Wake Word              | Porcupine                              | 1 MB Model, cross-platform              |
| LLM                    | llama.cpp (GGUF int4) or Ollama + GPTQ | Works in 8GB VRAM, up to 13B            |
| Agent framework        | CrewAI                                 | Declarative multi-agent graphs          |
| Vector DB              | Chroma (local) + pgvector (production) | Embedded for dev, PostgreSQL for prod   |
| API                    | FastAPI + Uvicorn                      | Type hints, async, background tasks     |
| Dashboard              | Streamlit                              | 1-file reactive SPA for ops view        |
| CI                     | Github Actions pytest template         | Free runners; sample workflow docs      |
| Scripts                | Powershell 7                           | Native hot-key, easy Windows automation |

## 4. Implementation Status and Development Timeline

### Current Status (as of August 2024)

| Component               | Status                 | Notes                                                                                             |
| ----------------------- | ---------------------- | ------------------------------------------------------------------------------------------------- |
| Core Architecture       | ✅ Implemented         | Async event loop, component registration, error handling, and event bus communication              |
| Configuration           | ✅ Enhanced            | Pydantic models for config with validation, nested config objects, and smart defaults             |
| Logging                 | ✅ Implemented         | Structured logging with JSON output option                                                         |
| Event Bus               | ✅ Implemented         | Async event pub/sub system with typed event definitions                                            |
| Model Manager           | ✅ Implemented         | Auto-discovery of models, metadata extraction, model selection, and validation                     |
| Prompt Templates        | ✅ Implemented         | Model-specific formatting, system prompts, sanitization, and template library                      |
| Response Cache          | ✅ Implemented         | In-memory and file-based caching with TTL expiration                                               |
| LLM Runner              | ✅ Enhanced            | llama.cpp integration with GPU support, conversation history, prompt templates, response caching   |
| CLI Tester              | ✅ Enhanced            | Interactive CLI for testing LLM with parameter customization and conversation history              |
| Model Info CLI          | ✅ Implemented         | CLI tool for inspecting available models and their metadata                                        |
| PostgreSQL Database     | ✅ Implemented         | Docker-based PostgreSQL with schema design, partitioning, and maintenance tools                   |
| Database Services       | ✅ Implemented         | Central DB service with specialized modules for metrics, models, users, and security               |
| User Management         | ✅ Implemented         | User database service with session tracking and conversation history                               |
| Security Service        | ✅ Implemented         | Authentication, authorization, rate limiting, and security monitoring                              |
| Backup & Restore Tools  | ✅ Implemented         | PowerShell scripts for database backup, restore, and scheduled maintenance                        |
| API Layer               | ⏳ In Progress         | FastAPI server with initial routes for LLM, models, metrics, and configuration                    |
| Memory / RAG            | ⏳ In Progress         | Database structure implemented, integration with LLM pipeline in progress                          |
| STT Pipeline            | ⏳ Planned             | Not yet implemented                                                                               |
| TTS Output              | ⏳ Planned             | Not yet implemented                                                                               |
| Dashboard               | ⏳ Planned             | Not yet implemented                                                                               |
| Agent Bus               | ⏳ Planned             | Not yet implemented                                                                               |
| Wake-word & Packaging   | ⏳ Planned             | Not yet implemented                                                                               |

### Next Steps

1. **Immediate Priority**: Complete API Integration
   - Finalize the integration of database services with API endpoints
   - Implement WebSocket support for streaming LLM responses
   - Add authentication middleware using the BigBrother security service
   - Implement rate limiting for API endpoints
   - Add comprehensive error handling and request validation

2. **Short-term Roadmap**:
   - Complete Memory/RAG integration with LLM pipeline
   - Finalize testing and optimization of database services
   - Build dashboard UI with Streamlit for monitoring
   - Begin STT pipeline using faster-whisper

3. **Mid-term Goals**:
   - Develop TTS output using Piper
   - Implement agent orchestration with CrewAI
   - Add wake-word detection with Porcupine
   - Optimize database performance and maintenance

### Development Timeline

| Week | Milestone              | Deliverables                                                                                                        |
| ---- | ---------------------- | ------------------------------------------------------------------------------------------------------------------- |
| 0-1  | Repo bootstrap         | ✅ Folder structure, Python environment, requirements, basic scripts                                                |
| 2    | Core manager & logging | ✅ Event loop, JSON logger, event classes                                                                          |
| 3    | LLM runner wrapper     | ✅ llama.cpp integration with GPU support, interactive CLI, response sanitization                                   |
| 3-4  | LLM enhancements       | ✅ Model management, prompt templates, response caching, conversation history                                       |
| 4-5  | Database implementation| ✅ PostgreSQL with Docker, partitioning, schemas, backup/restore tools                                              |
| 5-6  | Database services      | ✅ Specialized services for metrics, models, users, security, and caching                                           |
| 6-7  | API layer integration  | ⏳ Connecting database services to API endpoints, security middleware                                               |
| 7-8  | Memory / RAG           | ⏳ pgvector integration for production; Chroma for development                                                      |
| 8-9  | STT mini-pipeline      | ⏳ Integrate faster-whisper; audio input to text                                                                    |
| 9-10 | TTS output             | ⏳ Piper inference; voice selection by config                                                                       |
| 10-11| Dashboard v1           | ⏳ Streamlit panel reading /status and database metrics                                                             |
| 11-12| Agent bus              | ⏳ CrewAI integration                                                                                               |
| 12-13| Wake-word & packaging  | ⏳ Porcupine integration; installer scripts                                                                         |

Note: We've completed the development of specialized database services including user management, security (authentication, authorization, rate limiting), metrics logging, and model registry. The next phase focuses on integrating these services with the API layer and implementing the Memory/RAG functionality.


## 5. Environment & CI Details

- **Python setup** – use pyenv-win to install 3.11, then py -m venv .venv. Store dependencies in **pyproject.toml** (Poetry) or requirements.txt; pin torch, ctranslate2, llama-cpp-python (with --extra-index-url) for GPU builds.

- **Pre-commit** – black, isort. Run in dev.ps1.

- **Binary assets** – place GGUF models, Porcupine keyword files, Piper voices in models/ (git-ignored). Write a quantize.bat helper to convert .gguf from original checkpoints.

- **Model Management** – Models are automatically detected in the models/ directory. The ModelManager provides:
  1. Automatic discovery of GGUF models in the configured model directory
  2. Metadata extraction from filenames (parameter size, quantization level, model family)
  3. Model validation and selection based on user requirements
  4. Support for models from multiple families (Mistral, Llama, Phi, Mixtral, TinyLlama)
  5. Cache management for model information to avoid redundant file operations

For detailed instructions on using the LLM features, refer to [USING_LLM_FEATURES.md](USING_LLM_FEATURES.md).
