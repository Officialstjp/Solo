
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
## 4. Development Timeline

| Week | Milestone              | Deliverables                                                                                                        |
| ---- | ---------------------- | ------------------------------------------------------------------------------------------------------------------- |
| 0-1  | Repo bootstrap         | Folder skeletion, pyenv install, requirements.txt, pre-commit hooks						      |
| 2    | Core manager & logging | main.py event loop, JSON logger, stub event classes                                                                 |
| 3    | LLM runner wrapper     | Build llama.cpp with cuBLAS on Win11; load 7 B quant model; CLI demo echo                                           |
| 4    | STT mini-pipeline      | Integrate faster-whisper; wav/MP3 input -> text; hot-key starts/stop capture                                        |
| 5    | TTS output             | Piper inference; voice selection by config; test round-trip latency                                                 |
| 6    | API layer              | FastAPI routes /chat /transcribe /status; backround tasks and websockets                                            |
| 7    | Dashboard v1           | Streamlit panel reading /status; shoy token/s queue lengths, audio VU Meter                                         |
| 8    | Memory / RAG           | Chroma embedded DB; file-drop folder ingester; similarity search endpoint                                           |
| 9    | Agent bus              | CrewAI "plan -> execute -> critique" loop; task example: summarize PDF to memory                                    |
| 10   | Wake-word & packaging  | Porcupine integration; Powershell installer and run_agent.ps1 launcher                                              |

After 10 weeks we'll look at our Status and work on nice-to-haves, if all is well (OAuth, VM-Lab hooks (Package, e.g.?), support for multi-GPU, containerization)


## 5. Environment & CI Details
(provided by Chat, adjust later)

- **Python setup** – use pyenv-win to install 3.11, then py -m venv .venv. Store dependencies in **pyproject.toml** (Poetry) or requirements.txt; pin torch, ctranslate2, llama-cpp-python (with --extra-index-url) for GPU builds.

- **Pre-commit** – black, isort. Run in dev.ps1.
   
- **Binary assets** – place GGUF models, Porcupine keyword files, Piper voices in models/ (git-ignored). Write a quantize.bat helper to convert .gguf from original checkpoints.
   
