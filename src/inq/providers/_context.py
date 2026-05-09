from __future__ import annotations

from dataclasses import dataclass

from .base import AskRequest


@dataclass
class FormattedContext:
    language: str
    excerpt: str  # line-numbered, possibly windowed
    excerpt_label: str  # "lines 12-43 of 156" or "full file"
    anchored: str  # the actual anchored region (raw)


def format_context(req: AskRequest) -> FormattedContext:
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

    return FormattedContext(
        language=language,
        excerpt=excerpt,
        excerpt_label=label,
        anchored=anchored,
    )


SYSTEM_PROMPT = (
    "You are inq, an inline code-reading assistant. The user is reading a file in a "
    "browser viewer and asks questions anchored to specific lines or selections. "
    "Be concise and direct. Quote line numbers when useful. Prefer short answers "
    "over long ones; expand only when asked."
)


def build_user_text(req: AskRequest, ctx: FormattedContext) -> str:
    return (
        f"Anchor: lines {req.anchor_start}-{req.anchor_end}\n"
        f"```{ctx.language}\n{ctx.anchored}\n```\n\n"
        f"Question: {req.question}"
    )


def build_file_block(req: AskRequest, ctx: FormattedContext) -> str:
    return (
        f"File: {req.file_path}\n"
        f"Language: {ctx.language}\n"
        f"Showing: {ctx.excerpt_label}\n\n"
        f"```{ctx.language}\n{ctx.excerpt}\n```"
    )
