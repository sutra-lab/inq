from __future__ import annotations

import json
import re
import secrets
import time
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from . import google_auth
from .config import load_config
from .providers import AskRequest as ProviderAskRequest
from .providers import Provider, StreamEvent
from .registry import SourceRegistry
from .sources import DriveSource, FileNotFound, NotADirectory, NotAFile, SourceError
from .threads import StoredThread


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


class AddDriveSourceRequest(BaseModel):
    folder: str  # accepts a Drive URL or just a folder id


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


_FOLDER_URL_RE = re.compile(r"/folders/([A-Za-z0-9_-]+)")


def _extract_folder_id(spec: str) -> str:
    spec = spec.strip()
    m = _FOLDER_URL_RE.search(spec)
    if m:
        return m.group(1)
    return spec


def _slugify(label: str) -> str:
    """Make a stable id from a human label like 'drive: My Folder'."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", label).strip("-").lower()
    return s or "src"


def create_app(
    *,
    registry: SourceRegistry,
    provider: Provider,
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

    def _entry(source_id: str):
        try:
            return registry.get(source_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown source: {source_id}")

    # --- core data API --------------------------------------------------

    @app.get("/api/health")
    def health() -> dict:
        return {
            "ok": True,
            "version": __version__,
            "default_source": registry.default_id,
            "provider": provider.name,
            "model": provider.model,
        }

    @app.get("/api/tree")
    def get_tree(
        source: str = Query(default=None),
        path: str = "",
        depth: int = Query(default=1, ge=1, le=6),
    ) -> dict:
        e = _entry(source or registry.default_id)
        return e.source.list_dir(path, depth)

    @app.get("/api/file")
    def get_file(path: str = Query(...), source: str = Query(default=None)) -> dict:
        e = _entry(source or registry.default_id)
        return e.source.read_metadata(path)

    @app.get("/api/raw")
    def get_raw(path: str = Query(...), source: str = Query(default=None)) -> FileResponse:
        e = _entry(source or registry.default_id)
        local_path, mime = e.source.open_raw(path)
        return FileResponse(local_path, media_type=mime)

    @app.post("/api/ask")
    async def ask(
        req: AskHTTPRequest,
        source: str = Query(default=None),
    ) -> StreamingResponse:
        e = _entry(source or registry.default_id)
        try:
            file_data = e.source.read_for_ai(req.file)
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

    # --- threads (per-source) -------------------------------------------

    @app.get("/api/threads")
    def list_threads(source: str = Query(default=None)) -> dict:
        e = _entry(source or registry.default_id)
        return {"source": e.label, "threads": e.threads.list()}

    @app.post("/api/threads")
    def upsert_thread(thread: StoredThread, source: str = Query(default=None)) -> dict:
        e = _entry(source or registry.default_id)
        try:
            return e.threads.upsert(thread.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.delete("/api/threads/{thread_id}")
    def delete_thread(thread_id: str, source: str = Query(default=None)) -> dict:
        e = _entry(source or registry.default_id)
        ok = e.threads.delete(thread_id)
        if not ok:
            raise HTTPException(status_code=404, detail="thread not found")
        return {"ok": True, "id": thread_id}

    # --- sources --------------------------------------------------------

    @app.get("/api/sources")
    def list_sources() -> dict:
        return {"default": registry.default_id, "sources": registry.list()}

    @app.post("/api/sources/drive")
    def add_drive_source(req: AddDriveSourceRequest) -> dict:
        folder_id = _extract_folder_id(req.folder)
        if not folder_id:
            raise HTTPException(status_code=400, detail="missing folder id")
        # Quick auth precheck so the failure is clear if /api/google_auth wasn't run.
        if google_auth.load_credentials() is None:
            raise HTTPException(
                status_code=412,
                detail="google_auth_required",
            )
        try:
            ds = DriveSource(folder_id=folder_id)
        except FileNotFound:
            # 404 from Drive: either the folder really doesn't exist OR the
            # currently-authed account can't see it. We can't tell from the
            # API; assume the more common "wrong account" case and offer the
            # account picker.
            raise HTTPException(
                status_code=412,
                detail="google_account_mismatch",
            )
        except SourceError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        # id is stable per folder so opening the same folder twice doesn't dupe.
        sid = f"drive-{folder_id[:12]}"
        try:
            entry = registry.add(sid, "drive", ds)
        except ValueError:
            entry = registry.get(sid)
        return {
            "id": entry.id,
            "kind": entry.kind,
            "label": entry.label,
        }

    @app.delete("/api/sources/{source_id}")
    def remove_source(source_id: str) -> dict:
        ok = registry.remove(source_id)
        if not ok:
            raise HTTPException(status_code=400, detail="cannot remove this source")
        return {"ok": True, "id": source_id}

    # --- google_auth: in-browser web flow ------------------------------
    #
    # state[token] -> dict(redirect_uri, scopes, created)  — single-use.
    auth_states: dict[str, dict] = {}
    _STATE_TTL = 600  # seconds

    def _client_creds() -> tuple[str, str]:
        cfg = load_config()
        cid = cfg.google_oauth.client_id
        cs = cfg.google_oauth.client_secret
        if not cid or not cs:
            raise HTTPException(
                status_code=412,
                detail=(
                    "google oauth client not configured. add to "
                    "~/.config/inq/config.toml [google_oauth] or set "
                    "GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET, "
                    "or store in macOS keychain (service=inq, "
                    "account=google_oauth_client_{id,secret})."
                ),
            )
        return cid, cs

    @app.get("/api/google_auth/status")
    def auth_status() -> dict:
        cfg = load_config()
        client_configured = bool(
            cfg.google_oauth.client_id and cfg.google_oauth.client_secret
        )
        creds = google_auth.load_credentials()
        return {
            "client_configured": client_configured,
            "authenticated": creds is not None,
            "scopes": creds.scopes if creds else [],
        }

    @app.get("/api/google_auth/start")
    def auth_start(
        request: Request,
        prompt: str = "consent",
    ) -> RedirectResponse:
        cid, _ = _client_creds()
        # Garbage-collect old states.
        cutoff = time.time() - _STATE_TTL
        for k in list(auth_states):
            if auth_states[k]["created"] < cutoff:
                auth_states.pop(k, None)

        # Whitelist the prompt values we accept.
        if prompt not in {"consent", "select_account", "select_account consent"}:
            prompt = "consent"

        state = secrets.token_urlsafe(24)
        base = str(request.base_url).rstrip("/")
        redirect_uri = f"{base}/api/google_auth/callback"
        auth_states[state] = {
            "redirect_uri": redirect_uri,
            "scopes": list(google_auth.DEFAULT_SCOPES),
            "created": time.time(),
        }
        url = google_auth.build_auth_url(
            client_id=cid,
            redirect_uri=redirect_uri,
            state=state,
            scopes=google_auth.DEFAULT_SCOPES,
            prompt=prompt,
        )
        return RedirectResponse(url=url, status_code=302)

    @app.get("/api/google_auth/callback")
    def auth_callback(
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
    ) -> HTMLResponse:
        def _page(title: str, body: str, ok: bool) -> HTMLResponse:
            color = "#ffa657" if ok else "#ff7066"
            html = f"""<!doctype html><html><head><title>{title}</title></head>
