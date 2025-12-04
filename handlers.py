import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import threading

ignored = set()
ignored_lock = threading.Lock()

class Handler(FileSystemEventHandler):
    def __init__(self, root, on_create, on_modify, on_delete, on_moved):
        super().__init__()
        self.root = root
        self.on_create_cb = on_create
        self.on_modify_cb = on_modify
        self.on_delete_cb = on_delete
        self.on_moved_cb = on_moved

    def on_created(self, event):
        self._return_info(event, self.on_create_cb)

    def on_modified(self, event):
        self._return_info(event, self.on_modify_cb)

    def on_deleted(self, event):
        self._return_info(event, self.on_delete_cb)

    def on_moved(self, event):
        if event.is_directory:
            return

        old_rel = os.path.relpath(event.src_path, self.root)
        new_rel = os.path.relpath(event.dest_path, self.root)

        old_key = make_key(self.root, old_rel)
        new_key = make_key(self.root, new_rel)

        with ignored_lock:
            if old_key in ignored or new_key in ignored:
                ignored.discard(old_key)
                ignored.discard(new_key)
                return

        self.on_moved_cb(self.root, old_rel, new_rel)


    def _return_info(self, event, callback):
        if event.is_directory:
            return

        full_path = event.src_path
        relative = os.path.relpath(full_path, self.root)
        key = make_key(self.root, relative)

        with ignored_lock:
            if key in ignored:
                ignored.discard(key)
                return
        callback(self.root, relative)

def make_key(root, relative):
    return os.path.join(root, relative)