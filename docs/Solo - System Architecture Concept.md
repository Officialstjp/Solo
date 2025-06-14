
## 1. Folder & File Layout

``` Text
Solo/
├─ app/                    # runtime code
│  ├─ main.py              # CENTRAL MANAGER (launch & supervise coroutines)
│  ├─ config.py            # pydantic-based settings loader (.env / CLI flags)
│  ├─ core/
│  │   ├─ llm_runner.py    # llama.cpp / Ollama wrapper + caching
│  │   ├─ stt.py           # faster-whisper pipeline
│  │   ├─ tts.py           # piper voice synth
│  │   ├─ wake_word.py     # Porcupine hot-key / wake-word
│  │   ├─ memory.py        # Chroma vector-DB helper
│  │   └─ agent_bus.py     # CrewAI/Autogen orchestration helpers
│  ├─ api/
│  │   ├─ server.py        # FastAPI instance (REST + WebSocket)
│  │   └─ routes/…
│  ├─ ui/
│  │   └─ dashboard_app.py # Streamlit monitoring panel
│  ├─ utils/
│  │   ├─ logger.py        # struct-log setup
│  │   └─ events.py        # pydantic event schema, asyncio.Queue
│  └─ __init__.py
├─ scripts/
│  ├─ dev.ps1              # create venv, install deps, pre-commit
│  ├─ run_agent.ps1        # one-liner to start everything
│  └─ quantize.bat         # helper for gguf model conversion
├─ tests/                  # pytest unit + integration tests
│  └─ …
├─ requirements.txt / pyproject.toml
├─ .env.example            # sample secrets
└─ .github/
   └─ workflows/ci.yml     # pytest + lint GitHub Action
```


**Why?**
- ***app/*** is a **monorepo of micro-services** that can later be reused or split into docker images; the interface boundaries sit on the folder edges.
- ***main.py*** owns the asnyc event oop, starts each module in a asyncio.create_task,
	watches for crashes, and exposes health metrics through the FastAPI **/status** route
- The UI is a sperate Streamlit process so it never blocks inference threads.

---

## 2. Module Interfaces & Data-Flow

- **Event Bus** – **events.py** defines small pydantic models (**STTEvent**, **LLMReply**, **ActionRequest**). All long-running services push / subscribe via an **asyncio.Queue**; this keeps cross-module coupling near zero.

- **Speech I/O** – **stt.py** wraps _faster-whisper_ in **CTranslate2** for real-time transcription; **tts.py** calls _Piper_ for local, low-latency TTS voices on Windows.

- **Wake Word** – start with a PowerShell hot-key; later enable _Porcupine_ for always-on detection (lightweight, 7 kB RAM/core).

- **LLM Runner** – two interchangeable back-ends:
    1. **llama.cpp** built with cuBLAS on Windows (guide shows proper CMAKE_ARGS syntax).

    2. **Ollama** via WSL-2; recent builds expose GPU to Docker after NVIDIA container-toolkit update.
	A config flag selects which runtime.

- **Memory / RAG** – memory.py embeds text → vectors and stores them in **Chroma** (runs embedded SQLite by default; zero-ops).

- **Agent Layer** – agent_bus.py wraps **CrewAI** to create multi-agent workflows (planning, critique, tool-use).

- **API** – server.py is a **FastAPI** instance; REST routes hand off work to main.py via the event bus, and long jobs run in BackgroundTask helpers.

- **Dashboard** – **dashboard_app.py** uses **Streamlit** to consume **/status** JSON and render live tokens-per-second, GPU memory, & recent dialogues.

## 3. Technology Stack


| Layer                  | Tool                                   | Notes                                   |
| ---------------------- | -------------------------------------- | --------------------------------------- |
| Lang runtime           | Python 3.11 (pyenv-win)                | Fast async, typing, mature ML libs      |
| Centralized supervisor | asyncio + anyio, uvloop optional       | Lightweight process mgmt                |
| STT                    | faster-whisper CUDA                    | GPU-acceralerated Whisper model         |
| TTS                    | Piper                                  | Local voices, 50ms start latency        |
| Wake Word              | Porcupine                              | 1 MB Model, cross-platform              |
| LLM                    | llama.cpp (GGUF int4) or Ollama + GPTQ | Works in 8GB VRAM, up to 13B            |
| Agent framework        | CrewAI                                 | Declarative multi-agent graphs          |
| Vector DB              | Chroma                                 | Embedded, server-less, Python API       |
| API                    | FastAPI + Uvicorn                      | Tpye hints, async, background tasks     |
| Dashboard              | Streamlit                              | 1-file reactive SPA for ops view        |
| CI                     | Github Actions pytest template         | Free runners; sample workflow docs      |
| Scripts                | Powershell 7                           | Native hot-key, easy Windows automation |
## 4. Implementation Status and Development Timeline

