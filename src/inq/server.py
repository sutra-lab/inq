from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import __version__
from .providers import AskRequest as ProviderAskRequest
from .providers import Provider, StreamEvent
from .sources import FileNotFound, FileSource, NotADirectory, NotAFile, SourceError
from .threads import StoredThread, ThreadStore


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
    context_pages: int = Field(default=1, ge=0, le=20)
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
    except Exception as exc:
        yield _sse("error", f"{type(exc).__name__}: {exc}")
    finally:
        yield _sse("done", "")


def create_app(
    *,
    source: FileSource,
    provider: Provider,
    threads: ThreadStore,
    dev: bool = False,
) -> FastAPI:
    app = FastAPI(title="inq", version=__version__)

    if dev:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(FileNotFound)
    async def _fnf(_: Request, __: FileNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "not found"})

    @app.exception_handler(NotADirectory)
    async def _nad(_: Request, __: NotADirectory) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "not a directory"})

    @app.exception_handler(NotAFile)
    async def _naf(_: Request, __: NotAFile) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "not a file"})

    @app.exception_handler(SourceError)
    async def _se(_: Request, exc: SourceError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.get("/api/health")
    def health() -> dict:
        return {
            "ok": True,
            "version": __version__,
            "source": source.label,
            "provider": provider.name,
            "model": provider.model,
        }

    @app.get("/api/tree")
    def get_tree(path: str = "", depth: int = Query(default=1, ge=1, le=6)) -> dict:
        return source.list_dir(path, depth)

    @app.get("/api/file")
    def get_file(path: str = Query(...)) -> dict:
        return source.read_metadata(path)

    @app.get("/api/raw")
    def get_raw(path: str = Query(...)) -> FileResponse:
        local_path, mime = source.open_raw(path)
        return FileResponse(local_path, media_type=mime)

    @app.post("/api/ask")
    async def ask(req: AskHTTPRequest) -> StreamingResponse:
        try:
            file_data = source.read_for_ai(req.file)
        except FileNotFound:
            raise HTTPException(status_code=404, detail="file not found")
        except NotAFile:
            raise HTTPException(status_code=400, detail="not a file")
        except SourceError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        if req.anchor.endLine < req.anchor.startLine:
            raise HTTPException(status_code=400, detail="anchor.endLine < anchor.startLine")

        provider_req = ProviderAskRequest(
            file_path=req.file,
            file_data=file_data,
            anchor_start=req.anchor.startLine,
            anchor_end=req.anchor.endLine,
            question=req.question,
            history=[h.model_dump() for h in req.history],
            context_lines=req.context_lines,
            context_pages=req.context_pages,
            full_file=req.full_file,
        )

        return StreamingResponse(
            _to_sse(provider.stream(provider_req)),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/threads")
    def list_threads() -> dict:
        return {"source": source.label, "threads": threads.list()}

    @app.post("/api/threads")
    def upsert_thread(thread: StoredThread) -> dict:
        try:
            return threads.upsert(thread.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.delete("/api/threads/{thread_id}")
    def delete_thread(thread_id: str) -> dict:
        ok = threads.delete(thread_id)
        if not ok:
            raise HTTPException(status_code=404, detail="thread not found")
        return {"ok": True, "id": thread_id}

    return app
