from __future__ import annotations

import getpass
import sys
import webbrowser

from . import providers as _p
from .config import CONFIG_PATH, Config, load_config, save_config


# Tiny ANSI helpers — keeps deps to zero.
def _bold(s: str) -> str:
    return f"\033[1m{s}\033[0m"


def _dim(s: str) -> str:
    return f"\033[2m{s}\033[0m"


def _amber(s: str) -> str:
    return f"\033[38;5;215m{s}\033[0m"


def _green(s: str) -> str:
    return f"\033[32m{s}\033[0m"


def _red(s: str) -> str:
    return f"\033[31m{s}\033[0m"


def _ask(prompt: str, *, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            v = input(f"{prompt}{suffix}: ").strip()
        except EOFError:
            print()
            sys.exit(1)
        if v:
            return v
        if default is not None:
            return default


def _ask_choice(prompt: str, options: list[tuple[str, str]], *, default_idx: int = 0) -> str:
    """Prompt for one of several keyed options. Returns the chosen key."""
    print()
    print(_bold(prompt))
    for i, (_, label) in enumerate(options, start=1):
        marker = _amber(">") if i - 1 == default_idx else " "
        print(f"  {marker} {i}) {label}")
    while True:
        try:
            raw = input(f"\nchoose [1-{len(options)}, default {default_idx + 1}]: ").strip()
        except EOFError:
            print()
            sys.exit(1)
        if not raw:
            return options[default_idx][0]
        try:
            n = int(raw)
        except ValueError:
            print(_red("  please enter a number"))
            continue
        if 1 <= n <= len(options):
            return options[n - 1][0]
        print(_red(f"  out of range (1-{len(options)})"))


def run_init() -> int:
    print()
    print(_amber(_bold("INQ")) + _dim("  · setup"))
    print(_dim("  inquiry — terminal-native AI code reading"))
    print()

    existing = load_config()
    if existing.provider or existing.api_keys:
        print(_dim(f"  existing config at {CONFIG_PATH}"))
        if existing.provider:
            print(_dim(f"  current provider: {existing.provider}"))

    provider_options = [
        (name, _p.REGISTRY[name]["display_name"]) for name in _p.known_providers()
    ]
    default_idx = 0
    if existing.provider in _p.known_providers():
        default_idx = list(_p.known_providers()).index(existing.provider)

    provider = _ask_choice("which provider?", provider_options, default_idx=default_idx)
    info = _p.REGISTRY[provider]

    print()
    print(f"open this in your browser to create a key for {_bold(info['display_name'])}:")
    print(f"  {_amber(info['api_key_url'])}")
    print()
    try:
        opened = webbrowser.open(info["api_key_url"], new=2)
    except Exception:
        opened = False
    if opened:
        print(_dim("  (browser opened)"))
        print()

    while True:
        try:
            key = getpass.getpass("paste api key (hidden): ").strip()
        except EOFError:
            print()
            return 1
        if key:
            break
        print(_red("  empty key; try again or ^C to cancel"))

    # Pick model
    models = info["models"]
    model_options = [
        (m, m + (_dim("  · default") if m == info["default_model"] else "")) for m in models
    ]
    model_default_idx = 0
    if existing.model in models:
        model_default_idx = models.index(existing.model)
    elif info["default_model"] in models:
        model_default_idx = models.index(info["default_model"])
    model = _ask_choice("pick a model", model_options, default_idx=model_default_idx)

    # Persist
    api_keys = dict(existing.api_keys)
    api_keys[provider] = key
    cfg = Config(provider=provider, model=model, api_keys=api_keys)
    path = save_config(cfg)

    print()
    print(_green("✓ saved"))
    print(_dim(f"  config: {path}"))
    print(_dim("  perms:  0600 (read/write owner only)"))
    print()
    print("done. run " + _bold("inq --port 9090") + " from any directory to start.")
    print()
    return 0
