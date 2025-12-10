from __future__ import annotations

"""Utility helpers for working with filesystem paths."""

import time
from pathlib import Path
from typing import Union

from result import Result


def is_valid_path(path: Union[str, Path]) -> Result:
    """Validate that the given path is an existing directory.

    Args:
        path: The path to validate.

    Returns:
        Result.Ok(Path) if the path is a directory, otherwise Result.Err(str).
    """
    try:
        path_obj = Path(path)
        if not path_obj.is_dir():
            return Result.Err(f"Path is not directory. [{path}]")
        return Result.Ok(path_obj)
    except Exception:
        return Result.Err(f"Path is not valid. [{path}]")


def is_valid_file(path: Union[str, Path]) -> Result:
    """Validate that the given path is an existing file.

    Args:
        path: The path to validate.

    Returns:
        Result.Ok(Path) if the path is a file, otherwise Result.Err(str).
    """
    try:
        path_obj = Path(path)
        if not path_obj.is_file():
            return Result.Err(f"Path is not file. [{path}]")
        return Result.Ok(path_obj)
    except Exception:
        return Result.Err(f"Path is not valid. [{path}]")


def read_file_safely(
    path: Union[str, Path],
    retries: int = 10,
    delay: float = 0.05,
) -> bytes:
    """Read a file with retries on PermissionError.

    Args:
        path: Path to the file to read.
        retries: Number of attempts before giving up.
        delay: Delay (in seconds) between retries.

    Returns:
        The contents of the file as bytes.

    Raises:
        PermissionError: If the file cannot be read after all retries.
    """
    last_err: PermissionError | None = None

    for _ in range(retries):
        try:
            with open(path, "rb") as file_obj:
                return file_obj.read()
        except PermissionError as exc:
            last_err = exc
            time.sleep(delay)

    if last_err is not None:
        raise last_err

    # This should be unreachable, but keeps type-checkers happy.
    raise PermissionError(f"Could not read file: {path}")
