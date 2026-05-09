from __future__ import annotations

from datetime import datetime, timezone


def _anchor_str(thread: dict) -> str:
    a = thread.get("anchor") or {}
    s = a.get("startLine", 1)
    e = a.get("endLine", s)
    if thread.get("kind") == "pdf":
        return f"p{s}"
    if s == e:
        return f"L{s}"
    return f"L{s}-{e}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def render_markdown(
    source_label: str,
    threads: list[dict],
    *,
    filter_file: str | None = None,
) -> str:
    """Render a list of stored threads as agent-consumable markdown.

    AI threads use ``**Q:**`` for user turns followed by the assistant text.
    Comment threads render user messages as bullet items.
    """
    rows = (
        [t for t in threads if t.get("file") == filter_file] if filter_file else list(threads)
    )

    out: list[str] = []
    out.append("# inq notes")
    out.append(f"source: {source_label}")
    out.append(f"exported: {_now_iso()}")
    if filter_file:
        out.append(f"file: {filter_file}")
    out.append("")

    if not rows:
        out.append("_(no threads)_")
        out.append("")
        return "\n".join(out)

    for t in rows:
        mode = t.get("mode") or "ai"
        sigil = "#" if mode == "comment" else "@"
        verb = "note" if mode == "comment" else "ask"
        out.append(f"## {sigil} {verb} · {t.get('file', '?')}:{_anchor_str(t)}")
        meta: list[str] = []
        if t.get("createdAt"):
            meta.append(f"created: {t['createdAt']}")
        if mode == "ai" and t.get("model"):
            meta.append(f"model: {t['model']}")
        if meta:
            out.append(" · ".join(meta))
        out.append("")

        msgs = t.get("messages") or []
        if mode == "comment":
            for m in msgs:
                if m.get("role") != "user":
                    continue
                lines = (m.get("content") or "").splitlines() or [""]
                for line in lines:
                    line = line.rstrip()
                    if not line:
                        out.append("")
                    elif line.startswith(("- ", "* ")):
                        out.append(line)
                    else:
                        out.append(f"- {line}")
                out.append("")
        else:
            for m in msgs:
                role = m.get("role")
                content = (m.get("content") or "").rstrip()
                if not content:
                    continue
                if role == "user":
                    out.append(f"**Q:** {content}")
                elif role == "assistant":
                    out.append(content)
                out.append("")

        if t.get("error"):
            out.append(f"_error: {t['error']}_")
            out.append("")

        out.append("---")
        out.append("")

    return "\n".join(out).rstrip() + "\n"
