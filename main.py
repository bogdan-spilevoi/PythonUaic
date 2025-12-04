import os
from pathlib import Path
import zipfile
from path_utilities import is_valid_path, is_valid_file, read_file_safely
import argparse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
from handlers import Handler
from result import Result

parser = argparse.ArgumentParser()
parser.add_argument("--file", action="store_true")
args = parser.parse_args()

observer = Observer()
handlers = []
paths = []

def main():

    get_paths()
    if(paths == None or len(paths) == 0):
        return
    
    print(paths)
    init_handlers(paths)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_observer()


def parse_location(spec: str) -> Result:
    spec = spec.strip()
    if not spec:
        return Result.Err("Empty path specification.")

    # FOLDER
    if spec.startswith("folder:"):
        folder_path = spec[len("folder:"):]
        try_dir = is_valid_path(folder_path)
        if not try_dir.ok:
            return Result.Err(try_dir.error)
        return Result.Ok({
            "type": "folder",
            "path": try_dir.value, 
        })

    # ZIP
    if spec.startswith("zip:"):
        zip_path = spec[len("zip:"):]
        try_file = is_valid_file(zip_path)
        if not try_file.ok:
            return Result.Err(try_file.error)

        if not zipfile.is_zipfile(try_file.value):
            return Result.Err(f"Path is not a valid ZIP archive. [{zip_path}]")

        return Result.Ok({
            "type": "zip",
            "path": try_file.value,
        })

    # FTP
    if spec.startswith("ftp:"):
        ftp_spec = spec[len("ftp:"):]
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

            return Result.Ok({
                "type": "ftp",
                "username": username,
                "password": password,
                "host": host,
                "path": remote_path,
            })
        except ValueError:
            return Result.Err(f"Invalid FTP specification. [{spec}]")

    return Result.Err(f"Unknown path type (expected folder:/zip:/ftp:). [{spec}]")


def get_paths():
    if args.file:
        line = input("Enter path for paths file: ")
        try_paths_file = is_valid_file(line)
        if not try_paths_file.ok:
            print(try_paths_file.error)
            return None

        try:
            data = read_file_safely(try_paths_file.value)
        except PermissionError as e:
            print(f"Could not read paths file: {e}")
            return None

        for ln in data.decode(errors="ignore").splitlines():
            ln = ln.strip()
            if not ln:
                continue

            parsed = parse_location(ln)
            if not parsed.ok:
                print(parsed.error)
                continue

            paths.append(parsed.value)

    else:
        while True:
            line = input("Enter path (folder:/zip:/ftp: or [end]): ")
            if line.strip().lower() == "end":
                break

            parsed = parse_location(line)
            if not parsed.ok:
                print(parsed.error)
                continue

            paths.append(parsed.value)

    return paths

def init_sync():
    a=0

def init_handlers(paths):   
    for path in paths:
        handler = Handler(path, created, modified, deleted, moved)
        handlers.append(handler)
        observer.schedule(handler, path, recursive=False)

def stop_observer():
    observer.stop()
    observer.join()



def created(root, relative):
    print("[CREATE]", root, "->", relative)

def modified(root, relative):
    print("[MODIFY]", root, "->", relative)

def deleted(root, relative):
    print("[DELETE]", root, "->", relative)

def moved(root, old_rel, new_rel):
    print("[MOVED]", root, ":", old_rel, "->", new_rel)



def make_key(root, relative):
    return os.path.join(root, relative)

if __name__ == "__main__":
    main()
