from __future__ import annotations

"""Simple logging utilities with colored console output."""

from enum import Enum


class Color(str, Enum):
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"


def paint(text: str, color: Color) -> str:
    """Return the given text wrapped in ANSI color codes.

    Args:
        text: The text to colorize.
        color: The color to apply.

    Returns:
        The colorized text.
    """
    return f"{color}{text}{Color.RESET}"


def log(msg: str) -> None:
    """Log a general message."""
    print(paint(f"[LOG] {msg}", Color.YELLOW))


def log_info(msg: str) -> None:
    """Log an informational message."""
    print(paint(f"[INFO] {msg}", Color.BLUE))


def log_err(msg: str) -> None:
    """Log an error message."""
    print(paint(f"[ERR] {msg}", Color.RED))


def log_important(msg: str) -> None:
    """Log an important message."""
    print(paint(f"[IMPORTANT] {msg}", Color.MAGENTA))
