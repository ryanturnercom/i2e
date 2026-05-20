from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock


class FileStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = Lock()
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_write({})

    def _read(self) -> dict[str, str]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

    def _atomic_write(self, data: dict[str, str]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)

    def get(self, code: str) -> str | None:
        with self._lock:
            return self._read().get(code)

    def put(self, code: str, url: str) -> None:
        with self._lock:
            data = self._read()
            data[code] = url
            self._atomic_write(data)

    def all(self) -> dict[str, str]:
        with self._lock:
            return dict(self._read())
