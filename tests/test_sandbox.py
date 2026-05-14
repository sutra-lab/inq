from __future__ import annotations

from pathlib import Path

import pytest

from inq.sandbox import (
    GitignoreFilter,
    is_binary,
    language_for,
    list_dir,
    read_file,
    resolve_within,
)


class TestResolveWithin:
    def test_simple_relative(self, tmp_root: Path) -> None:
        out = resolve_within(tmp_root, "a.py")
        assert out == tmp_root / "a.py"

    def test_nested(self, tmp_root: Path) -> None:
        out = resolve_within(tmp_root, "pkg/deep.py")
        assert out == tmp_root / "pkg" / "deep.py"

    def test_empty_resolves_to_root(self, tmp_root: Path) -> None:
        # Empty string goes through; we let LocalSource handle that case.
        out = resolve_within(tmp_root, "")
        assert out == tmp_root

    def test_absolute_path_rejected(self, tmp_root: Path) -> None:
        with pytest.raises(ValueError, match="absolute paths"):
            resolve_within(tmp_root, "/etc/passwd")

    def test_dotdot_escape_rejected(self, tmp_root: Path) -> None:
        with pytest.raises(ValueError, match="escapes root"):
            resolve_within(tmp_root, "../escaped")

    def test_nested_dotdot_escape_rejected(self, tmp_root: Path) -> None:
        with pytest.raises(ValueError, match="escapes root"):
            resolve_within(tmp_root, "pkg/../../outside")

    def test_symlink_escape_rejected(self, tmp_root: Path, tmp_path: Path) -> None:
        outside = tmp_path / "outside.txt"
        outside.write_text("secret\n", encoding="utf-8")
        link = tmp_root / "shortcut"
        link.symlink_to(outside)
        with pytest.raises(ValueError, match="escapes root"):
            resolve_within(tmp_root, "shortcut")


class TestGitignoreFilter:
    def test_baseline_ignores_git_dir(self, tmp_root: Path) -> None:
        (tmp_root / ".git").mkdir()
        (tmp_root / ".git" / "HEAD").write_text("ref\n", encoding="utf-8")
        gi = GitignoreFilter(tmp_root)
        assert gi.ignored(tmp_root / ".git")
        assert gi.ignored(tmp_root / ".git" / "HEAD")

    def test_project_gitignore_applied(self, tmp_root: Path) -> None:
        gi = GitignoreFilter(tmp_root)
        assert gi.ignored(tmp_root / "secret")
        assert gi.ignored(tmp_root / "noise.log")

    def test_non_ignored_passes(self, tmp_root: Path) -> None:
        gi = GitignoreFilter(tmp_root)
        assert not gi.ignored(tmp_root / "a.py")
        assert not gi.ignored(tmp_root / "pkg")

    def test_path_outside_root_treated_as_ignored(self, tmp_root: Path, tmp_path: Path) -> None:
        gi = GitignoreFilter(tmp_root)
        assert gi.ignored(tmp_path / "elsewhere.txt")


class TestListDir:
    def test_lists_root_children(self, tmp_root: Path) -> None:
        gi = GitignoreFilter(tmp_root)
        result = list_dir(tmp_root, tmp_root, gi, depth=1)
        names = [c["name"] for c in result["children"]]
        # gitignored entries dropped
        assert "secret" not in names
        assert "noise.log" not in names
        assert "a.py" in names
        assert "pkg" in names

    def test_dirs_sort_before_files(self, tmp_root: Path) -> None:
        gi = GitignoreFilter(tmp_root)
        result = list_dir(tmp_root, tmp_root, gi, depth=1)
        types = [c["type"] for c in result["children"]]
        # all dirs appear before any file
        last_dir = max((i for i, t in enumerate(types) if t == "dir"), default=-1)
        first_file = next((i for i, t in enumerate(types) if t == "file"), len(types))
        assert last_dir < first_file

    def test_depth_one_does_not_recurse(self, tmp_root: Path) -> None:
        gi = GitignoreFilter(tmp_root)
        result = list_dir(tmp_root, tmp_root, gi, depth=1)
        pkg = next(c for c in result["children"] if c["name"] == "pkg")
        assert "children" not in pkg

    def test_depth_two_recurses_one_level(self, tmp_root: Path) -> None:
        gi = GitignoreFilter(tmp_root)
        result = list_dir(tmp_root, tmp_root, gi, depth=2)
        pkg = next(c for c in result["children"] if c["name"] == "pkg")
        assert pkg["children"]
        assert any(c["name"] == "deep.py" for c in pkg["children"])


class TestLanguageFor:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("a.py", "python"),
            ("a.ts", "typescript"),
            ("a.tsx", "typescript"),
            ("a.rs", "rust"),
            ("a.md", "markdown"),
            ("a.unknown", "text"),
            ("Dockerfile", "dockerfile"),
            ("Makefile", "makefile"),
        ],
    )
    def test_language_detection(self, tmp_path: Path, name: str, expected: str) -> None:
        assert language_for(tmp_path / name) == expected


class TestIsBinary:
    def test_text_file_not_binary(self, tmp_path: Path) -> None:
        f = tmp_path / "t.txt"
        f.write_text("hello world\n", encoding="utf-8")
        assert is_binary(f) is False

    def test_null_byte_means_binary(self, tmp_path: Path) -> None:
        f = tmp_path / "b.bin"
        f.write_bytes(b"abc\x00def")
        assert is_binary(f) is True


class TestReadFile:
    def test_reads_small_text(self, tmp_root: Path) -> None:
        out = read_file(tmp_root / "a.py", max_size=10_000)
        assert out["language"] == "python"
        assert "x = 1" in out["content"]
        assert "skipped" not in out

    def test_rejects_oversize(self, tmp_root: Path) -> None:
        big = tmp_root / "big.txt"
        big.write_text("x" * 5000, encoding="utf-8")
        out = read_file(big, max_size=1000)
        assert out["skipped"] == "too_large"
        assert out["content"] == ""

    def test_rejects_binary(self, tmp_path: Path) -> None:
        b = tmp_path / "x.bin"
        b.write_bytes(b"\x00\x01\x02")
        out = read_file(b, max_size=10_000)
        assert out["skipped"] == "binary"
        assert out["language"] == "binary"