<body style="font-family:ui-monospace,Menlo,Consolas,monospace;background:#0c0d0e;color:#e3e6e4;padding:40px;margin:0">
  <h2 style="color:{color}">{title}</h2>
  <p>{body}</p>
  <p style="color:#8a8f93">you can close this window.</p>
  <script>
    try {{
      if (window.opener) {{
        window.opener.postMessage(
          {{type: 'inq:google_auth', ok: {str(ok).lower()}}},
          '*'
        )
      }}
    }} catch (e) {{}}
    setTimeout(() => {{ try {{ window.close() }} catch (e) {{}} }}, 800)
  </script>
</body></html>"""
            return HTMLResponse(content=html, status_code=200 if ok else 400)

        if error:
            return _page("inq · auth failed", f"google said: {error}", ok=False)
        if not code or not state:
            return _page("inq · auth failed", "missing code or state in callback", ok=False)
        info = auth_states.pop(state, None)
        if info is None:
            return _page(
                "inq · auth failed",
                "unknown or expired auth state. start over.",
                ok=False,
            )
        try:
            cid, cs = _client_creds()
            creds = google_auth.exchange_code(
                client_id=cid,
                client_secret=cs,
                code=code,
                redirect_uri=info["redirect_uri"],
                scopes=info["scopes"],
            )
            google_auth.save_credentials(creds)
        except Exception as exc:
            return _page(
                "inq · auth failed",
                f"{type(exc).__name__}: {exc}",
                ok=False,
            )
        return _page(
            "inq · authentication complete",
            "scope granted: drive.readonly",
            ok=True,
        )

    # --- static frontend (built via `cd web && npm run build`) ----------
    # mounted last so /api/* and the named routes above win over it.
    web_dir = Path(__file__).parent / "web"
    if web_dir.is_dir() and (web_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")

    return app
