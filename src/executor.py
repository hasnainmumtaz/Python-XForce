"""Execute user code in a shared namespace. Returns (result, stdout, stderr)."""

import ast
import io
import sys


def execute_code(source: str, namespace: dict) -> tuple:
    """
    Execute source in namespace. Returns (result, stdout_str, stderr_str).
    result is the value of the last expression if the source is a single expression, else None.
    """
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    try:
        sys.stdout = out_buf
        sys.stderr = err_buf
        try:
            tree = ast.parse(source)
            if (
                len(tree.body) == 1
                and isinstance(tree.body[0], ast.Expr)
            ):
                value = eval(compile(ast.Expression(body=tree.body[0].value), "<input>", "eval"), namespace)
                return (value, out_buf.getvalue(), err_buf.getvalue())
        except SyntaxError:
            pass
        exec(compile(source, "<input>", "exec"), namespace)
        return (None, out_buf.getvalue(), err_buf.getvalue())
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
