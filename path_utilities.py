from pathlib import Path
import time
from result import Result

def is_valid_path(path: str) -> Result:
    try:
        p = Path(path)
        if not p.is_dir():
            return Result.Err(f"Path is not directory. [{path}]")
        return Result.Ok(Path(path))
    except Exception:
        return Result.Err(f"Path is not valid. [{path}]")
    
def is_valid_file(path: str) -> Result:
    try:
        p = Path(path)
        if not p.is_file():
            return Result.Err(f"Path is not file. [{path}]")
        return Result.Ok(Path(path))
    except Exception:
        return Result.Err(f"Path is not valid. [{path}]")
    
def read_file_safely(path, retries=10, delay=0.05):
    last_err = None
    for _ in range(retries):
        try:
            with open(path, "rb") as f:
                return f.read()
        except PermissionError as e:
            last_err = e
            time.sleep(delay)
    raise last_err