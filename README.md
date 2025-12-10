# FileSync — Multi-Location Real-Time File Synchronization

FileSync is a Python-based synchronization system that keeps multiple storage locations continuously mirrored.  
It detects changes in real time and ensures every participating location always contains the most up-to-date version of each file.

The system supports:
- **Local folders**
- **ZIP archives**
- **FTP servers**

FileSync uses watcher threads, a global event processing queue, and a latest-write-wins synchronization model to replicate file changes across all locations.

---

## 🚀 Features

### ✔️ Multi-Location Synchronization
Synchronizes files across:
- `folder:/path/to/folder`
- `zip:/path/to/archive.zip`
- `ftp:username:password@host/path`

All locations are abstracted into a uniform interface.

### ✔️ Real-Time Monitoring
A dedicated watcher thread monitors each location for:
- File creation  
- File modification  
- File deletion  

Events are pushed into a shared queue for processing.

### ✔️ Automatic Conflict Resolution
When multiple watchers detect events for the same file:

- Events are grouped by filename  
- The version with the **newest timestamp** wins  
- That version is propagated to all other locations  

### ✔️ Initial Full Synchronization
On startup:
1. All locations are scanned  
2. The latest version of each file is determined  
3. Out-of-date locations are updated  

Ensures a consistent baseline before real-time sync begins.

### ✔️ ZIP & FTP Support
ZIP archives behave like virtual folders: read, write, delete, and list operations are all supported.

FTP support includes:
- Recursive directory traversal  
- Timestamp parsing via MDTM  
- Creating directories and uploading files as needed  

### ✔️ PEP-Compliant Codebase
Includes:
- PEP 8 formatting  
- PEP 257 docstrings  
- PEP 484 type hints  
- Modular architecture  

---

## 🗂 Project Structure

```
project/
│
├── main.py             # Core orchestration logic and synchronization engine
├── logger.py           # Colored logging utilities
├── path_utilities.py   # Path validation and safe file reading helpers
├── result.py           # Lightweight Result<T,E> type for error handling
└── README.md           # Project documentation
```

---

## 📘 How It Works

### 1. Define your sync locations
Either interactively or using `--file`, you define paths using this format:

```
folder:/local/folder
zip:/path/to/archive.zip
ftp:user:password@hostname/path
```

### 2. Initial synchronization
The system checks every location and identifies the most recent copy of each file.  
All other locations are updated to match.

### 3. Real-time watchers begin
Each location is scanned repeatedly:

- Modified files are detected by comparing MTIMEs  
- Created and deleted files are detected by comparing directory/file listings  
- All changes are added to a thread-safe queue  

### 4. Event batching and replication
The main thread:
- Groups events by filename  
- Determines the "winning" timestamp  
- Writes the correct version to every other location  

Deletes are propagated globally as well.

---

## 🧪 Usage

### 🔹 Interactive Mode
Run:

```bash
python main.py
```

You will be prompted:

```
Enter path (folder:/zip:/ftp: or [end]):
```

Enter as many locations as needed, then type `end`.

---

### 🔹 Using a File to Provide Paths
Create a file containing one location per line:

```
folder:/my/data
zip:/backups/archive.zip
ftp:admin:1234@192.168.1.20/files
```

Run:

```bash
python main.py --file
```

You will be prompted to enter the file path.

---

## 🛠 Dependencies

The project uses only Python’s standard library:
- `os`, `zipfile`, `ftplib`, `tempfile`, `threading`, `queue`
- `argparse`, `pathlib`, `datetime`, `typing`

No external packages required.

---

## ⚠️ Limitations & Notes

- File renames appear as a deletion + creation  
- Large ZIPs may take time to rewrite  
- FTP support depends on the server’s implementation of directory listing and MDTM  
- Watchers operate with periodic scans, not OS-level file events  

---

## 📌 Future Enhancements

Potential features:
- Add support for S3 / SMB / SCP
- Ignore-patterns (`.gitignore` style)
- Web dashboard showing sync status
- Async I/O or watchdog integration for faster detection

---

## ❤️ Contributing

Pull requests and suggestions are welcome.  
Let me know if you'd like a `CONTRIBUTING.md` template.

---

## 📫 Support

If you need help setting up new storage types, adding features, or packaging this as a pip module, feel free to ask.
