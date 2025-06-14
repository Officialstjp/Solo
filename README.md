# Solo

Solo is a local-first voice assistant that combines speech recognition, text-to-speech and a lightweight large language model. The application is organised as a set of micro‑services under the `app/` folder with `main.py` acting as an async supervisor. A FastAPI server exposes REST and WebSocket endpoints while a Streamlit dashboard provides runtime metrics.

## Key Components
- **LLM Runner** – llama.cpp backend with GPU support - ✅ Initial implementation
- **Event Bus** - Asynchronous event-based communication between components - ✅ Implemented
- **CLI Tester** - Interactive testing interface for LLM functionality - ✅ In progress
- **STT** – real-time transcription using faster-whisper - ⏳ Planned
- **TTS** – voice output powered by Piper - ⏳ Planned
- **Memory** – Chroma vector database for retrieval‑augmented generation - ⏳ Planned
- **Agent Bus** – CrewAI orchestration for multi‑agent workflows - ⏳ Planned
- **Dashboard UI** - Streamlit metrics display - ⏳ Planned

## Implementation Status
The project is currently focused on core LLM functionality:
- ✅ Event bus architecture for component communication
- ✅ Base LLM runner with llama.cpp integration
- ✅ Interactive testing CLI for LLM
- 🔄 Improving CLI experience and interaction flow
- ⏳ Speech components (STT/TTS) and additional features to follow

## Setup
1. Install Python 3.11 or later (supports up to 3.13).
2. Run `scripts/setup-dev.ps1` (PowerShell) to create a virtual environment and install dependencies.
3. Download a compatible GGUF model to the `models/` directory (currently using TinyLlama 1.1B).
4. Start the assistant with `pwsh scripts/run_agent.ps1` or run `python app/main.py` directly.

## Development
- Use the interactive LLM tester to try out prompts: `python -m app.main`
- For a simpler demo: `python -m app.core.llm_demo --model "[model_path]" --interactive`

Refer to `docs/Solo - System Architecture Concept.md` for detailed architecture information and the development roadmap.
