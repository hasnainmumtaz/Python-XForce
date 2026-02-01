"""LLM and Jedi suggestion providers; debounced AutoSuggest for ghost text."""

import threading
import time
from typing import Callable

from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.document import Document

from src.config import get_config

# Jedi is fast enough to call synchronously so ghost text appears immediately.
# LLM is slow, so we use a debounced worker and cache (suggestion appears after next keypress or short wait).
_USE_JEDI_SYNC = True


def _jedi_completion(text: str, cursor_position: int) -> str | None:
    """Return continuation string from Jedi completions (suffix to insert), or None."""
    try:
        import jedi
    except ImportError:
        return None
    try:
        script = jedi.Script(text, path="<input>")
        before = text[:cursor_position]
        lines = before.split("\n")
        line = len(lines)  # 1-based
        column = len(lines[-1]) if lines else 0  # 0-based
        completions = script.complete(line, column)
        if not completions:
            return None
        c = completions[0]
        # Jedi Completion.complete is the suffix to insert (e.g. "ad" for "load")
        return getattr(c, "complete", None) or c.name
    except Exception:
        return None


def _llm_completion(
    text: str,
    cursor_position: int,
    session_context: dict | None = None,
) -> str | None:
    """Return continuation string from LLM API, or None. session_context can include defined_names, recent_lines."""
    config = get_config()
    api_key = config.get("openai_api_key") or ""
    if not api_key:
        return None
    model = config.get("openai_model") or "gpt-4o-mini"
    max_tokens = config.get("openai_max_tokens") or 120
    before_cursor = text[:cursor_position]
    after_cursor = text[cursor_position:]
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        context_parts = []
        if session_context:
            names = session_context.get("defined_names")
            if names:
                context_parts.append(f"Names already defined in this REPL session (use these in suggestions): {', '.join(sorted(names)[:80])}")
            recent = session_context.get("recent_lines")
            if recent:
                context_parts.append("Recently executed code (for context):\n" + "\n".join(recent[-12:]))
        context_block = "\n\n".join(context_parts) + "\n\n" if context_parts else ""
        prompt = (
            "You suggest code to insert AFTER the cursor only. Do NOT repeat anything that is already before the cursor.\n\n"
            + context_block
            + "Text BEFORE cursor (already typed, do not repeat):\n"
            f"{before_cursor!r}\n\n"
            "Text AFTER cursor (if any):\n"
            f"{after_cursor!r}\n\n"
            "Return ONLY the new text to INSERT at the cursor (the continuation). "
            "You MAY return multiple lines (e.g. a function body, loop body, or block). "
            "E.g. if before cursor is 'def ', return 'my_func():\\n    return 1' or similar—never repeat 'def'. "
            "If the user is typing a name that matches a defined name, suggest that (e.g. 'hello' -> 'hello()'). "
            "If nothing to add, return empty."
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        content = (resp.choices[0].message.content or "").strip()
        # Allow multi-line; strip wrapping quotes only if content is a single line
        if "\n" not in content:
            if content.startswith('"') and content.endswith('"'):
                content = content[1:-1].replace('\\"', '"')
            elif content.startswith("'") and content.endswith("'"):
                content = content[1:-1].replace("\\'", "'")
        # Strip overlapping prefix from the first line only (so multi-line stays intact)
        if before_cursor and content:
            first_line, _, rest = content.partition("\n")
            if first_line.startswith(before_cursor):
                first_line = first_line[len(before_cursor):]
            elif before_cursor.rstrip() and first_line.startswith(before_cursor.rstrip()):
                first_line = first_line[len(before_cursor.rstrip()):]
            content = first_line + ("\n" + rest if rest else "")
        if not content.strip():
            return None
        return content
    except Exception as e:
        raise _LLMError(str(e)) from e


class _LLMError(Exception):
    """Raised when the LLM provider fails; caught in worker and stored for toolbar."""

    pass


def get_suggestion_provider() -> Callable[[str, int], str | None]:
    """Return a function (text, cursor_position) -> continuation or None. Prefers LLM if configured, else Jedi."""
    config = get_config()
    if (config.get("openai_api_key") or "").strip():
        return _llm_completion
    return _jedi_completion


class CodeSuggestAutoSuggest(AutoSuggest):
    """AutoSuggest that shows code completions (Jedi or LLM). Jedi runs sync for instant ghost text; LLM uses debounced cache."""

    def __init__(self, debounce_sec: float = 0.15):
        self._get_suggestion = get_suggestion_provider()
        self._debounce_sec = debounce_sec
        self._lock = threading.Lock()
        self._request: tuple[str, int] | None = None
        self._cache: dict[tuple[str, int], str] = {}
        self._cv = threading.Condition()
        self._use_llm = (get_config().get("openai_api_key") or "").strip() != ""
        self._refresh_callback: Callable[[], None] | None = None
        self._get_session_context: Callable[[], dict | None] | None = None
        self._last_llm_error: str | None = None  # Shown in toolbar when OpenAI fails
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def set_session_context(self, get_context: Callable[[], dict | None] | None) -> None:
        """Set a callable that returns REPL context (defined_names, recent_lines) for better LLM suggestions."""
        self._get_session_context = get_context

    def set_refresh_callback(self, callback: Callable[[], None] | None) -> None:
        """Call this so we can trigger a re-request when the LLM cache updates (so ghost text appears without typing again)."""
        self._refresh_callback = callback

    def _worker(self) -> None:
        while True:
            with self._cv:
                self._cv.wait()
                request = self._request
            if request is None:
                continue
            time.sleep(self._debounce_sec)
            with self._lock:
                if self._request != request:
                    continue
            try:
                if self._use_llm and self._get_session_context:
                    ctx = self._get_session_context()
                    result = _llm_completion(request[0], request[1], ctx)
                else:
                    result = self._get_suggestion(request[0], request[1])
            except _LLMError as e:
                result = None
                self._last_llm_error = str(e)
            else:
                self._last_llm_error = None
            with self._lock:
                if result is not None:
                    self._cache[request] = result
                elif request in self._cache:
                    del self._cache[request]
                if len(self._cache) > 2:
                    self._cache = {k: v for k, v in list(self._cache.items())[-2:]}
            # So ghost text appears without typing again (LLM path).
            if result is not None and self._refresh_callback:
                try:
                    self._refresh_callback()
                except Exception:
                    pass

    def get_last_llm_error(self) -> str | None:
        """Return the last OpenAI/LLM error message, if any (for toolbar)."""
        return self._last_llm_error

    def get_current_suggestion_text(self, document: Document) -> str | None:
        """Return the suggestion text for this document (for toolbar). Uses cache or Jedi sync."""
        request = (document.text, document.cursor_position)
        if not document.text.strip():
            return None
        if _USE_JEDI_SYNC and not self._use_llm:
            return self._get_suggestion(document.text, document.cursor_position)
        with self._lock:
            return self._cache.get(request)

    def get_suggestion(self, buffer, document: Document) -> Suggestion | None:
        request = (document.text, document.cursor_position)
        # Jedi path: call synchronously so ghost text appears immediately (no debounce).
        if _USE_JEDI_SYNC and not self._use_llm:
            result = self._get_suggestion(document.text, document.cursor_position)
            if result:
                return Suggestion(result)
            return None
        # LLM path: use debounced cache; suggestion may appear after next keypress.
        with self._lock:
            cached = self._cache.get(request)
        with self._cv:
            self._request = request
            self._cv.notify()
        if cached:
            return Suggestion(cached)
        return None
