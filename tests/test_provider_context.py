from __future__ import annotations

from inq.providers._context import (
    build_file_block,
    build_user_text,
    format_context,
)
from inq.providers.base import AskRequest


def _text_request(content: str, start: int, end: int, **overrides) -> AskRequest:
    return AskRequest(
        file_path="a.py",
        file_data={"kind": "text", "language": "python", "content": content},
        anchor_start=start,
        anchor_end=end,
        question="what does this do?",
        **overrides,
    )


def _pdf_request(pages: list[str], page: int, **overrides) -> AskRequest:
    return AskRequest(
        file_path="doc.pdf",
        file_data={"kind": "pdf", "pages": pages},
        anchor_start=page,
        anchor_end=page,
        question="what is this section?",
        **overrides,
    )


class TestTextContext:
    def test_windowed_excerpt_includes_anchor(self) -> None:
        content = "\n".join(f"line{i}" for i in range(1, 11))
        ctx = format_context(_text_request(content, 5, 5, context_lines=2))
        assert "line3" in ctx.excerpt
        assert "line5" in ctx.excerpt
        assert "line7" in ctx.excerpt
        # context window of 2 should NOT pull line1 or line10
        assert "line1\n" not in ctx.excerpt
        assert "line10" not in ctx.excerpt

    def test_excerpt_label_reflects_window(self) -> None:
        content = "\n".join(f"line{i}" for i in range(1, 11))
        ctx = format_context(_text_request(content, 5, 5, context_lines=2))
        assert "of 10" in ctx.excerpt_label
        assert ctx.excerpt_label.startswith("lines ")

    def test_full_file_mode(self) -> None:
        content = "a\nb\nc\n"
        ctx = format_context(_text_request(content, 1, 1, full_file=True))
        assert ctx.excerpt_label == "full file"
        assert "a" in ctx.excerpt and "c" in ctx.excerpt

    def test_anchored_text_extracts_range(self) -> None:
        content = "alpha\nbeta\ngamma\ndelta\n"
        ctx = format_context(_text_request(content, 2, 3))
        assert ctx.anchored == "beta\ngamma"
        assert ctx.anchor_label == "lines 2-3"

    def test_single_line_anchor_label(self) -> None:
        content = "a\nb\nc\n"
        ctx = format_context(_text_request(content, 2, 2))
        assert ctx.anchor_label == "line 2"

    def test_empty_content_no_crash(self) -> None:
        ctx = format_context(_text_request("", 1, 1))
        assert ctx.anchored == ""

    def test_excerpt_lines_are_numbered(self) -> None:
        content = "a\nb\nc\n"
        ctx = format_context(_text_request(content, 1, 1, full_file=True))
        # numbered with right-aligned 5-wide column
        assert "    1  a" in ctx.excerpt
        assert "    2  b" in ctx.excerpt


class TestPdfContext:
    def test_anchored_returns_target_page(self) -> None:
        pages = ["one", "two", "three"]
        ctx = format_context(_pdf_request(pages, 2))
        assert ctx.anchored == "two"
        assert ctx.anchor_label == "page 2"

    def test_window_includes_neighbors(self) -> None:
        pages = ["one", "two", "three", "four"]
        ctx = format_context(_pdf_request(pages, 3, context_pages=1))
        assert "--- page 2 ---" in ctx.excerpt
        assert "--- page 3 ---" in ctx.excerpt
        assert "--- page 4 ---" in ctx.excerpt
        assert "--- page 1 ---" not in ctx.excerpt

    def test_full_document_mode(self) -> None:
        pages = ["a", "b"]
        ctx = format_context(_pdf_request(pages, 1, full_file=True))
        assert "full document (2 pages)" == ctx.excerpt_label

    def test_no_pages(self) -> None:
        ctx = format_context(_pdf_request([], 1))
        assert ctx.anchored == ""


def test_build_user_text_includes_question_and_anchor() -> None:
    content = "a = 1\nb = 2\n"
    req = _text_request(content, 1, 2)
    ctx = format_context(req)
    out = build_user_text(req, ctx)
    assert "what does this do?" in out
    assert "a = 1" in out
    assert "```python" in out


def test_build_file_block_includes_path_and_kind() -> None:
    content = "x = 1\n"
    req = _text_request(content, 1, 1)
    ctx = format_context(req)
    out = build_file_block(req, ctx)
    assert "File: a.py" in out
    assert "Kind: text" in out
    assert "x = 1" in out