### Current Status (as of June 14, 2025)

| Component               | Status                 | Notes                                                                                             |
| ----------------------- | ---------------------- | ------------------------------------------------------------------------------------------------- |
| Core Architecture       | ✅ Implemented         | Basic async event loop, component registration, and event bus communication                        |
| Configuration           | ✅ Implemented         | Pydantic models for config with environment variable support                                       |
| Logging                 | ✅ Implemented         | Structured logging with JSON output option                                                         |
| Event Bus               | ✅ Implemented         | Async event pub/sub system with typed event definitions                                            |
| LLM Runner              | ✅ Partial             | Basic llama.cpp integration with GPU support                                                       |
| CLI Tester              | 🔄 In Progress        | Interactive CLI for testing LLM (needs improved UX)                                                |
| STT Pipeline            | ⏳ Planned             | Not yet implemented                                                                               |
| TTS Output              | ⏳ Planned             | Not yet implemented                                                                               |
| API Layer               | ⏳ Planned             | Not yet implemented                                                                               |
| Dashboard               | ⏳ Planned             | Not yet implemented                                                                               |
| Memory / RAG            | ⏳ Planned             | Not yet implemented                                                                               |
| Agent Bus               | ⏳ Planned             | Not yet implemented                                                                               |
| Wake-word & Packaging   | ⏳ Planned             | Not yet implemented                                                                               |

### Next Steps

1. **Immediate Priority**: Fix UX issues in the LLM Tester interface
   - Improve prompt flow and response handling
   - Fix system prompt reuse issues
   - Enhance error handling and response formatting

2. **Short-term Roadmap**:
   - Complete LLM runner with proper caching and error handling
   - Implement basic STT pipeline for audio input
   - Add TTS output for spoken responses
   - Begin API layer implementation

3. **Mid-term Goals**:
   - Develop monitoring dashboard
   - Implement memory/RAG capabilities
   - Add agent orchestration

### Original Development Timeline

| Week | Milestone              | Deliverables                                                                                                        |
| ---- | ---------------------- | ------------------------------------------------------------------------------------------------------------------- |
| 0-1  | Repo bootstrap         | ✅ Folder structure, Python environment, requirements, basic scripts                                                |
| 2    | Core manager & logging | ✅ Event loop, JSON logger, event classes                                                                          |
| 3    | LLM runner wrapper     | 🔄 Basic llama.cpp integration with GPU support, interactive CLI                                                    |
| 4    | STT mini-pipeline      | ⏳ Integrate faster-whisper; audio input to text                                                                    |
| 5    | TTS output             | ⏳ Piper inference; voice selection by config                                                                       |
| 6    | API layer              | ⏳ FastAPI routes /chat /transcribe /status                                                                         |
| 7    | Dashboard v1           | ⏳ Streamlit panel reading /status                                                                                  |
| 8    | Memory / RAG           | ⏳ Chroma embedded DB; similarity search                                                                            |
| 9    | Agent bus              | ⏳ CrewAI integration                                                                                               |
| 10   | Wake-word & packaging  | ⏳ Porcupine integration; installer scripts                                                                         |

Note: The timeline may be adjusted based on progress and priority shifts. Currently focused on establishing core LLM functionality with a robust event-based architecture.


## 5. Environment & CI Details
(provided by Chat, adjust later)

- **Python setup** – use pyenv-win to install 3.11, then py -m venv .venv. Store dependencies in **pyproject.toml** (Poetry) or requirements.txt; pin torch, ctranslate2, llama-cpp-python (with --extra-index-url) for GPU builds.

- **Pre-commit** – black, isort. Run in dev.ps1.

- **Binary assets** – place GGUF models, Porcupine keyword files, Piper voices in models/ (git-ignored). Write a quantize.bat helper to convert .gguf from original checkpoints.
