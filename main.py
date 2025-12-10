from __future__ import annotations

import argparse
import datetime
import os
import queue
import tempfile
import threading
import time
import zipfile
from collections import defaultdict
from io import BytesIO
from typing import Any, Callable, Dict, List, Optional, Tuple

from ftplib import FTP

from logger import log, log_err, log_info, log_important
from path_utilities import is_valid_file, is_valid_path, read_file_safely
from result import Result

parser = argparse.ArgumentParser()
parser.add_argument("--file", action="store_true")
args = parser.parse_args()

paths: List[Dict[str, Any]] = []
event_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
last_events: Dict[str, Dict[str, Any]] = {}
num_watchers: int = 0

start_barrier: Optional[threading.Barrier] = None
end_barrier: Optional[threading.Barrier] = None


def main() -> None:
    """Main entry point for the synchronization program."""
    global num_watchers, start_barrier, end_barrier

    get_paths()
    if paths is None or len(paths) == 0:
        return

    num_watchers = len(paths)
    start_barrier = threading.Barrier(num_watchers + 1)
    end_barrier = threading.Barrier(num_watchers + 1)
    init_sync()

    for watcher_id, path in enumerate(paths, start=1):
        threading.Thread(
            target=watch_file,
            args=(path, event_queue, last_events, watcher_id),
            daemon=True,
        ).start()

    try:
        while True:
            # Wait for all watcher threads to reach the barrier
            if start_barrier is not None:
                start_barrier.wait()

            batch: List[Dict[str, Any]] = []
            last_events.clear()

            try:
                event = event_queue.get(timeout=1)
                batch.append(event)
            except queue.Empty:
                batch = []

            while True:
                try:
                    event = event_queue.get_nowait()
                    batch.append(event)
                except queue.Empty:
                    break

            if batch:
                handle_batch(batch)

            if end_barrier is not None:
                end_barrier.wait()

    except KeyboardInterrupt:
        log_info("Program stopped, stopping all watcher threads")


def parse_location(spec: str) -> Result:
    """Parse a location specification into a structured dictionary.

    Supported formats:
        - folder:/path/to/folder
        - zip:/path/to/archive.zip
        - ftp:username:password@host/path
    """
    spec = spec.strip()
    if not spec:
        return Result.Err("Empty path specification.")

    # FOLDER
    if spec.startswith("folder:"):
        folder_path = spec[len("folder:") :]
        try_dir = is_valid_path(folder_path)
        if not try_dir.ok:
            return Result.Err(try_dir.error)
        return Result.Ok(
            {
                "type": "folder",
                "path": try_dir.value,
            }
        )

    # ZIP
    if spec.startswith("zip:"):
        zip_path = spec[len("zip:") :]
        try_file = is_valid_file(zip_path)
        if not try_file.ok:
            return Result.Err(try_file.error)

        if not zipfile.is_zipfile(try_file.value):
            return Result.Err(f"Path is not a valid ZIP archive. [{zip_path}]")

        return Result.Ok(
            {
                "type": "zip",
                "path": try_file.value,
            }
        )

    # FTP
    if spec.startswith("ftp:"):
        ftp_spec = spec[len("ftp:") :]
        try:
            creds, rest = ftp_spec.split("@", 1)
            username, password = creds.split(":", 1)
            if "/" in rest:
                host, remote_path = rest.split("/", 1)
                remote_path = "/" + remote_path
            else:
                host = rest
                remote_path = "/"

            if not username or not password or not host:
                return Result.Err(f"Invalid FTP specification. [{spec}]")

            return Result.Ok(
                {
                    "type": "ftp",
                    "username": username,
                    "password": password,
                    "host": host,
                    "path": remote_path,
                }
            )
        except ValueError:
            return Result.Err(f"Invalid FTP specification. [{spec}]")

    return Result.Err(f"Unknown path type (expected folder:/zip:/ftp:). [{spec}]")


