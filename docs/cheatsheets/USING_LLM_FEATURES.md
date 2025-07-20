# Using Solo's Enhanced LLM Features

This guide explains how to use the recently implemented LLM features in the Solo assistant.

## Model Management

The ModelManager automatically discovers and manages GGUF models in the `models/` directory.

### Available Models

To see what models are available on this system:

```bash
python -m app.core.model_info --verbose
```

This will show all detected models along with their metadata (parameter size, quantization level, format).

### Selecting a Model

Models can be selected in several ways:

1. **In config.py**: Update the `llm.model_path` setting
2. **Environment variable**: Set `SOLO_LLM_MODEL_PATH`
3. **Command line**: Pass `--model` to CLI tools

Example:
```bash
python -m app.core.llm_demo --model "models/mistral-7b-instruct-v0.2.Q4_K_M.gguf" --interactive
```

## Prompt Templates

Solo uses model-specific prompt templates to format inputs correctly for each model.

### Available Templates

Templates are available for several model families:
- Mistral
- Llama
- Phi
- Mixtral
- TinyLlama
- Default (fallback)

The system automatically detects which template to use based on the model filename.

### Customizing System Prompts

You can customize the system prompt in several ways:

1. **In config.py**: Update the `llm.system_prompt` setting
2. **Environment variable**: Set `SOLO_LLM_SYSTEM_PROMPT`
3. **Command line**: Pass `--system_prompt` to CLI tools

Example:
```bash
python -m app.core.llm_demo --system_prompt "You are a helpful AI assistant named Solo." --interactive
```

## Response Caching

Solo caches responses to avoid redundant computation, especially for common queries.

### Cache Management

Cache is automatically managed, but you can:

1. **Clear the cache**:
```bash
python -c "from app.core.model_cache import ResponseCache; ResponseCache().clear_cache()"
```

2. **Change TTL**: Modify `llm.cache_ttl` in config.py (in seconds)

3. **Disable caching**: Set `llm.use_cache = False` in config.py

## Conversation History

Solo keeps track of conversation history to maintain context across multiple turns.

### Managing History

1. **Clear history** in interactive mode: Type `/clear` in the CLI tools
2. **Disable history**: Set `llm.use_conversation_history = False` in config.py

## Interactive Testing

The CLI tester provides an interactive environment to test the LLM functionality:

```bash
python -m app.core.llm_tester
```

### Commands

- `/help`: Show available commands
- `/clear`: Clear conversation history
- `/exit` or `/quit`: Exit the tester
- `/params`: Show current parameters
- `/set <param> <value>`: Change a parameter

### Parameters

Adjustable parameters include:
- `temperature`: Controls randomness (0.0-1.0)
- `top_p`: Controls diversity (0.0-1.0)
- `max_tokens`: Maximum response length
- `context_window`: Size of context window in tokens
- `system_prompt`: The system prompt to use

## Demo Mode

For a simpler testing experience, use the demo mode:

```bash
python -m app.core.llm_demo --interactive
```

This provides a more streamlined interface with fewer options.

## Integration in Applications

To use the LLM in code:

```python
from app.core.llm_runner import LLMRunner
from app.config import get_config

config = get_config()
llm = LLMRunner(config)

response = await llm.generate_response("Tell me a joke")
print(response)
```

## VS Code Tasks

Several VS Code tasks are available to make development easier:

1. **Run Main Application**: Launches the main Solo application
2. **Run LLM Demo**: Starts the interactive LLM demo
3. **Show Available Models**: Lists all detected models
4. **Run LLM Tester**: Starts the interactive LLM tester
5. **Clear Cache**: Clears the response cache

Access these by pressing `Ctrl+Shift+P` and typing "Tasks: Run Task".
