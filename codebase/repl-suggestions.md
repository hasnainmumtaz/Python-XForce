# REPL and suggestions

This doc describes the TUI REPL loop, suggestion pipeline, ghost text, and execution so future changes don’t break the flow.

## Flow overview

1. **Entrypoint**: `xforce.py` calls `run_repl()` from `src/repl.py`.
2. **REPL loop** (`src/repl.py`): Uses `prompt_toolkit.PromptSession` to read input with `>>>` / `...` prompts. Multi-line input is collected until `ast.parse(text)` succeeds. Then `src/executor.execute_code(text, namespace)` runs the code in the same Python process and prints result/stdout/stderr.
3. **Suggestions**: The session is created with `auto_suggest=ThreadedAutoSuggest(CodeSuggestAutoSuggest(...))`. As the user types, `CodeSuggestAutoSuggest.get_suggestion(buffer, document)` is called (possibly in a thread). It returns a `Suggestion(continuation_text)` for ghost text; Tab or Right Arrow accepts it.
4. **Suggestion pipeline** (`src/suggestions.py`): A background thread runs a debounced (0.35s) request: it calls a provider (Jedi or LLM) with `(document.text, document.cursor_position)` and caches the continuation string. `get_suggestion` returns the cached suggestion for the current `(text, cursor_position)` and notifies the worker to refresh. Provider choice: if `OPENAI_API_KEY` is set (via `src/config.get_config()`), `_llm_completion` is used; otherwise `_jedi_completion`.
5. **Execution** (`src/executor.py`): Code is run with `exec(compile(...), namespace)`. If the source is a single expression, it is `eval`’d and the value is returned for the REPL to print.

## Key files

| File | Role |
|------|------|
| `xforce.py` | Entrypoint; imports `src.repl.run_repl`. |
| `src/repl.py` | REPL loop, prompt_toolkit session, multi-line collection, execution and print. |
| `src/executor.py` | `execute_code(text, namespace)` → (result, stdout, stderr); expression vs exec. |
| `src/suggestions.py` | `CodeSuggestAutoSuggest` (debounced cache + worker), `_jedi_completion`, `_llm_completion`, `get_suggestion_provider()`. |
| `src/config.py` | `get_config()` → `openai_api_key`, `openai_model` from env and optional config file. |

## Changing behavior without breaking things

- **Add a new suggestion provider**: Implement a `(text, cursor_position) -> str | None` function and plug it into `get_suggestion_provider()` in `src/suggestions.py` (e.g. prefer LLM if key set, else Jedi, else new provider).
- **Change debounce**: Pass a different `debounce_sec` to `CodeSuggestAutoSuggest` in `src/repl.py`.
- **Change execution**: Only `src/executor.py` runs user code; keep namespace handling and stdout/stderr capture there.
- **Config**: All config is read via `src/config.get_config()`; add new keys in `config.py` and in the optional config file parsing.
