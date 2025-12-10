import datetime
from ftplib import FTP
import os
from pathlib import Path
import tempfile
import zipfile
from path_utilities import is_valid_path, is_valid_file, read_file_safely
import argparse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
from handlers import Handler
from result import Result
from io import BytesIO
import zipfile
from logger import log, log_err, log_info

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
    
    init_sync()
    return
    
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
            log_err(try_paths_file.error)
            return None

        try:
            data = read_file_safely(try_paths_file.value)
        except PermissionError as e:
            log_err(f"Could not read paths file: {e}")
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

def init_sync():
    log_info("Finding latest files for initial sync.")
    latest_files = {}
    for path in paths:
        files_in_path = ls(path)
        for rel_path, (path, mtime) in files_in_path.items():
            if rel_path in latest_files:
                _, existing_mtime = latest_files[rel_path]
                if mtime > existing_mtime:
                    latest_files[rel_path] = (path, mtime)
            else:
                latest_files[rel_path] = (path, mtime)

    log_info(
        f"Syncing all to latest files:\n" +
        "\n".join(f"{k}: {v}" for k, v in latest_files.items())
    )

    for path in paths:
        files_in_path = ls(path)
        _, mtime = files_in_path[rel_path]
        for rel_path, (latest_path, latest_mtime) in latest_files.items():
            if rel_path not in files_in_path.keys():
                log(f"File [{rel_path}] not found in [{path["path"]}], writing latest from [{latest_path["path"]}]")
                write(rel_path, path, get_bytes(rel_path, latest_path))
            else:               
                if mtime < latest_mtime:
                    log(f"File [{rel_path}] from [{path["path"]}] [{time.ctime(mtime)}] is behind latest, writing from [{latest_path["path"]}] [{time.ctime(latest_mtime)}]")
                    write(rel_path, path, get_bytes(rel_path, latest_path))

    


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


def ls(path):
    folder_list = {}
    if path["type"] == "folder":       
        for root, dirs, files in os.walk(path["path"]):
            for file in files:
                full_path = os.path.join(root, file)
                modified = os.path.getmtime(full_path)

                rel_path = os.path.relpath(full_path, path["path"])

                folder_list[rel_path] = (path, modified)

    if path["type"] == "zip":
        zip_path = path["path"]

        with zipfile.ZipFile(zip_path, "r") as z:
            for info in z.infolist():
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

        def walk_ftp(current_remote_path):
            lines = []
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
                    except:
                        pass

                    rel_path = item_path[len(base_remote):].lstrip("/")
                    folder_list[rel_path] = (path, mtime)

        walk_ftp(base_remote)
        ftp.quit()

    return folder_list

def write(rel_path, path, bytes_data):
    if path["type"] == "folder":
        base = path["path"]
        dest = os.path.join(base, rel_path)

        os.makedirs(os.path.dirname(dest), exist_ok=True)

        with open(dest, "wb") as f:
            f.write(bytes_data)

        return True

    if path["type"] == "zip":
        zip_path = path["path"]
        zip_dir = os.path.dirname(zip_path)

        tmp_fd, tmp_name = tempfile.mkstemp(suffix=".zip", dir=zip_dir)
        os.close(tmp_fd)

        try:
            if os.path.exists(zip_path):
                with zipfile.ZipFile(zip_path, "r") as zin, zipfile.ZipFile(tmp_name, "w", zipfile.ZIP_DEFLATED) as zout:

                    for item in zin.infolist():
                        if item.filename == rel_path:
                            continue
                        data = zin.read(item.filename)
                        zout.writestr(item, data)

                    zout.writestr(rel_path, bytes_data)
            else:
                with zipfile.ZipFile(tmp_name, "w", zipfile.ZIP_DEFLATED) as zout:
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
            except:
                log_err(f"Problem when making dir in FTP {base_remote}")
            current = current + "/" + folder

        ftp.cwd(os.path.dirname(full_remote))

        bio = BytesIO(bytes_data)
        ftp.storbinary("STOR " + filename, bio)

        ftp.quit()
        return True

    raise ValueError(f"Unknown location type: {path['type']}")

def get_bytes(rel_path, path):
    if path["type"] == "folder":
        full_path = os.path.join(path["path"], rel_path)
        with open(full_path, "rb") as f:
            return f.read()

    if path["type"] == "zip":
        zip_path = path["path"]
        with zipfile.ZipFile(zip_path, "r") as z:
            with z.open(rel_path, "r") as f:
                return f.read()

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


def parse_mdtm_to_unix(ts: str) -> float:
    """
    Convert MDTM timestamp like '20251204201800.948' or '20251204201800'
    to a Unix timestamp (float seconds since epoch).
    """
    if "." in ts:
        dt = datetime.datetime.strptime(ts, "%Y%m%d%H%M%S.%f")
    else:
        dt = datetime.datetime.strptime(ts, "%Y%m%d%H%M%S")
    dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.timestamp()



if __name__ == "__main__":
    main()
