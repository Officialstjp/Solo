# Solo

Solo is a local-first voice assistant that combines speech recognition, text-to-speech and a lightweight large language model. The application is organised as a set of micro‑services under the `app/` folder with `main.py` acting as an async supervisor. A FastAPI server exposes REST and WebSocket endpoints while a Streamlit dashboard provides runtime metrics.

## Key Components
- **STT** – real-time transcription using faster-whisper.
- **TTS** – voice output powered by Piper.
- **LLM Runner** – llama.cpp or Ollama backend with optional GPU support.
- **Memory** – Chroma vector database for retrieval‑augmented generation.
- **Agent Bus** – CrewAI orchestration for multi‑agent workflows.

## Setup
1. Install Python 3.11.
2. Run `scripts/dev.ps1` (PowerShell) to create a virtual environment and install dependencies from `requirements.txt`.
3. Copy `.env.example` to `.env` and adjust any settings.
4. Start the assistant with `pwsh scripts/run_agent.ps1` or run `python app/main.py` directly.

Refer to `Solo - System Architecture Concept.md` for detailed architecture information and the development timeline.
