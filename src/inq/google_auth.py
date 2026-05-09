"""Google OAuth via the loopback redirect flow.

Why loopback (not device flow): Google's "Desktop app" client type does not
support the OAuth 2.0 device authorization grant; that flow requires a "TVs
and Limited Input devices" client. Loopback works for any context where the
user can reach a localhost port from a browser — i.e., when ``inq auth google``
runs on the same machine as the user's browser. For SSH-forwarded inq, run
``inq auth google`` locally and then copy the resulting credentials file to
the remote host (or rely on shared $HOME).
"""

from __future__ import annotations

import http.server
import json
import os
import secrets
import socket
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path


CREDENTIALS_PATH = Path(
    os.environ.get("INQ_GOOGLE_CREDS")
    or (Path.home() / ".config" / "inq" / "credentials" / "google.json")
)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

DEFAULT_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


@dataclass
class GoogleCredentials:
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: str
    expiry: float  # epoch seconds
    scopes: list[str]

    def is_expired(self, skew: int = 60) -> bool:
        return time.time() + skew >= self.expiry

    def to_json(self) -> dict:
        return {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expiry": self.expiry,
            "scopes": self.scopes,
        }

    @classmethod
    def from_json(cls, d: dict) -> "GoogleCredentials":
        return cls(
            client_id=d["client_id"],
            client_secret=d["client_secret"],
            access_token=d["access_token"],
            refresh_token=d["refresh_token"],
            expiry=float(d.get("expiry", 0)),
            scopes=list(d.get("scopes", [])),
        )


def load_credentials(path: Path = CREDENTIALS_PATH) -> GoogleCredentials | None:
    if not path.is_file():
        return None
    try:
        return GoogleCredentials.from_json(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def save_credentials(creds: GoogleCredentials, path: Path = CREDENTIALS_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(creds.to_json(), indent=2)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


# -------- loopback flow ---------------------------------------------------


def _free_localhost_port() -> int:
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    captured: dict | None = None  # set by the loopback server below

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        parsed = urllib.parse.urlsplit(self.path)
        params = dict(urllib.parse.parse_qsl(parsed.query))

        # Only the OAuth redirect carries a `code` or `error` param. Browsers
        # also auto-request /favicon.ico after rendering the success page;
        # those (and any other stray GETs) must not overwrite the real capture.
        if type(self).captured is None and ("code" in params or "error" in params):
            type(self).captured = params

        # Quietly 204 the favicon so the browser stops trying.
        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        body = (
            "<html><body style=\"font-family:ui-monospace,Menlo,Consolas,monospace;"
            "background:#0c0d0e;color:#e3e6e4;padding:40px\">"
            "<h2 style=\"color:#ffa657\">inq · authentication complete</h2>"
            "<p>You can close this tab and return to your terminal.</p>"
            "</body></html>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *_args, **_kwargs) -> None:  # silence stdout noise
        pass


def authorize_loopback(
    client_id: str,
    client_secret: str,
    *,
    scopes: list[str] | None = None,
    open_browser: bool = True,
) -> GoogleCredentials:
    """Run the Google OAuth 2.0 loopback flow and return fresh credentials.

    Spins up a one-shot HTTP server on a random localhost port, builds the
    auth URL with that as ``redirect_uri``, opens the user's browser, and
    waits for the callback that carries the authorization code. Then exchanges
    the code for an access + refresh token pair.
    """
    scopes = list(scopes or DEFAULT_SCOPES)
    state = secrets.token_urlsafe(16)
    port = _free_localhost_port()
    redirect_uri = f"http://127.0.0.1:{port}/"

    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "include_granted_scopes": "true",
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(auth_params)}"

    # Fresh per-call subclass so the captured state doesn't leak across calls.
    class Handler(_CallbackHandler):
        captured = None

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print(f"open this URL to authorize inq:\n  {auth_url}\n")
    if open_browser:
        try:
            webbrowser.open(auth_url, new=2)
        except Exception:
            pass

    try:
        deadline = time.time() + 600  # 10 minutes
        while Handler.captured is None:
            if time.time() > deadline:
                raise TimeoutError("timed out waiting for OAuth callback")
            time.sleep(0.2)
        params = Handler.captured
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    if params.get("state") != state:
        raise RuntimeError("OAuth state mismatch — possible CSRF; aborting")
    if "error" in params:
        raise RuntimeError(f"OAuth error: {params['error']}")
    code = params.get("code")
    if not code:
        raise RuntimeError("OAuth callback missing 'code'")

    return _exchange_code(
        client_id=client_id,
        client_secret=client_secret,
        code=code,
        redirect_uri=redirect_uri,
        scopes=scopes,
    )


def _exchange_code(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    scopes: list[str],
) -> GoogleCredentials:
    body = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("ascii")
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.loads(r.read().decode("utf-8"))

    return GoogleCredentials(
        client_id=client_id,
        client_secret=client_secret,
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token", ""),
        expiry=time.time() + float(payload.get("expires_in", 3600)),
        scopes=scopes,
    )


def refresh(creds: GoogleCredentials) -> GoogleCredentials:
    """Use the refresh token to get a fresh access token. Returns a new creds."""
    if not creds.refresh_token:
        raise RuntimeError("no refresh_token on file; run `inq auth google` again")
    body = urllib.parse.urlencode(
        {
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "refresh_token": creds.refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode("ascii")
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.loads(r.read().decode("utf-8"))

    return GoogleCredentials(
        client_id=creds.client_id,
        client_secret=creds.client_secret,
        access_token=payload["access_token"],
        # Google may rotate the refresh_token; if not present, keep the old one.
        refresh_token=payload.get("refresh_token") or creds.refresh_token,
        expiry=time.time() + float(payload.get("expires_in", 3600)),
        scopes=creds.scopes,
    )


def ensure_fresh(creds: GoogleCredentials) -> GoogleCredentials:
    """Return the creds, refreshing them on disk if expired."""
    if not creds.is_expired():
        return creds
    new_creds = refresh(creds)
    save_credentials(new_creds)
    return new_creds
