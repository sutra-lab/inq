"""Google Drive as a read-only FileSource.

Uses Drive API v3 over plain ``urllib``. ``path`` here is the Drive file id
(stable, no name-collision concerns). Each instance is rooted at a folder id.

Supported content kinds:
  - PDFs                          → kind="pdf" (page-anchored, served via /raw)
  - text/* and json/xml           → kind="text" (read in full)
  - application/vnd.google-apps.document  → exported as text/plain (kind="text")
  - everything else               → kind="binary"
"""

from __future__ import annotations

import json
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .. import google_auth
from ..sandbox import language_for
from .base import FileNotFound, NotAFile, SourceError


DRIVE_API = "https://www.googleapis.com/drive/v3"

# Google-native types we know how to export to text.
GOOGLE_DOC_EXPORTS = {
    "application/vnd.google-apps.document": "text/plain",
}

FOLDER_MIME = "application/vnd.google-apps.folder"


class DriveSource:
    def __init__(self, folder_id: str, max_file_size: int = 10 * 1024 * 1024) -> None:
        creds = google_auth.load_credentials()
        if creds is None:
            raise SourceError(
                "no google credentials on file. run `inq auth google` first."
            )
        self._creds = google_auth.ensure_fresh(creds)
        self.folder_id = folder_id
        self.max_file_size = max_file_size
        self._tempdir = Path(tempfile.mkdtemp(prefix="inq-drive-"))

        # Let FileNotFound propagate. Drive returns 404 both when the folder
        # truly doesn't exist and when it exists but isn't visible to the
        # currently-authenticated google account. The server layer treats
        # this as "wrong account" and offers an account-picker re-auth.
        meta = self._api_get(
            f"/files/{folder_id}",
            params={"fields": "id,name,mimeType"},
        )
        if meta.get("mimeType") != FOLDER_MIME:
            raise SourceError(f"not a folder: {folder_id} (got {meta.get('mimeType')})")
        self.root_name = meta.get("name", folder_id)
        self.label = f"drive: {self.root_name}"

    def __del__(self) -> None:  # best-effort temp cleanup
        try:
            shutil.rmtree(self._tempdir, ignore_errors=True)
        except Exception:
            pass

    # -- HTTP -------------------------------------------------------------

    def _auth_headers(self) -> dict:
        self._creds = google_auth.ensure_fresh(self._creds)
        return {"Authorization": f"Bearer {self._creds.access_token}"}

    def _api_get(self, path: str, params: dict | None = None) -> dict:
        url = f"{DRIVE_API}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=self._auth_headers())
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise FileNotFound(path)
            body = e.read().decode("utf-8", "replace") if hasattr(e, "read") else ""
            raise SourceError(f"drive api {e.code}: {body[:200]}")

    def _api_get_bytes(self, path: str, params: dict | None = None) -> bytes:
        url = f"{DRIVE_API}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=self._auth_headers())
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise FileNotFound(path)
            body = e.read().decode("utf-8", "replace") if hasattr(e, "read") else ""
            raise SourceError(f"drive api {e.code}: {body[:200]}")

    # -- FileSource API ---------------------------------------------------

    def list_dir(self, path: str = "", depth: int = 1) -> dict:
        folder_id = path or self.folder_id
        children = self._list_children(folder_id, depth)
        return {
            "path": "" if folder_id == self.folder_id else folder_id,
            "children": children,
        }

    def _list_children(self, folder_id: str, depth: int) -> list[dict]:
        if depth <= 0:
            return []
        items: list[dict] = []
        page_token: str | None = None
        while True:
            params = {
                "q": f"'{folder_id}' in parents and trashed = false",
                "fields": "nextPageToken, files(id,name,mimeType,size,modifiedTime)",
                "pageSize": "1000",
                "orderBy": "folder,name",
            }
            if page_token:
                params["pageToken"] = page_token
            data = self._api_get("/files", params)
            for f in data.get("files", []):
                is_dir = f.get("mimeType") == FOLDER_MIME
                node = {
                    "name": f["name"],
                    "path": f["id"],
                    "type": "dir" if is_dir else "file",
                }
                if is_dir and depth > 1:
                    node["children"] = self._list_children(f["id"], depth - 1)
                items.append(node)
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return items

    def read_metadata(self, path: str) -> dict:
        meta = self._api_get(
            f"/files/{path}",
            params={"fields": "id,name,mimeType,size,modifiedTime"},
        )
        if meta.get("mimeType") == FOLDER_MIME:
            raise NotAFile(path)
        size = int(meta.get("size") or 0)
        name = meta.get("name", path)
        mime = meta.get("mimeType", "")

        if size and size > self.max_file_size:
            return {
                "path": path,
                "name": name,
                "kind": "skipped",
                "size": size,
                "skipped": "too_large",
            }

        if mime == "application/pdf":
            local = self._download(path, mime)
            try:
                from pypdf import PdfReader

                reader = PdfReader(str(local))
                page_count = len(reader.pages)
            except Exception as exc:
                return {
                    "path": path,
                    "name": name,
                    "kind": "skipped",
                    "size": size,
                    "skipped": f"pdf: {exc}",
                }
            return {
                "path": path,
                "name": name,
                "kind": "pdf",
                "size": size,
                "page_count": page_count,
            }

        if mime in GOOGLE_DOC_EXPORTS:
            try:
                content = self._api_get_bytes(
                    f"/files/{path}/export",
                    params={"mimeType": GOOGLE_DOC_EXPORTS[mime]},
                ).decode("utf-8", errors="replace")
            except SourceError as exc:
                return {
                    "path": path,
                    "name": name,
                    "kind": "skipped",
                    "size": size,
                    "skipped": f"export: {exc}",
                }
            return {
                "path": path,
                "name": name,
                "kind": "text",
                "size": len(content.encode("utf-8")),
                "language": "markdown",
                "content": content,
            }

        if mime.startswith("text/") or mime in ("application/json", "application/xml"):
            try:
                content = self._api_get_bytes(
                    f"/files/{path}",
                    params={"alt": "media"},
                ).decode("utf-8", errors="replace")
            except SourceError as exc:
                return {
                    "path": path,
                    "name": name,
                    "kind": "skipped",
                    "size": size,
                    "skipped": f"download: {exc}",
                }
            return {
                "path": path,
                "name": name,
                "kind": "text",
                "size": len(content.encode("utf-8")),
                "language": language_for(Path(name)),
                "content": content,
            }

        return {
            "path": path,
            "name": name,
            "kind": "binary",
            "size": size,
            "skipped": "binary",
        }

    def read_for_ai(self, path: str) -> dict:
        meta = self.read_metadata(path)
        if meta.get("kind") != "pdf":
            return meta
        local = self._tempdir / f"{path}.pdf"
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(local))
            pages = [p.extract_text() or "" for p in reader.pages]
        except Exception as exc:
            return {
                "path": path,
                "name": meta.get("name"),
                "kind": "skipped",
                "size": meta.get("size", 0),
                "skipped": f"pdf-extract: {exc}",
            }
        return {**meta, "pages": pages}

    def open_raw(self, path: str) -> tuple[Path, str]:
        meta = self._api_get(f"/files/{path}", params={"fields": "id,mimeType"})
        mime = meta.get("mimeType", "application/octet-stream")
        if mime == FOLDER_MIME:
            raise NotAFile(path)
        local = self._download(path, mime)
        return local, mime

    # -- helpers ----------------------------------------------------------

    def _download(self, file_id: str, mime: str) -> Path:
        suffix = ".pdf" if mime == "application/pdf" else ""
        local = self._tempdir / f"{file_id}{suffix}"
        if local.is_file():
            return local
        if mime in GOOGLE_DOC_EXPORTS:
            data = self._api_get_bytes(
                f"/files/{file_id}/export",
                params={"mimeType": GOOGLE_DOC_EXPORTS[mime]},
            )
        else:
            data = self._api_get_bytes(f"/files/{file_id}", params={"alt": "media"})
        local.write_bytes(data)
        return local
