#!/usr/bin/env python3
"""Entrypoint for the Python REPL with code suggestions. Run instead of `python` for suggestions."""

from src.repl import run_repl


def main() -> None:
    run_repl()


if __name__ == "__main__":
    main()
