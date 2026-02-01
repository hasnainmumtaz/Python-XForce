# Codebase overview

This project is a custom Python REPL with LLM-powered code suggestions.

## Documentation

- [REPL and suggestions](repl-suggestions.md) – TUI REPL loop, suggestion pipeline, ghost text, execution.

## Key areas

- **Entrypoint**: `xforce.py` – run this instead of `python` for the enhanced REPL.
- **REPL core**: `src/repl.py` – main loop, prompt_toolkit session, execution.
- **Suggestions**: `src/suggestions.py` – LLM provider, debounced cache.
- **Config**: `src/config.py` – API key and model (env / file).
