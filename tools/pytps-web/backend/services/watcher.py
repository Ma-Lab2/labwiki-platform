"""
watcher.py - Cross-platform file watcher using watchdog library.
Detects new image files and notifies via callback.
"""

import os
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Callable, Optional

IMAGE_EXTENSIONS = {'.tif', '.tiff', '.jpg', '.jpeg', '.png', '.raw'}


class ImageFileHandler(FileSystemEventHandler):
    """Watches for new image files in a directory."""

    def __init__(self, callback: Callable[[str], None]):
        super().__init__()
        self.callback = callback

    def on_created(self, event):
        if event.is_directory:
            return
        ext = os.path.splitext(event.src_path)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            self.callback(event.src_path)


class DirectoryWatcher:
    """Manages a watchdog observer for a single directory."""

    def __init__(self):
        self._observer: Optional[Observer] = None
        self._watching_path: Optional[str] = None

    def start(self, directory: str, callback: Callable[[str], None]):
        self.stop()
        if not os.path.isdir(directory):
            raise ValueError(f"Directory not found: {directory}")

        handler = ImageFileHandler(callback)
        self._observer = Observer()
        self._observer.schedule(handler, directory, recursive=False)
        self._observer.start()
        self._watching_path = directory

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            self._watching_path = None

    @property
    def is_watching(self) -> bool:
        return self._observer is not None and self._observer.is_alive()

    @property
    def watching_path(self) -> Optional[str]:
        return self._watching_path
