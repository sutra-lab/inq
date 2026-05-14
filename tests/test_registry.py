from __future__ import annotations

from pathlib import Path

import pytest

from inq.registry import SourceRegistry
from inq.sources.local import LocalSource


def test_registry_starts_with_default(tmp_root: Path) -> None:
    src = LocalSource(tmp_root)
    reg = SourceRegistry(default=src)
    entries = reg.list()
    assert len(entries) == 1
    assert entries[0]["id"] == "local"
    assert entries[0]["kind"] == "local"
    assert entries[0]["default"] is True


def test_get_returns_default_entry(tmp_root: Path) -> None:
    src = LocalSource(tmp_root)
    reg = SourceRegistry(default=src)
    entry = reg.get("local")
    assert entry.source is src
    assert entry.threads is not None


def test_get_unknown_raises(tmp_root: Path) -> None:
    reg = SourceRegistry(default=LocalSource(tmp_root))
    with pytest.raises(KeyError):
        reg.get("nope")


def test_add_extra_source(tmp_root: Path, tmp_path: Path) -> None:
    other_root = tmp_path / "other"
    other_root.mkdir()
    (other_root / "x.py").write_text("pass\n", encoding="utf-8")

    reg = SourceRegistry(default=LocalSource(tmp_root))
    reg.add("local2", "local", LocalSource(other_root))
    assert {e["id"] for e in reg.list()} == {"local", "local2"}


def test_add_duplicate_id_rejected(tmp_root: Path) -> None:
    reg = SourceRegistry(default=LocalSource(tmp_root))
    with pytest.raises(ValueError, match="already exists"):
        reg.add("local", "local", LocalSource(tmp_root))


def test_remove_non_default(tmp_root: Path, tmp_path: Path) -> None:
    other_root = tmp_path / "other"
    other_root.mkdir()
    reg = SourceRegistry(default=LocalSource(tmp_root))
    reg.add("local2", "local", LocalSource(other_root))
    assert reg.remove("local2") is True
    assert {e["id"] for e in reg.list()} == {"local"}


def test_remove_default_blocked(tmp_root: Path) -> None:
    reg = SourceRegistry(default=LocalSource(tmp_root))
    assert reg.remove("local") is False


def test_remove_missing_returns_false(tmp_root: Path) -> None:
    reg = SourceRegistry(default=LocalSource(tmp_root))
    assert reg.remove("ghost") is False


def test_added_source_has_separate_thread_store(tmp_root: Path, tmp_path: Path) -> None:
    other_root = tmp_path / "other"
    other_root.mkdir()
    reg = SourceRegistry(default=LocalSource(tmp_root))
    reg.add("local2", "local", LocalSource(other_root))
    assert reg.get("local").threads.path != reg.get("local2").threads.path
