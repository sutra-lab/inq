from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol, runtime_checkable


@dataclass
class AskRequest:
    """Provider-agnostic ask request.

    Built once per request from the HTTP body + the resolved file content,
    handed to the configured provider.

    For text files, ``anchor_start``/``anchor_end`` are 1-based line numbers.
    For PDFs, ``anchor_start`` is the 1-based page number (and end is ignored).
    """

    file_path: str
    file_data: dict
    anchor_start: int
    anchor_end: int
    question: str
    history: list[dict] = field(default_factory=list)
    context_lines: int = 20
    context_pages: int = 1
    full_file: bool = False
    max_tokens: int = 2048


@dataclass
class StreamEvent:
    """A single event emitted by a provider's stream.

    The server encodes these as SSE events. ``type`` mirrors SSE event names.
    """

    type: str  # "start" | "token" | "usage" | "error"
    data: Any  # str for token/error, dict for start/usage


@runtime_checkable
class Provider(Protocol):
    name: str
    model: str

    async def stream(self, req: AskRequest) -> AsyncIterator[StreamEvent]: ...
