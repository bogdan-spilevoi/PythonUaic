from pathlib import Path
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