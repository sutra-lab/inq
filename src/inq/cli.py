from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn

from . import __version__
from .config import load_config, resolve_runtime
from .init_cmd import run_init
from .providers import known_providers, make_provider
from .server import create_app
from .sources import LocalSource, SourceError


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

    # Default subcommand: serve. Add the same args at the top level so
    # `inq --port 9090` works without a subcommand.
    _add_serve_args(p)
    return p


def _add_serve_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--port", type=int, default=9090, help="port to bind (default 9090)")
    p.add_argument("--root", type=Path, default=Path.cwd(), help="directory to serve (default cwd)")
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

    return _run_serve(args, parser)


def _run_serve(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        parser.error(f"--root is not a directory: {root}")

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
        source = LocalSource(root=root, max_file_size=args.max_file_size)
    except SourceError as exc:
        parser.error(str(exc))

    app = create_app(source=source, provider=provider, dev=args.dev)

    print(f"inq {__version__}")
    print(f"  source:   {source.label}")
    print(f"  provider: {provider.name}  ({resolved.source})")
    print(f"  model:    {provider.model}")
    print(f"  serving:  http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info", access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
