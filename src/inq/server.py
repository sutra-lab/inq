from __future__ import annotations

import json
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import __version__
from .providers import AskRequest as ProviderAskRequest
from .providers import Provider, StreamEvent
from .sandbox import GitignoreFilter, list_dir, read_file, resolve_within


class Anchor(BaseModel):
    startLine: int = Field(ge=1)
    endLine: int = Field(ge=1)


class HistoryMessage(BaseModel):
    role: str
    content: str


class AskHTTPRequest(BaseModel):
    question: str
    file: str
    anchor: Anchor
    context_lines: int = Field(default=20, ge=0, le=2000)
    full_file: bool = False
    history: list[HistoryMessage] = Field(default_factory=list)


def _sse(event: str, data: str) -> bytes:
    safe = data.replace("\r\n", "\n").replace("\n", "\ndata: ")
    return f"event: {event}\ndata: {safe}\n\n".encode("utf-8")


async def _to_sse(events: AsyncIterator[StreamEvent]) -> AsyncIterator[bytes]:
    try:
        async for ev in events:
            if ev.type == "token":
                yield _sse("token", str(ev.data))
            elif ev.type == "start":
                yield _sse("start", json.dumps(ev.data))
            elif ev.type == "usage":
                yield _sse("usage", json.dumps(ev.data))
            elif ev.type == "error":
                yield _sse("error", str(ev.data))
            else:
                yield _sse(ev.type, str(ev.data))
    except Exception as exc:  # provider-level crash
        yield _sse("error", f"{type(exc).__name__}: {exc}")
    finally:
        yield _sse("done", "")


def create_app(
    *,
    root: Path,
    provider: Provider,
    max_file_size: int = 2 * 1024 * 1024,
    dev: bool = False,
) -> FastAPI:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"root is not a directory: {root}")

    gi = GitignoreFilter(root)

    app = FastAPI(title="inq", version=__version__)

    if dev:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/api/health")
    def health() -> dict:
        return {
            "ok": True,
            "version": __version__,
            "root": str(root),
            "provider": provider.name,
            "model": provider.model,
        }

    @app.get("/api/tree")
    def get_tree(path: str = "", depth: int = Query(default=1, ge=1, le=6)) -> dict:
        try:
            base = resolve_within(root, path) if path else root
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if not base.exists():
            raise HTTPException(status_code=404, detail="not found")
        if not base.is_dir():
            raise HTTPException(status_code=400, detail="not a directory")
        return list_dir(base, root, gi, depth)

    @app.get("/api/file")
    def get_file(path: str = Query(...)) -> dict:
        try:
            abs_path = resolve_within(root, path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if not abs_path.exists():
            raise HTTPException(status_code=404, detail="not found")
        if not abs_path.is_file():
            raise HTTPException(status_code=400, detail="not a file")
        data = read_file(abs_path, max_file_size)
        return {"path": path, **data}

    @app.post("/api/ask")
    async def ask(req: AskHTTPRequest) -> StreamingResponse:
        try:
            abs_path = resolve_within(root, req.file)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if not abs_path.is_file():
            raise HTTPException(status_code=404, detail="file not found")
        if req.anchor.endLine < req.anchor.startLine:
            raise HTTPException(status_code=400, detail="anchor.endLine < anchor.startLine")

        file_data = read_file(abs_path, max_file_size)

        provider_req = ProviderAskRequest(
            file_path=req.file,
            file_data=file_data,
            anchor_start=req.anchor.startLine,
            anchor_end=req.anchor.endLine,
            question=req.question,
            history=[h.model_dump() for h in req.history],
            context_lines=req.context_lines,
            full_file=req.full_file,
        )

        return StreamingResponse(
            _to_sse(provider.stream(provider_req)),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app