def get_paths() -> Optional[List[Dict[str, Any]]]:
    """Populate the global paths list either from a file or interactive input."""
    if args.file:
        line = input("Enter path for paths file: ")
        try_paths_file = is_valid_file(line)
        if not try_paths_file.ok:
            log_err(try_paths_file.error)
            return None

        try:
            data = read_file_safely(try_paths_file.value)
        except PermissionError as exc:
            log_err(f"Could not read paths file: {exc}")
            return None

        for ln in data.decode(errors="ignore").splitlines():
            ln = ln.strip()
            if not ln:
                continue

            parsed = parse_location(ln)
            if not parsed.ok:
                log_err(parsed.error)
                continue

            paths.append(parsed.value)

    else:
        while True:
            line = input("Enter path (folder:/zip:/ftp: or [end]): ")
            if line.strip().lower() == "end":
                break

            parsed = parse_location(line)
            if not parsed.ok:
                log_err(parsed.error)
                continue

            paths.append(parsed.value)

    return paths


def init_sync() -> None:
    """Perform an initial synchronization between all locations."""
    log_info("Finding latest files for initial sync.")
    latest_files = get_latest_files()

    log_info(
        "Syncing all to latest files:\n"
        + "\n".join(
            f"    [{rel_path}] from [{location['path']}] version "
            f"[{time.ctime(mtime)}]"
            for rel_path, (location, mtime) in latest_files.items()
        )
    )
    sync_to_latest(latest_files)


def get_latest_files() -> Dict[str, Tuple[Dict[str, Any], float]]:
    """Get the latest version of each file across all locations."""
    latest_files: Dict[str, Tuple[Dict[str, Any], float]] = {}
    for path in paths:
        files_in_path = ls(path)
        for rel_path, (loc_path, mtime) in files_in_path.items():
            if rel_path in latest_files:
                _, existing_mtime = latest_files[rel_path]
                if mtime > existing_mtime:
                    latest_files[rel_path] = (loc_path, mtime)
            else:
                latest_files[rel_path] = (loc_path, mtime)
    return latest_files


def sync_to_latest(latest_files: Dict[str, Tuple[Dict[str, Any], float]]) -> None:
    """Ensure each location has the latest version of every file."""
    for path in paths:
        files_in_path = ls(path)
        for rel_path, (latest_path, latest_mtime) in latest_files.items():
            if rel_path not in files_in_path:
                log(
                    f"File [{rel_path}] not found in [{path['path']}], "
                    f"writing latest from [{latest_path['path']}]"
                )
                write(rel_path, path, get_bytes(rel_path, latest_path))
            else:
                _, mtime = files_in_path[rel_path]
                if mtime < latest_mtime:
                    log(
                        "File [{rel_path}] from [{src}] [{src_time}] is behind latest, "
                        "writing from [{latest}] [{latest_time}]".format(
                            rel_path=rel_path,
                            src=path["path"],
                            src_time=time.ctime(mtime),
                            latest=latest_path["path"],
                            latest_time=time.ctime(latest_mtime),
                        )
                    )
                    write(rel_path, path, get_bytes(rel_path, latest_path))


def watch_file(
    path: Dict[str, Any],
    event_queue: "queue.Queue[Dict[str, Any]]",
    last_events: Dict[str, Dict[str, Any]],
    watcher_id: int,
) -> None:
    """Watch a single location for file changes and enqueue events."""
    global start_barrier, end_barrier

    prev = ls(path)
    log_info(f"Starting daemon watcher at {path['path']}")

    while True:
        curr = ls(path)

        prev_keys = set(prev.keys())
        curr_keys = set(curr.keys())

        # Updated files
        for rel_path in prev_keys & curr_keys:
            _, prev_mtime = prev[rel_path]
            _, curr_mtime = curr[rel_path]

            last_type = last_events.get(rel_path, {}).get("type")
            if curr_mtime > prev_mtime and last_type != "updated":
                event_queue.put(
                    {
                        "type": "updated",
                        "location": path,
                        "rel_path": rel_path,
                        "mtime": curr_mtime,
                    }
                )
                log(
                    f"T{watcher_id}-{time.time()} UPDATED File [{rel_path}] "
                    f"at [{path['path']}]"
                )

        # Deleted files
        for rel_path in prev_keys - curr_keys:
            last_type = last_events.get(rel_path, {}).get("type")
            if last_type == "deleted":
                continue

            event_queue.put(
                {
                    "type": "deleted",
                    "location": path,
                    "rel_path": rel_path,
                    "mtime": time.time(),
                }
            )
            log(
                f"T{watcher_id}-{time.time()} DELETED File [{rel_path}] "
                f"from [{path['path']}]"
            )

        # Created files
        for rel_path in curr_keys - prev_keys:
            last_type = last_events.get(rel_path, {}).get("type")
            if last_type == "created":
                continue

            _, new_mtime = curr[rel_path]
            event_queue.put(
                {
                    "type": "created",
                    "location": path,
                    "rel_path": rel_path,
                    "mtime": new_mtime,
                }
            )
            log(
                f"T{watcher_id}-{time.time()} CREATED File [{rel_path}] "
                f"at [{path['path']}]"
            )

        prev = curr

        if start_barrier is not None:
            start_barrier.wait()
        if end_barrier is not None:
            end_barrier.wait()


