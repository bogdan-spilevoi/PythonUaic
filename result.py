from __future__ import annotations

"""Simple Result type to represent success or failure of operations."""

from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass
class Result(Generic[T, E]):
    """Represents the result of an operation.

    Attributes:
        ok: True if the operation succeeded, False otherwise.
        value: The value produced on success.
        error: The error produced on failure.
    """

    ok: bool
    value: Optional[T] = None
    error: Optional[E] = None

    @staticmethod
    def Ok(value: Optional[T] = None) -> "Result[T, E]":
        """Create a successful result.

        Args:
            value: The value to store in the result.

        Returns:
            A Result instance representing success.
        """
        return Result(True, value=value)

    @staticmethod
    def Err(error: E) -> "Result[T, E]":
        """Create a failed result.

        Args:
            error: The error to store in the result.

        Returns:
            A Result instance representing failure.
        """
        return Result(False, error=error)

    def __repr__(self) -> str:
        """Return a string representation of the result."""
        if self.ok:
            return f"Ok({self.value})"
        return f"Err({self.error})"
