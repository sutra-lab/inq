from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

THREADS_DIR = Path(
    os.environ.get("INQ_THREADS_DIR")
    or (Path.home() / ".config" / "inq" / "threads")
)


class ThreadAnchor(BaseModel):
    startLine: int = Field(ge=1)
    endLine: int = Field(ge=1)


class ThreadMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class StoredThread(BaseModel):
    id: str
    file: str
    kind: Literal["text", "pdf"]
    mode: Literal["ai", "comment"] = "ai"
    language: str
    anchor: ThreadAnchor
    messages: list[ThreadMessage]
    error: str | None = None
    model: str | None = None
    createdAt: str
    updatedAt: str


def _source_key(source_label: str) -> str:
    return hashlib.sha256(source_label.encode("utf-8")).hexdigest()[:16]


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ThreadStore:
    """JSON-backed thread persistence, scoped per source."""

    source_label: str
    base_dir: Path = THREADS_DIR

    @property
    def path(self) -> Path:
        return self.base_dir / f"{_source_key(self.source_label)}.json"

    # -- IO ---------------------------------------------------------------

    def _read(self) -> dict:
        if not self.path.is_file():
            return {"source": self.source_label, "threads": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"source": self.source_label, "threads": []}
        if not isinstance(data, dict) or not isinstance(data.get("threads"), list):
            return {"source": self.source_label, "threads": []}
        return data

    def _write(self, data: dict) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        body = json.dumps(data, ensure_ascii=False, indent=2)
        # Atomic write: temp file in same dir, then rename.
        fd, tmp = tempfile.mkstemp(prefix=".thr_", suffix=".tmp", dir=self.base_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(body)
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # -- API --------------------------------------------------------------

    def list(self) -> list[dict]:
        data = self._read()
        out: list[dict] = []
        for raw in data["threads"]:
            try:
                out.append(StoredThread.model_validate(raw).model_dump())
            except ValidationError:
                # Skip malformed entries rather than failing the whole list.
                continue
        return out

    def upsert(self, thread: dict) -> dict:
        try:
            t = StoredThread.model_validate(thread)
        except ValidationError as exc:
            raise ValueError(f"invalid thread: {exc}") from exc
        now = _now_iso()
        existing = self._read()
        threads = existing["threads"]
        t_dict = t.model_dump()
        t_dict["updatedAt"] = now
        replaced = False
        for i, raw in enumerate(threads):
            if isinstance(raw, dict) and raw.get("id") == t.id:
                t_dict["createdAt"] = raw.get("createdAt") or t.createdAt
                threads[i] = t_dict
                replaced = True
                break
        if not replaced:
            t_dict["createdAt"] = t.createdAt or now
            threads.append(t_dict)
        existing["source"] = self.source_label
        self._write(existing)
        return t_dict

    def delete(self, thread_id: str) -> bool:
        data = self._read()
        before = len(data["threads"])
        data["threads"] = [
            t for t in data["threads"] if not (isinstance(t, dict) and t.get("id") == thread_id)
        ]
        if len(data["threads"]) == before:
            return False
        self._write(data)
        return True
