from __future__ import annotations

from pathlib import Path

import pathspec


LANG_BY_EXT: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".swift": "swift",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".fish": "fish",
    ".md": "markdown",
    ".markdown": "markdown",
    ".rst": "rst",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".ini": "ini",
    ".html": "html",
    ".htm": "html",
    ".xml": "xml",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".sql": "sql",
    ".lua": "lua",
    ".vim": "vim",
    ".r": "r",
    ".tex": "latex",
}

# Always-on excludes layered on top of any user .gitignore.
BASELINE_IGNORES: list[str] = [
    ".git/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    "node_modules/",
    ".venv/",
    "venv/",
    ".DS_Store",
    "*.pyc",
]


class GitignoreFilter:
    """Applies the root-level .gitignore plus a small baseline of always-ignored entries."""

    def __init__(self, root: Path) -> None:
        self.root = root
        patterns: list[str] = list(BASELINE_IGNORES)
        gi = root / ".gitignore"
        if gi.is_file():
            try:
                patterns.extend(gi.read_text(encoding="utf-8").splitlines())
            except OSError:
                pass
        self.spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    def ignored(self, abs_path: Path) -> bool:
        try:
            rel = abs_path.relative_to(self.root)
        except ValueError:
            return True
        rel_s = rel.as_posix()
        if abs_path.is_dir():
            rel_s += "/"
        return self.spec.match_file(rel_s)


def resolve_within(root: Path, rel: str) -> Path:
    """Resolve a client-supplied relative path to an absolute path inside root.

    Raises ValueError if the path escapes root via ``..`` or symlinks.
    """
    if rel.startswith("/"):
        raise ValueError("absolute paths are not allowed")
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes root: {rel}") from exc
    return candidate


def _entry_sort_key(p: Path) -> tuple[int, str]:
    return (0 if p.is_dir() else 1, p.name.lower())


def list_dir(base: Path, root: Path, gi: GitignoreFilter, depth: int) -> dict:
    def walk(d: Path, remaining: int) -> list[dict]:
        out: list[dict] = []
        try:
            children = sorted(d.iterdir(), key=_entry_sort_key)
        except (PermissionError, OSError):
            return out
        for child in children:
            if gi.ignored(child):
                continue
            is_dir = child.is_dir()
            node: dict = {
                "name": child.name,
                "path": child.relative_to(root).as_posix(),
                "type": "dir" if is_dir else "file",
            }
            if is_dir and remaining > 1:
                node["children"] = walk(child, remaining - 1)
            out.append(node)
        return out

    rel = "" if base == root else base.relative_to(root).as_posix()
    return {"path": rel, "children": walk(base, depth)}


def is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(8192)
    except OSError:
        return True
    return b"\x00" in chunk


def language_for(path: Path) -> str:
    if path.name.lower() in {"dockerfile", "containerfile"}:
        return "dockerfile"
    if path.name.lower() == "makefile":
        return "makefile"
    return LANG_BY_EXT.get(path.suffix.lower(), "text")


def read_file(path: Path, max_size: int) -> dict:
    """Returns a uniform dict describing the file content (or why it was skipped)."""
    try:
        size = path.stat().st_size
    except OSError as exc:
        return {"language": "text", "content": "", "size": 0, "skipped": f"stat: {exc}"}

    if size > max_size:
        return {"language": "text", "content": "", "size": size, "skipped": "too_large"}
    if is_binary(path):
        return {"language": "binary", "content": "", "size": size, "skipped": "binary"}
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return {"language": "text", "content": "", "size": size, "skipped": "encoding"}
    return {"language": language_for(path), "content": content, "size": size}
