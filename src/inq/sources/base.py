from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


class FileNotFound(Exception):
    """Raised when a path resolves to nothing on the source."""


class NotADirectory(Exception):
    """Raised when a tree call targets a non-directory."""


class NotAFile(Exception):
    """Raised when a file call targets a non-file."""


class SourceError(Exception):
    """Generic source error; e.g. unreachable backend, permission denied."""


@runtime_checkable
class FileSource(Protocol):
    """A read-only source of files and directories.

    Concrete implementations: ``LocalSource`` (filesystem), eventually
    ``DriveSource`` (Google Drive). Methods raise ``FileNotFound``,
    ``NotADirectory``, ``NotAFile``, or ``SourceError`` on failure; the server
    layer maps those to HTTP status codes.
    """

    label: str  # "local: /path" or "drive: folder/name" — for the startup banner

    def list_dir(self, path: str, depth: int = 1) -> dict:
        """Return ``{path, children}`` for the given directory."""
        ...

    def read_metadata(self, path: str) -> dict:
        """Return small metadata for /api/file: kind, size, language or page_count."""
        ...

    def read_for_ai(self, path: str) -> dict:
        """Return full payload for the AI provider: includes content or page text."""
        ...

    def open_raw(self, path: str) -> tuple[Path, str]:
        """Return ``(local_path, mime_type)`` for serving raw bytes.

        Local sources return the file path; remote sources may need to download
        to a temp file first. The server uses this for things like PDF rendering
        that need the original bytes.
        """
        ...
