from __future__ import annotations

from inq.notes import render_markdown


def _ai_thread(**overrides) -> dict:
    base = {
        "id": "t1",
        "file": "a.py",
        "kind": "text",
        "mode": "ai",
        "language": "python",
        "anchor": {"startLine": 5, "endLine": 8},
        "messages": [
            {"role": "user", "content": "what does this do?"},
            {"role": "assistant", "content": "it sums two numbers."},
        ],
        "createdAt": "2026-05-14T00:00:00Z",
        "updatedAt": "2026-05-14T00:00:00Z",
        "model": "claude-sonnet-4-6",
    }
    base.update(overrides)
    return base


def _comment_thread(**overrides) -> dict:
    base = {
        "id": "c1",
        "file": "a.py",
        "kind": "text",
        "mode": "comment",
        "language": "python",
        "anchor": {"startLine": 12, "endLine": 12},
        "messages": [
            {"role": "user", "content": "TODO refactor this"},
            {"role": "user", "content": "actually, leave it"},
        ],
        "createdAt": "2026-05-14T00:00:00Z",
        "updatedAt": "2026-05-14T00:00:00Z",
    }
    base.update(overrides)
    return base


def test_empty_threads_yields_placeholder() -> None:
    out = render_markdown("local: /tmp", [])
    assert "_(no threads)_" in out
    assert "source: local: /tmp" in out


def test_ai_thread_renders_q_and_a() -> None:
    out = render_markdown("local: /tmp", [_ai_thread()])
    assert "## @ ask · a.py:L5-8" in out
    assert "**Q:** what does this do?" in out
    assert "it sums two numbers." in out
    assert "model: claude-sonnet-4-6" in out


def test_single_line_anchor_uses_short_form() -> None:
    out = render_markdown("local: /tmp", [_ai_thread(anchor={"startLine": 7, "endLine": 7})])
    assert "a.py:L7" in out
    assert "L7-7" not in out


def test_pdf_anchor_uses_page_form() -> None:
    out = render_markdown("local: /tmp", [_ai_thread(kind="pdf", anchor={"startLine": 3, "endLine": 3})])
    assert "a.py:p3" in out


def test_comment_renders_as_bullets() -> None:
    out = render_markdown("local: /tmp", [_comment_thread()])
    assert "## # note · a.py:L12" in out
    assert "- TODO refactor this" in out
    assert "- actually, leave it" in out
    # comments don't get Q: prefix
    assert "**Q:**" not in out


def test_comment_preserves_existing_bullets() -> None:
    t = _comment_thread(messages=[{"role": "user", "content": "- already a bullet\nfollow up line"}])
    out = render_markdown("local: /tmp", [t])
    assert "- already a bullet" in out
    assert "- follow up line" in out


def test_filter_file_scopes_output() -> None:
    a = _ai_thread()
    b = _ai_thread(id="t2", file="b.py", anchor={"startLine": 1, "endLine": 1})
    out = render_markdown("local: /tmp", [a, b], filter_file="a.py")
    assert "a.py" in out
    assert "b.py" not in out
    assert "file: a.py" in out


def test_error_renders_when_present() -> None:
    out = render_markdown("local: /tmp", [_ai_thread(error="rate limited")])
    assert "_error: rate limited_" in out


def test_threads_separated_by_hr() -> None:
    out = render_markdown("local: /tmp", [_ai_thread(), _ai_thread(id="t2")])
    assert out.count("\n---\n") >= 2
