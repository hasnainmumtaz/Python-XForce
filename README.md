# xforce — Python REPL with code suggestions

A custom Python REPL that uses your installed Python (e.g. 3.13.x) and adds **code suggestions** as you type: ghost text you can accept with **Tab** or **Right Arrow**.

- **Without API key**: Jedi-based completions (identifiers, attributes).
- **With OpenAI API key**: LLM-powered line completions (optional).

Same Python interpreter as your `python.exe`; run this instead of `python` when you want suggestions.

## Install for command-line use (optional)

To run **`python-xforce`** from any directory:

1. From the project root, install in editable mode:

   ```bash
   pip install -e .
   ```

2. Start the REPL from anywhere:

   ```bash
   python-xforce
   ```

   **Windows:** If `python-xforce` is not recognized, the installer put the script in your user Python `Scripts` folder (e.g. `%APPDATA%\Python\Python313\Scripts`). Add that folder to your [user PATH](https://learn.microsoft.com/en-us/windows/win32/procthread/environment-variables). Or use **`python -m xforce`** instead; it works without changing PATH.

   **Linux/macOS:** The script is typically installed to a directory already on PATH (e.g. `~/.local/bin`). If not, add that directory to PATH or use **`python -m xforce`**.

## Run with your Python (e.g. 3.13.x)

If you prefer not to install, run from the project:

1. Create a virtualenv (recommended) and install dependencies:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate  # Linux/macOS
   pip install -r requirements.txt
   ```

2. Start the REPL from the project root:

   ```bash
   python xforce.py
   ```

   (Run from the directory that contains `xforce.py` and the `src` folder, or set `PYTHONPATH` to that directory.)

3. Type code at the `>>>` prompt. Suggestions appear as dim/italic ghost text after the cursor. Press **Right Arrow** or **Tab** to accept.
   - **Jedi** (no API key): ghost text appears as you type.
   - **LLM** (with API key): ghost text may appear after a short pause (~0.3s); if not, press **Right Arrow** once to refresh.
   - If you don’t see ghost text, try running in **Windows Terminal** or another terminal that supports dim/bright colors; the suggestion is only shown when the cursor is at the end of the line.

## Config (optional — for LLM suggestions)

- **Config file only**: xforce reads **only** from the config file. Environment variables are **not** used unless you explicitly allow them in the config.

  xforce looks for config in this order (first found wins):
  1. `~/.xforce_config` (your home directory)
  2. `.xforce` in the current working directory (e.g. project root)

  To set up: copy the example and add your key:

  ```bash
  copy xforce_config.example %USERPROFILE%\.xforce_config   # Windows
  # cp xforce_config.example ~/.xforce_config               # Linux/macOS
  # Then edit and set openai_api_key=sk-... (your real key)
  ```

  Format (key=value, one per line; lines starting with # are comments):

  ```
  openai_api_key=sk-...
  openai_model=gpt-4o-mini
  ```

- **Optional: allow env vars**: If you want `OPENAI_API_KEY` and `OPENAI_MODEL` to be read from the environment (and override the file), add to your config:

  ```
  use_env_vars=true
  ```

If no API key is set (in the config, or in env when allowed), the REPL uses **Jedi** only (no API calls).

## Requirements

- Python 3.10+
- `prompt_toolkit`, `jedi` (required)
- `openai` (required only if you use LLM suggestions)
