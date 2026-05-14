from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from inq.registry import SourceRegistry
from inq.server import create_app
from inq.sources.local import LocalSource
from inq.threads import ThreadStore

from .conftest import FakeProvider


@pytest.fixture
def app_client(
    tmp_root: Path, threads_dir: Path, fake_provider: FakeProvider
) -> TestClient:
    src = LocalSource(tmp_root)
    reg = SourceRegistry(default=src)
    # Redirect thread persistence to the test-owned threads dir.
    reg.get("local").threads = ThreadStore(source_label=src.label, base_dir=threads_dir)
    app = create_app(registry=reg, provider=fake_provider)
    return TestClient(app)


class TestHealth:
    def test_health_shape(self, app_client: TestClient) -> None:
        r = app_client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["default_source"] == "local"
        assert body["provider"] == "fake"


class TestTree:
    def test_lists_root(self, app_client: TestClient) -> None:
        r = app_client.get("/api/tree")
        assert r.status_code == 200
        names = {c["name"] for c in r.json()["children"]}
        assert "a.py" in names
        # gitignored not exposed
        assert "secret" not in names

    def test_unknown_source(self, app_client: TestClient) -> None:
        r = app_client.get("/api/tree", params={"source": "ghost"})
        assert r.status_code == 404

    def test_escape_rejected(self, app_client: TestClient) -> None:
        r = app_client.get("/api/tree", params={"path": "../"})
        assert r.status_code == 400


class TestFile:
    def test_reads_text_file(self, app_client: TestClient) -> None:
        r = app_client.get("/api/file", params={"path": "a.py"})
        assert r.status_code == 200
        body = r.json()
        assert body["kind"] == "text"
        assert body["language"] == "python"
        assert "x = 1" in body["content"]

    def test_missing_file(self, app_client: TestClient) -> None:
        r = app_client.get("/api/file", params={"path": "ghost.py"})
        assert r.status_code == 404

    def test_directory_rejected(self, app_client: TestClient) -> None:
        r = app_client.get("/api/file", params={"path": "pkg"})
        assert r.status_code == 400


class TestSources:
    def test_lists_default(self, app_client: TestClient) -> None:
        r = app_client.get("/api/sources")
        assert r.status_code == 200
        body = r.json()
        assert body["default"] == "local"
        assert any(s["id"] == "local" for s in body["sources"])

    def test_cannot_remove_default(self, app_client: TestClient) -> None:
        r = app_client.delete("/api/sources/local")
        assert r.status_code == 400


class TestThreads:
    def test_list_starts_empty(self, app_client: TestClient) -> None:
        r = app_client.get("/api/threads")
        assert r.status_code == 200
        assert r.json()["threads"] == []

    def test_upsert_and_list(
        self, app_client: TestClient, sample_thread: dict
    ) -> None:
        r = app_client.post("/api/threads", json=sample_thread)
        assert r.status_code == 200
        listed = app_client.get("/api/threads").json()["threads"]
        assert len(listed) == 1
        assert listed[0]["id"] == "t1"

    def test_delete(self, app_client: TestClient, sample_thread: dict) -> None:
        app_client.post("/api/threads", json=sample_thread)
        r = app_client.delete("/api/threads/t1")
        assert r.status_code == 200
        assert app_client.get("/api/threads").json()["threads"] == []

    def test_delete_missing(self, app_client: TestClient) -> None:
        r = app_client.delete("/api/threads/ghost")
        assert r.status_code == 404


class TestAsk:
    def test_streams_tokens(
        self, app_client: TestClient, fake_provider: FakeProvider
    ) -> None:
        body = {
            "question": "what does this do?",
            "file": "a.py",
            "anchor": {"startLine": 1, "endLine": 2},
        }
        with app_client.stream("POST", "/api/ask", json=body) as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            chunks = b"".join(r.iter_bytes()).decode("utf-8")
        assert "event: start" in chunks
        assert "event: token" in chunks
        assert "event: done" in chunks
        assert len(fake_provider.calls) == 1
        assert fake_provider.calls[0].question == "what does this do?"

    def test_missing_file_404(self, app_client: TestClient) -> None:
        body = {
            "question": "y?",
            "file": "ghost.py",
            "anchor": {"startLine": 1, "endLine": 1},
        }
        r = app_client.post("/api/ask", json=body)
        assert r.status_code == 404

    def test_inverted_anchor_400(self, app_client: TestClient) -> None:
        body = {
            "question": "y?",
            "file": "a.py",
            "anchor": {"startLine": 5, "endLine": 2},
        }
        r = app_client.post("/api/ask", json=body)
        assert r.status_code == 400
