"""REPL loop using prompt_toolkit. Reads input, executes in same Python, prints result."""

import ast
import sys
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import ThreadedAutoSuggest
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.application import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

from src.executor import execute_code
from src.suggestions import CodeSuggestAutoSuggest

# Make suggestion (ghost) text visible in more terminals (default #666666 can disappear)
REPL_STYLE = Style.from_dict({"auto-suggestion": "#888888 italic", "bottom-toolbar": "#888888 bg:#222222"})


def _get_prompt(continuation: bool = False) -> str:
    return "... " if continuation else ">>> "


def _bottom_toolbar(session: PromptSession, suggester: CodeSuggestAutoSuggest | None) -> HTML:
    """Show current suggestion in toolbar (from buffer or directly from suggester), or OpenAI error."""
    try:
        buf = session.default_buffer
        if suggester:
            err = suggester.get_last_llm_error()
            if err:
                escaped = err.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")[:120]
                return HTML('<style fg="#ff8888">OpenAI error:</style> ' + escaped)
        text = None
        if buf.suggestion and buf.suggestion.text:
            text = buf.suggestion.text
        if not text and suggester:
            text = suggester.get_current_suggestion_text(buf.document)
        if text:
            if "\n" in text:
                first_line, rest = text.split("\n", 1)
                n_more = rest.count("\n") + 1
                display = first_line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") + f" <style fg=\"#888888\">(+{n_more} lines)</style>"
            else:
                display = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            return HTML('<style fg="#88ff88">Suggestion:</style> <b>' + display + '</b>  <style fg="#888888">Right / Tab to accept</style>')
    except Exception:
        pass
    return HTML("")


def run_repl() -> None:
    """Run the REPL loop: read input, execute with same interpreter, print result."""
    history = InMemoryHistory()
    suggester = CodeSuggestAutoSuggest(debounce_sec=0.15)

    # Tab to accept suggestion (prompt_toolkit only binds Right/Ctrl-F/Ctrl-E by default)
    tab_accept_bindings = KeyBindings()

    @Condition
    def suggestion_available() -> bool:
        app = get_app()
        buf = app.current_buffer
        if not buf.document.is_cursor_at_the_end:
            return False
        if buf.suggestion and buf.suggestion.text:
            return True
        if suggester and suggester.get_current_suggestion_text(buf.document):
            return True
        return False

    @tab_accept_bindings.add("tab", filter=suggestion_available)
    def _accept_suggestion_on_tab(event) -> None:
        buf = event.current_buffer
        if buf.suggestion and buf.suggestion.text:
            buf.insert_text(buf.suggestion.text)
            return
        if suggester:
            text = suggester.get_current_suggestion_text(buf.document)
            if text:
                buf.insert_text(text)

    @tab_accept_bindings.add("tab", filter=~suggestion_available)
    def _insert_indent_on_tab(event) -> None:
        """Insert 4 spaces when Tab is pressed and there is no suggestion to accept."""
        event.current_buffer.insert_text("    ")

    session = PromptSession(
        history=history,
        auto_suggest=ThreadedAutoSuggest(suggester),
        style=REPL_STYLE,
        bottom_toolbar=lambda: _bottom_toolbar(session, suggester),
        key_bindings=tab_accept_bindings,
    )

    def _request_suggestion_refresh() -> None:
        """Ask prompt_toolkit to re-request the suggestion so ghost text appears after LLM cache updates."""
        session.app.create_background_task(session.default_buffer._async_suggester())

    suggester.set_refresh_callback(_request_suggestion_refresh)

    namespace = {"__name__": "__main__"}
    recent_executed: list[str] = []  # Last N executed code lines/blocks for LLM context
    _RECENT_MAX_LINES = 20

    def _session_context() -> dict:
        """Build REPL context for LLM: defined names and recently executed code."""
        defined = [k for k in namespace.keys() if not k.startswith("__")]
        return {
            "defined_names": defined,
            "recent_lines": list(recent_executed[-_RECENT_MAX_LINES:]),
        }

    suggester.set_session_context(_session_context)

    # Banner
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"Python {version} (xforce REPL with suggestions)")
    print('Type "exit()" or Ctrl-D to quit.')

    while True:
        try:
            try:
                text = session.prompt(_get_prompt(False))
            except EOFError:
                break
            if not text.strip():
                continue

            # Collect multi-line input (e.g. "def f():", "    return 1", then empty line)
            while True:
                try:
                    ast.parse(text)
                    break
                except SyntaxError:
                    # After a line ending with ":", default to 4 spaces so user gets automatic indent
                    default_more = "    " if text.rstrip().endswith(":") else ""
                    try:
                        more = session.prompt(_get_prompt(True), default=default_more)
                    except EOFError:
                        more = ""
                    # Empty line = user is done; break out and let execute_code show any error
                    if not more.strip():
                        break
                    # Auto-indent: if previous line ends with ":" and user didn't indent, prepend 4 spaces
                    if text.rstrip().endswith(":") and more and not more[0].isspace():
                        more = "    " + more
                    text += "\n" + more

            result, out, err = execute_code(text, namespace)
            if err:
                print(err, end="", file=sys.stderr)
            if out:
                print(out, end="")
            if result is not None:
                print(repr(result))
            # Keep recent executed code for LLM context (split into lines, cap total)
            for line in text.strip().splitlines():
                recent_executed.append(line.strip())
            while len(recent_executed) > _RECENT_MAX_LINES:
                recent_executed.pop(0)

        except KeyboardInterrupt:
            print("KeyboardInterrupt")
        except Exception as e:
            print(f"{type(e).__name__}: {e}")

    print("Goodbye!")
