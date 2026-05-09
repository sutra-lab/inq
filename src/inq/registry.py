"""Multi-source registry.

Holds the set of FileSources the server is willing to serve right now, plus
each one's per-source ThreadStore. `local` is always present (it's how inq is
launched). Drive sources can be added at runtime through ``/api/sources``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from .sources import FileSource
from .threads import ThreadStore


@dataclass
class SourceEntry:
    id: str
    kind: str  # "local" | "drive"
    label: str
    source: FileSource
    threads: ThreadStore


class SourceRegistry:
    def __init__(self, default: FileSource, default_id: str = "local") -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, SourceEntry] = {}
        self.default_id = default_id
        kind = "drive" if type(default).__name__ == "DriveSource" else "local"
        self._entries[default_id] = SourceEntry(
            id=default_id,
            kind=kind,
            label=default.label,
            source=default,
            threads=ThreadStore(source_label=default.label),
        )

    def get(self, source_id: str) -> SourceEntry:
        with self._lock:
            entry = self._entries.get(source_id)
        if entry is None:
            raise KeyError(source_id)
        return entry

    def add(self, source_id: str, kind: str, source: FileSource) -> SourceEntry:
        with self._lock:
            if source_id in self._entries:
                raise ValueError(f"source id already exists: {source_id}")
            entry = SourceEntry(
                id=source_id,
                kind=kind,
                label=source.label,
                source=source,
                threads=ThreadStore(source_label=source.label),
            )
            self._entries[source_id] = entry
        return entry

    def remove(self, source_id: str) -> bool:
        with self._lock:
            if source_id == self.default_id:
                return False
            return self._entries.pop(source_id, None) is not None

    def list(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "id": e.id,
                    "kind": e.kind,
                    "label": e.label,
                    "default": e.id == self.default_id,
                }
                for e in self._entries.values()
            ]
