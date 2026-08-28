from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class TempFileManager:
    def __init__(self) -> None:
        self._tracked_paths: set[str] = set()

    @contextmanager
    def managed_temp_path(self, suffix: str = "") -> Iterator[Path]:
        fd, raw_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        path = Path(raw_path)
        self._tracked_paths.add(str(path))
        try:
            yield path
        finally:
            self.safe_delete(path)

    def track(self, path: Path) -> None:
        self._tracked_paths.add(str(path))

    def safe_delete(self, path: Path) -> None:
        try:
            if path.exists():
                path.unlink()
        finally:
            self._tracked_paths.discard(str(path))

    def cleanup_all_safely(self) -> None:
        for raw in list(self._tracked_paths):
            try:
                p = Path(raw)
                if p.exists():
                    p.unlink()
            except Exception:
                pass
            finally:
                self._tracked_paths.discard(raw)

