from __future__ import annotations

import json
from pathlib import Path

import pytest

from inq.threads import StoredThread, ThreadStore, _source_key


def test_list_empty_returns_empty(thread_store: ThreadStore) -> None:
    assert thread_store.list() == []


def test_upsert_creates_thread(thread_store: ThreadStore, sample_thread: dict) -> None:
    stored = thread_store.upsert(sample_thread)
    assert stored["id"] == "t1"
    listed = thread_store.list()
    assert len(listed) == 1
    assert listed[0]["id"] == "t1"


def test_upsert_replaces_existing(thread_store: ThreadStore, sample_thread: dict) -> None:
    thread_store.upsert(sample_thread)
    updated = {**sample_thread, "messages": sample_thread["messages"] + [
        {"role": "user", "content": "follow up?"},
        {"role": "assistant", "content": "sure."},
    ]}
    thread_store.upsert(updated)
    listed = thread_store.list()
    assert len(listed) == 1
    assert len(listed[0]["messages"]) == 4


def test_upsert_preserves_createdAt_on_replace(
    thread_store: ThreadStore, sample_thread: dict
) -> None:
    thread_store.upsert(sample_thread)
    first_created = thread_store.list()[0]["createdAt"]
    later = {**sample_thread, "createdAt": "2099-01-01T00:00:00Z"}
    stored = thread_store.upsert(later)
    assert stored["createdAt"] == first_created


def test_upsert_rejects_invalid_thread(thread_store: ThreadStore) -> None:
    with pytest.raises(ValueError, match="invalid thread"):
        thread_store.upsert({"id": "bad"})  # missing required fields


def test_comment_mode_accepted(thread_store: ThreadStore, sample_thread: dict) -> None:
    comment = {
        **sample_thread,
        "id": "c1",
        "mode": "comment",
        "messages": [{"role": "user", "content": "TODO refactor"}],
    }
    stored = thread_store.upsert(comment)
    assert stored["mode"] == "comment"


def test_pdf_kind_accepted(thread_store: ThreadStore, sample_thread: dict) -> None:
    pdf = {**sample_thread, "id": "p1", "kind": "pdf", "language": "pdf"}
    stored = thread_store.upsert(pdf)
    assert stored["kind"] == "pdf"


def test_delete_removes(thread_store: ThreadStore, sample_thread: dict) -> None:
    thread_store.upsert(sample_thread)
    assert thread_store.delete("t1") is True
    assert thread_store.list() == []


def test_delete_missing_returns_false(thread_store: ThreadStore) -> None:
    assert thread_store.delete("nope") is False


def test_persistence_across_instances(
    threads_dir: Path, sample_thread: dict
) -> None:
    a = ThreadStore(source_label="local: /tmp/x", base_dir=threads_dir)
    a.upsert(sample_thread)
    b = ThreadStore(source_label="local: /tmp/x", base_dir=threads_dir)
    assert len(b.list()) == 1


def test_file_mode_is_0600(
    thread_store: ThreadStore, sample_thread: dict
) -> None:
    thread_store.upsert(sample_thread)
    mode = thread_store.path.stat().st_mode & 0o777
    assert mode == 0o600


def test_source_label_isolates_threads(threads_dir: Path, sample_thread: dict) -> None:
    a = ThreadStore(source_label="local: /a", base_dir=threads_dir)
    b = ThreadStore(source_label="local: /b", base_dir=threads_dir)
    a.upsert(sample_thread)
    assert a.list() == [a.list()[0]]
    assert b.list() == []
    assert a.path != b.path


def test_source_key_is_deterministic_and_short() -> None:
    key = _source_key("local: /tmp/x")
    assert len(key) == 16
    assert _source_key("local: /tmp/x") == key
    assert _source_key("local: /tmp/y") != key


def test_corrupt_json_yields_empty_list(threads_dir: Path) -> None:
    store = ThreadStore(source_label="local: /broken", base_dir=threads_dir)
    store.path.write_text("not json {{{", encoding="utf-8")
    assert store.list() == []


def test_skips_malformed_entries_but_keeps_good_ones(
    threads_dir: Path, sample_thread: dict
) -> None:
    store = ThreadStore(source_label="local: /mixed", base_dir=threads_dir)
    store.path.write_text(
        json.dumps({
            "source": "local: /mixed",
            "threads": [sample_thread, {"id": "broken"}],
        }),
        encoding="utf-8",
    )
    listed = store.list()
    assert len(listed) == 1
    assert listed[0]["id"] == "t1"


def test_stored_thread_default_mode_is_ai() -> None:
    t = StoredThread.model_validate({
        "id": "x", "file": "f", "kind": "text", "language": "text",
        "anchor": {"startLine": 1, "endLine": 1},
        "messages": [{"role": "user", "content": "y"}],
        "createdAt": "2026-05-14T00:00:00Z",
        "updatedAt": "2026-05-14T00:00:00Z",
    })
    assert t.mode == "ai"
