from __future__ import annotations

from pathlib import Path

import pytest

from inq.sources.base import FileNotFound, NotAFile, SourceError
from inq.sources.local import LocalSource


def test_label_includes_root(tmp_root: Path) -> None:
    src = LocalSource(tmp_root)
    assert src.label == f"local: {tmp_root}"


def test_root_must_be_a_directory(tmp_path: Path) -> None:
    f = tmp_path / "not-a-dir"
    f.write_text("hi", encoding="utf-8")
    with pytest.raises(SourceError, match="not a directory"):
        LocalSource(f)


def test_list_dir_at_root(local_source: LocalSource) -> None:
    result = local_source.list_dir("")
    names = {c["name"] for c in result["children"]}
    assert "a.py" in names
    # gitignored entries dropped
    assert "secret" not in names
    assert "noise.log" not in names


def test_list_dir_nested(local_source: LocalSource) -> None:
    result = local_source.list_dir("pkg")
    names = {c["name"] for c in result["children"]}
    assert "deep.py" in names


def test_list_dir_unknown_path(local_source: LocalSource) -> None:
    with pytest.raises(FileNotFound):
        local_source.list_dir("ghost")


def test_list_dir_escape_rejected(local_source: LocalSource) -> None:
    with pytest.raises(SourceError, match="escapes root"):
        local_source.list_dir("../escaped")


def test_read_metadata_text(local_source: LocalSource) -> None:
    meta = local_source.read_metadata("a.py")
    assert meta["kind"] == "text"
    assert meta["language"] == "python"
    assert "x = 1" in meta["content"]


def test_read_metadata_missing(local_source: LocalSource) -> None:
    with pytest.raises(FileNotFound):
        local_source.read_metadata("ghost.py")


def test_read_metadata_directory_rejected(local_source: LocalSource) -> None:
    with pytest.raises(NotAFile):
        local_source.read_metadata("pkg")


def test_read_metadata_too_large(tmp_root: Path) -> None:
    big = tmp_root / "big.py"
    big.write_text("x" * 5000, encoding="utf-8")
    src = LocalSource(tmp_root, max_file_size=1000)
    meta = src.read_metadata("big.py")
    assert meta["kind"] == "skipped"
    assert meta["skipped"] == "too_large"


def test_read_metadata_binary(tmp_root: Path) -> None:
    b = tmp_root / "bin"
    b.write_bytes(b"\x00\x01\x02")
    src = LocalSource(tmp_root)
    meta = src.read_metadata("bin")
    assert meta["kind"] == "binary"


def test_read_for_ai_passthrough_for_text(local_source: LocalSource) -> None:
    out = local_source.read_for_ai("a.py")
    assert out["kind"] == "text"
    assert "x = 1" in out["content"]


def test_open_raw_returns_path_and_mime(local_source: LocalSource, tmp_root: Path) -> None:
    abs_path, mime = local_source.open_raw("a.py")
    assert abs_path == tmp_root / "a.py"
    assert mime == "application/octet-stream"


def test_pdf_magic_detected(tmp_root: Path) -> None:
    fake = tmp_root / "weird.txt"
    fake.write_bytes(b"%PDF-1.4\n%fake\n")
    src = LocalSource(tmp_root)
    # extension is .txt but magic byte sniff catches it
    _, mime = src.open_raw("weird.txt")
    assert mime == "application/pdf"
