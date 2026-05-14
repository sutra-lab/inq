from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from inq.providers.base import AskRequest, StreamEvent
from inq.sources.local import LocalSource
from inq.threads import ThreadStore


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.py").write_text("x = 1\ny = 2\nz = 3\n", encoding="utf-8")
    (root / "README.md").write_text("# hi\n\nbody\n", encoding="utf-8")
    sub = root / "pkg"
    sub.mkdir()
    (sub / "deep.py").write_text("print('hello')\n", encoding="utf-8")
    (root / ".gitignore").write_text("secret/\n*.log\n", encoding="utf-8")
    secret = root / "secret"
    secret.mkdir()
    (secret / "do_not_show.txt").write_text("nope\n", encoding="utf-8")
    (root / "noise.log").write_text("debug\n", encoding="utf-8")
    return root


@pytest.fixture
def threads_dir(tmp_path: Path) -> Path:
    d = tmp_path / "threads"
    d.mkdir()
    return d


@pytest.fixture
def thread_store(threads_dir: Path) -> ThreadStore:
    return ThreadStore(source_label="local: /tmp/x", base_dir=threads_dir)


@pytest.fixture
def local_source(tmp_root: Path) -> LocalSource:
    return LocalSource(tmp_root)


@pytest.fixture
def sample_thread() -> dict:
    return {
        "id": "t1",
        "file": "a.py",
        "kind": "text",
        "mode": "ai",
        "language": "python",
        "anchor": {"startLine": 1, "endLine": 2},
        "messages": [
            {"role": "user", "content": "what does this do?"},
            {"role": "assistant", "content": "assigns numbers."},
        ],
        "createdAt": "2026-05-14T00:00:00Z",
        "updatedAt": "2026-05-14T00:00:00Z",
    }


class FakeProvider:
    """Deterministic Provider for testing the server's /api/ask wiring."""

    name = "fake"
    model = "fake-model-1"

    def __init__(self, tokens: list[str] | None = None) -> None:
        self.tokens = tokens or ["hello ", "world"]
        self.calls: list[AskRequest] = []

    async def stream(self, req: AskRequest) -> AsyncIterator[StreamEvent]:
        self.calls.append(req)
        yield StreamEvent(type="start", data={"model": self.model})
        for tok in self.tokens:
            yield StreamEvent(type="token", data=tok)
        yield StreamEvent(type="usage", data={"input_tokens": 1, "output_tokens": 1})


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()
