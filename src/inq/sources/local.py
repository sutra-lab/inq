from __future__ import annotations

from pathlib import Path

from ..sandbox import (
    GitignoreFilter,
    is_binary,
    language_for,
    list_dir as _list_dir,
    resolve_within,
)
from .base import FileNotFound, NotADirectory, NotAFile, SourceError


PDF_MAGIC = b"%PDF-"


class LocalSource:
    """Read-only filesystem source rooted at ``--root``."""

    def __init__(self, root: Path, max_file_size: int = 2 * 1024 * 1024) -> None:
        root = root.expanduser().resolve()
        if not root.is_dir():
            raise SourceError(f"root is not a directory: {root}")
        self.root = root
        self.max_file_size = max_file_size
        self.gi = GitignoreFilter(root)
        self.label = f"local: {root}"

    # -- helpers ----------------------------------------------------------

    def _resolve(self, path: str) -> Path:
        try:
            return resolve_within(self.root, path) if path else self.root
        except ValueError as exc:
            raise SourceError(str(exc)) from exc

    def _is_pdf(self, path: Path) -> bool:
        if path.suffix.lower() == ".pdf":
            return True
        try:
            with path.open("rb") as f:
                return f.read(5) == PDF_MAGIC
        except OSError:
            return False

    # -- API --------------------------------------------------------------

    def list_dir(self, path: str = "", depth: int = 1) -> dict:
        base = self._resolve(path)
        if not base.exists():
            raise FileNotFound(path)
        if not base.is_dir():
            raise NotADirectory(path)
        return _list_dir(base, self.root, self.gi, depth)

    def read_metadata(self, path: str) -> dict:
        abs_path = self._resolve(path)
        if not abs_path.exists():
            raise FileNotFound(path)
        if not abs_path.is_file():
            raise NotAFile(path)

        size = abs_path.stat().st_size
        if size > self.max_file_size:
            return {"path": path, "kind": "skipped", "size": size, "skipped": "too_large"}

        if self._is_pdf(abs_path):
            try:
                from pypdf import PdfReader

                reader = PdfReader(str(abs_path))
                page_count = len(reader.pages)
            except Exception as exc:  # corrupt / encrypted / etc.
                return {
                    "path": path,
                    "kind": "skipped",
                    "size": size,
                    "skipped": f"pdf: {exc}",
                }
            return {
                "path": path,
                "kind": "pdf",
                "size": size,
                "page_count": page_count,
            }

        if is_binary(abs_path):
            return {"path": path, "kind": "binary", "size": size, "skipped": "binary"}

        try:
            content = abs_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return {"path": path, "kind": "skipped", "size": size, "skipped": "encoding"}

        return {
            "path": path,
            "kind": "text",
            "language": language_for(abs_path),
            "content": content,
            "size": size,
        }

    def read_for_ai(self, path: str) -> dict:
        """Same as ``read_metadata`` but for PDFs we also extract per-page text."""
        meta = self.read_metadata(path)
        if meta.get("kind") != "pdf":
            return meta

        abs_path = self._resolve(path)
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(abs_path))
            pages: list[str] = []
            for p in reader.pages:
                try:
                    pages.append(p.extract_text() or "")
                except Exception:
                    pages.append("")
        except Exception as exc:
            return {
                "path": path,
                "kind": "skipped",
                "size": meta["size"],
                "skipped": f"pdf-extract: {exc}",
            }
        return {**meta, "pages": pages}

    def open_raw(self, path: str) -> tuple[Path, str]:
        abs_path = self._resolve(path)
        if not abs_path.exists():
            raise FileNotFound(path)
        if not abs_path.is_file():
            raise NotAFile(path)
        if self._is_pdf(abs_path):
            return abs_path, "application/pdf"
        return abs_path, "application/octet-stream"