def handle_batch(events: List[Dict[str, Any]]) -> None:
    """Handle a batch of file events, resolving conflicts by latest mtime."""
    by_rel: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for ev in events:
        by_rel[ev["rel_path"]].append(ev)

    for rel_path, evs in by_rel.items():
        evs.sort(key=lambda e: e["mtime"])
        winner = evs[-1]
        types = {e["type"] for e in evs}

        last_events[rel_path] = winner

        if types == {"deleted"}:
            log_important(f"MAIN-{time.time()} DELETING {rel_path}")
            for loc in paths:
                delete(rel_path, loc)
        else:
            data = get_bytes(rel_path, winner["location"])
            log_important(f"MAIN-{time.time()} WRITING {rel_path}")
            for loc in paths:
                if loc is not winner["location"]:
                    write(rel_path, loc, data)


def ls(path: Dict[str, Any]) -> Dict[str, Tuple[Dict[str, Any], float]]:
    """List all files for a given path, returning relative path and mtime."""
    folder_list: Dict[str, Tuple[Dict[str, Any], float]] = {}

    if path["type"] == "folder":
        for root, _, files in os.walk(path["path"]):
            for file in files:
                full_path = os.path.join(root, file)
                modified = os.path.getmtime(full_path)
                rel_path = os.path.relpath(full_path, path["path"])
                folder_list[rel_path] = (path, modified)

    if path["type"] == "zip":
        zip_path = path["path"]

        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue

                rel_path = info.filename
                parts = rel_path.split("/", 1)
                if len(parts) == 2:
                    rel_path = parts[1]

                modified_ts = time.mktime(info.date_time + (0, 0, -1))
                folder_list[rel_path] = (path, modified_ts)

    if path["type"] == "ftp":
        ftp = FTP()
        ftp.connect(path["host"])
        ftp.login(path["username"], path["password"])

        base_remote = path["path"]

        def walk_ftp(current_remote_path: str) -> None:
            lines: List[str] = []
            ftp.retrlines("LIST " + current_remote_path, lines.append)

            for line in lines:
                parts = line.split(maxsplit=8)
                name = parts[-1]
                item_path = current_remote_path.rstrip("/") + "/" + name

                is_dir = line.startswith("d")

                if is_dir:
                    walk_ftp(item_path)
                else:
                    try:
                        resp = ftp.sendcmd("MDTM " + item_path)
                        ts = resp.split()[1]
                        mtime = parse_mdtm_to_unix(ts)
                    except Exception:
                        continue

                    rel_path = item_path[len(base_remote) :].lstrip("/")
                    folder_list[rel_path] = (path, mtime)

        walk_ftp(base_remote)
        ftp.quit()

    return folder_list


def write(rel_path: str, path: Dict[str, Any], bytes_data: bytes) -> bool:
    """Write bytes to the specified relative path in the given location."""
    if path["type"] == "folder":
        base = path["path"]
        dest = os.path.join(base, rel_path)

        os.makedirs(os.path.dirname(dest), exist_ok=True)

        with open(dest, "wb") as file_obj:
            file_obj.write(bytes_data)

        return True

    if path["type"] == "zip":
        zip_path = path["path"]
        zip_dir = os.path.dirname(zip_path)

        tmp_fd, tmp_name = tempfile.mkstemp(suffix=".zip", dir=zip_dir)
        os.close(tmp_fd)

        try:
            if os.path.exists(zip_path):
                with zipfile.ZipFile(zip_path, "r") as zin, zipfile.ZipFile(
                    tmp_name, "w", zipfile.ZIP_DEFLATED
                ) as zout:
                    for item in zin.infolist():
                        if item.filename == rel_path:
                            continue
                        data = zin.read(item.filename)
                        zout.writestr(item, data)

                    zout.writestr(rel_path, bytes_data)
            else:
                with zipfile.ZipFile(
                    tmp_name, "w", zipfile.ZIP_DEFLATED
                ) as zout:
                    zout.writestr(rel_path, bytes_data)

            os.replace(tmp_name, zip_path)
        finally:
            if os.path.exists(tmp_name) and not os.path.samefile(tmp_name, zip_path):
                try:
                    os.remove(tmp_name)
                except OSError:
                    log_err(f"OS Error when removing tmp zip file {tmp_name}")

        return True

    if path["type"] == "ftp":
        ftp = FTP()
        ftp.connect(path["host"])
        ftp.login(path["username"], path["password"])

        base_remote = path["path"].rstrip("/")

        rel = rel_path.replace("\\", "/")
        full_remote = base_remote + "/" + rel

        parts = rel.split("/")
        filename = parts[-1]
        folders = parts[:-1]

        current = base_remote
        for folder in folders:
            try:
                ftp.mkd(current + "/" + folder)
            except Exception:
                log_err(f"Problem when making dir in FTP {base_remote}")
            current = current + "/" + folder

        ftp.cwd(os.path.dirname(full_remote))

        bio = BytesIO(bytes_data)
        ftp.storbinary("STOR " + filename, bio)

        ftp.quit()
        return True

    raise ValueError(f"Unknown location type: {path['type']}")


