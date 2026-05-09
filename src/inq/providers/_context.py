from __future__ import annotations

from dataclasses import dataclass

from .base import AskRequest


@dataclass
class FormattedContext:
    language: str
    excerpt: str  # numbered/labelled body for the system block
    excerpt_label: str  # "lines 12-43 of 156" / "pages 2-4 of 12" / "full file"
    anchored: str  # the actual anchored region (raw)
    anchor_label: str  # "lines 12-15" or "page 3"


def format_context(req: AskRequest) -> FormattedContext:
    kind = req.file_data.get("kind", "text")
    if kind == "pdf":
        return _format_pdf(req)
    return _format_text(req)


def _format_text(req: AskRequest) -> FormattedContext:
    content = req.file_data.get("content", "") or ""
    language = req.file_data.get("language", "text") or "text"
    lines = content.splitlines()
    n = len(lines)

    if req.full_file or n == 0:
        numbered = "\n".join(f"{i + 1:>5}  {line}" for i, line in enumerate(lines))
        excerpt = numbered if numbered else content
        label = "full file"
    else:
        start = max(0, req.anchor_start - 1 - req.context_lines)
        end = min(n, req.anchor_end + req.context_lines)
        excerpt_lines = lines[start:end]
        excerpt = "\n".join(
            f"{i + 1:>5}  {line}" for i, line in enumerate(excerpt_lines, start=start)
        )
        label = f"lines {start + 1}-{end} of {n}"

    s = max(1, req.anchor_start)
    e = min(n, req.anchor_end)
    anchored = "\n".join(lines[s - 1:e]) if e >= s else ""
    anchor_label = f"lines {s}-{e}" if e > s else f"line {s}"

    return FormattedContext(
        language=language,
        excerpt=excerpt,
        excerpt_label=label,
        anchored=anchored,
        anchor_label=anchor_label,
    )


def _format_pdf(req: AskRequest) -> FormattedContext:
    pages: list[str] = req.file_data.get("pages") or []
    n = len(pages)
    page_num = max(1, req.anchor_start)
    page_num = min(n, page_num) if n else page_num

    if req.full_file or n == 0:
        excerpt = "\n\n".join(
            f"--- page {i + 1} ---\n{p}" for i, p in enumerate(pages)
        )
        label = f"full document ({n} pages)"
    else:
        win = max(0, req.context_pages)
        start = max(1, page_num - win)
        end = min(n, page_num + win)
        excerpt = "\n\n".join(
            f"--- page {i} ---\n{pages[i - 1]}" for i in range(start, end + 1)
        )
        label = (
            f"page {page_num}"
            if start == end == page_num
            else f"pages {start}-{end} of {n}"
        )

    anchored = pages[page_num - 1] if 1 <= page_num <= n else ""
    return FormattedContext(
        language="pdf",
        excerpt=excerpt,
        excerpt_label=label,
        anchored=anchored,
        anchor_label=f"page {page_num}",
    )


SYSTEM_PROMPT = (
    "You are inq, an inline reading assistant. The user is reading a file in a "
    "browser viewer and asks questions anchored to specific lines, selections, or "
    "pages. Be concise and direct. Quote line/page numbers when useful. Prefer "
    "short answers over long ones; expand only when asked."
)


def build_user_text(req: AskRequest, ctx: FormattedContext) -> str:
    fence = ctx.language if ctx.language and ctx.language != "pdf" else "text"
    return (
        f"Anchor: {ctx.anchor_label}\n"
        f"```{fence}\n{ctx.anchored}\n```\n\n"
        f"Question: {req.question}"
    )


def build_file_block(req: AskRequest, ctx: FormattedContext) -> str:
    fence = ctx.language if ctx.language and ctx.language != "pdf" else "text"
    return (
        f"File: {req.file_path}\n"
        f"Kind: {req.file_data.get('kind', 'text')}\n"
        f"Showing: {ctx.excerpt_label}\n\n"
        f"```{fence}\n{ctx.excerpt}\n```"
    )
