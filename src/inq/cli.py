from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import uvicorn

from . import __version__, google_auth
from .config import load_config, resolve_runtime
from .init_cmd import run_init
from .notes import render_markdown
from .providers import known_providers, make_provider
from .registry import SourceRegistry
from .server import create_app
from .sources import DriveSource, LocalSource, SourceError
from .threads import ThreadStore


def _parse_size(s: str) -> int:
    s = s.strip().lower()
    units = {"k": 1024, "m": 1024**2, "g": 1024**3}
    if s and s[-1] in units:
        return int(float(s[:-1]) * units[s[-1]])
    return int(s)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="inq",
        description="Terminal-native web UI for AI-assisted code review.",
    )
    p.add_argument("--version", action="version", version=f"inq {__version__}")

    sub = p.add_subparsers(dest="command")

    init = sub.add_parser("init", help="Configure the AI provider and key.")
    init.set_defaults(_action="init")

    serve = sub.add_parser("serve", help="Run the inq server (default).")
    _add_serve_args(serve)
    serve.set_defaults(_action="serve")

    notes = sub.add_parser(
        "notes",
        help="Print saved threads (Q&A and notes) for a directory as markdown.",
    )
    notes.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="directory whose threads to print (default cwd)",
    )
    notes.add_argument(
        "--file",
        default=None,
        help="filter to threads anchored to this file path (relative to --root)",
    )
    notes.add_argument("--json", action="store_true", help="emit raw JSON instead of markdown")
    notes.set_defaults(_action="notes")

    auth = sub.add_parser("auth", help="Authenticate with a third-party (e.g., Google).")
    auth_sub = auth.add_subparsers(dest="auth_target")
    google_p = auth_sub.add_parser("google", help="Run the Google OAuth loopback flow.")
    google_p.add_argument(
        "--no-browser",
        action="store_true",
        help="don't try to open a browser; just print the URL",
    )
    auth.set_defaults(_action="auth")

    # Default subcommand: serve. Add the same args at the top level so
    # `inq --port 9090` works without a subcommand.
    _add_serve_args(p)
    return p


def _add_serve_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--port", type=int, default=9090, help="port to bind (default 9090)")
    p.add_argument("--root", type=Path, default=Path.cwd(), help="directory to serve (default cwd)")
    p.add_argument(
        "--source",
        default=None,
        help=(
            "alternate source. examples: "
            "'drive:FOLDER_ID' (Google Drive folder, requires `inq auth google`). "
            "default: local filesystem rooted at --root."
        ),
    )
    p.add_argument("--host", default="127.0.0.1", help="host to bind (default 127.0.0.1)")
    p.add_argument(
        "--max-file-size",
        type=_parse_size,
        default="2M",
        help="reject files above this size (e.g. 2M, 512k, 1048576). Default 2M.",
    )
    p.add_argument("--dev", action="store_true", help="enable CORS for vite dev (5173)")
    p.add_argument(
        "--provider",
        choices=known_providers(),
        default=None,
        help="override the configured provider for this run",
    )
    p.add_argument("--model", default=None, help="override the configured model for this run")
    p.add_argument(
        "--api-key-file",
        type=Path,
        default=None,
        help="read the api key from a file (overrides env / config)",
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    action = getattr(args, "_action", None)
    if args.command == "init" or action == "init":
        return run_init()

    if args.command == "notes" or action == "notes":
        return _run_notes(args, parser)

    if args.command == "auth" or action == "auth":
        return _run_auth(args, parser)

    return _run_serve(args, parser)


def _build_local(args: argparse.Namespace) -> LocalSource:
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        raise SourceError(f"--root is not a directory: {root}")
    return LocalSource(root=root, max_file_size=args.max_file_size)


def _build_source(args: argparse.Namespace):
    """Return a LocalSource or DriveSource based on --source / --root."""
    spec = (args.source or "").strip()
    if spec.startswith("drive:"):
        folder_id = spec[len("drive:") :].strip()
        if not folder_id:
            raise SourceError("drive:<FOLDER_ID> requires a folder id")
        return DriveSource(folder_id=folder_id)
    if spec and not spec.startswith("local"):
        raise SourceError(f"unknown source spec: {spec!r} (expected 'drive:<id>')")
    return _build_local(args)


def _run_auth(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    target = getattr(args, "auth_target", None)
    if target != "google":
        parser.error("usage: inq auth google [--no-browser]")
    cfg = load_config()
    cid = cfg.google_oauth.client_id
    cs = cfg.google_oauth.client_secret
    if not cid or not cs:
        print(
            "no Google OAuth client configured.\n"
            "  add to ~/.config/inq/config.toml:\n"
            "    [google_oauth]\n"
            '    client_id = "..."\n'
            '    client_secret = "..."\n'
            "  or set GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET in env.",
            file=sys.stderr,
        )
        return 2
    try:
        creds = google_auth.authorize_loopback(
            client_id=cid,
            client_secret=cs,
            open_browser=not args.no_browser,
        )
    except Exception as exc:
        print(f"auth failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    path = google_auth.save_credentials(creds)
    print(f"\n✓ saved Google credentials to {path}")
    print(f"  scopes:  {', '.join(creds.scopes)}")
    return 0


def _run_notes(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        parser.error(f"--root is not a directory: {root}")
    try:
        source = LocalSource(root=root)
    except SourceError as exc:
        parser.error(str(exc))
    threads = ThreadStore(source_label=source.label).list()
    if args.json:
        print(json.dumps({"source": source.label, "threads": threads}, indent=2))
        return 0
    sys.stdout.write(render_markdown(source.label, threads, filter_file=args.file))
    return 0


def _run_serve(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.host != "127.0.0.1":
        print(
            f"warning: binding to {args.host} — inq has no auth. "
            "only do this on a fully trusted network.",
            file=sys.stderr,
        )

    cli_key: str | None = None
    cli_key_source: str | None = None
    if args.api_key_file is not None:
        try:
            cli_key = args.api_key_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            parser.error(f"cannot read --api-key-file: {exc}")
        cli_key_source = f"--api-key-file ({args.api_key_file})"

    cfg = load_config()
    resolved = resolve_runtime(
        cfg,
        cli_provider=args.provider,
        cli_model=args.model,
        cli_key=cli_key,
        cli_key_source=cli_key_source,
    )
    if isinstance(resolved, str):
        print(resolved, file=sys.stderr)
        return 2

    try:
        provider = make_provider(resolved.provider, resolved.api_key, resolved.model)
    except Exception as exc:  # surface SDK init errors clearly
        print(f"failed to initialise {resolved.provider}: {exc}", file=sys.stderr)
        return 2

    try:
        local = _build_local(args)
    except SourceError as exc:
        parser.error(str(exc))

    registry = SourceRegistry(default=local, default_id="local")

    # Optional: also pre-register a Drive source if --source drive:... was given.
    if args.source and args.source.strip().startswith("drive:"):
        try:
            extra = _build_source(args)  # validates + instantiates
        except SourceError as exc:
            parser.error(str(exc))
        if extra is not local:
            try:
                registry.add("drive-cli", "drive", extra)
            except Exception as exc:
                parser.error(f"failed to add drive source: {exc}")

    app = create_app(registry=registry, provider=provider, dev=args.dev)

    print(f"inq {__version__}")
    print(f"  default:  {registry.default_id} = {local.label}")
    for entry in registry.list():
        if entry["id"] != registry.default_id:
            print(f"  source:   {entry['id']} = {entry['label']}")
    print(f"  provider: {provider.name}  ({resolved.source})")
    print(f"  model:    {provider.model}")
    print(f"  serving:  http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info", access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