def get_bytes(rel_path: str, path: Dict[str, Any]) -> bytes:
    """Read and return file contents as bytes from the given location."""
    if path["type"] == "folder":
        full_path = os.path.join(path["path"], rel_path)
        with open(full_path, "rb") as file_obj:
            return file_obj.read()

    if path["type"] == "zip":
        zip_path = path["path"]
        with zipfile.ZipFile(zip_path, "r") as zf:
            with zf.open(rel_path, "r") as file_obj:
                return file_obj.read()

    if path["type"] == "ftp":
        ftp = FTP()
        ftp.connect(path["host"])
        ftp.login(path["username"], path["password"])

        base_remote = path["path"].rstrip("/")
        rel = rel_path.replace("\\", "/")
        remote_full = base_remote + "/" + rel

        dirpart = os.path.dirname(remote_full)
        if dirpart:
            ftp.cwd(dirpart)

        buffer = BytesIO()
        filename = os.path.basename(remote_full)

        ftp.retrbinary("RETR " + filename, buffer.write)

        ftp.quit()
        return buffer.getvalue()

    raise ValueError(f"Unknown location type: {path['type']}")


def delete(rel_path: str, path: Dict[str, Any]) -> bool:
    """Delete the file at the given relative path in the specified location."""
    if path["type"] == "folder":
        full_path = os.path.join(path["path"], rel_path)
        if os.path.exists(full_path):
            os.remove(full_path)
        return True

    if path["type"] == "zip":
        zip_path = path["path"]
        zip_dir = os.path.dirname(zip_path)

        if not os.path.exists(zip_path):
            return True

        tmp_fd, tmp_name = tempfile.mkstemp(suffix=".zip", dir=zip_dir)
        os.close(tmp_fd)

        try:
            with zipfile.ZipFile(zip_path, "r") as zin, zipfile.ZipFile(
                tmp_name, "w", zipfile.ZIP_DEFLATED
            ) as zout:
                for item in zin.infolist():
                    if item.filename != rel_path:
                        data = zin.read(item.filename)
                        zout.writestr(item, data)

            os.replace(tmp_name, zip_path)

        except Exception:
            if os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except Exception:
                    log_err(
                        f"Problem deleting tmp zip file {tmp_name} at {zip_path}"
                    )
            raise

        return True

    if path["type"] == "ftp":
        ftp = FTP()
        ftp.connect(path["host"], 21)
        ftp.login(path["username"], path["password"])

        base_remote = path["path"].rstrip("/")
        rel = rel_path.replace("\\", "/")
        remote_full = base_remote + "/" + rel

        try:
            ftp.delete(remote_full)
        except Exception:
            log_err(f"File {rel} does not exist on ftp {base_remote}")

        ftp.quit()
        return True

    return False


def parse_mdtm_to_unix(ts: str) -> float:
    """Parse an FTP MDTM timestamp string into a Unix timestamp."""
    if "." in ts:
        dt = datetime.datetime.strptime(ts, "%Y%m%d%H%M%S.%f")
    else:
        dt = datetime.datetime.strptime(ts, "%Y%m%d%H%M%S")
    dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.timestamp()


if __name__ == "__main__":
    main()
