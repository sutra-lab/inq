from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


CONFIG_PATH = Path(
    os.environ.get("INQ_CONFIG")
    or (Path.home() / ".config" / "inq" / "config.toml")
)


@dataclass
class Config:
    provider: str | None = None
    model: str | None = None
    api_keys: dict[str, str] = field(default_factory=dict)

    def api_key_for(self, provider: str) -> str | None:
        return self.api_keys.get(provider)


def load_config(path: Path = CONFIG_PATH) -> Config:
    if not path.is_file():
        return Config()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return Config()

    provider = data.get("provider") if isinstance(data.get("provider"), str) else None
    model = data.get("model") if isinstance(data.get("model"), str) else None

    api_keys: dict[str, str] = {}
    providers_block = data.get("providers")
    if isinstance(providers_block, dict):
        for name, block in providers_block.items():
            if isinstance(block, dict):
                key = block.get("api_key")
                if isinstance(key, str) and key:
                    api_keys[name] = key

    return Config(provider=provider, model=model, api_keys=api_keys)


def save_config(cfg: Config, path: Path = CONFIG_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    if cfg.provider:
        out.append(f'provider = "{_esc(cfg.provider)}"')
    if cfg.model:
        out.append(f'model = "{_esc(cfg.model)}"')
    out.append("")
    for name in sorted(cfg.api_keys):
        out.append(f"[providers.{name}]")
        out.append(f'api_key = "{_esc(cfg.api_keys[name])}"')
        out.append("")
    body = "\n".join(out).rstrip() + "\n"
    # Write with restrictive permissions (0600).
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
    # Re-apply mode in case the file already existed with looser perms.
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


@dataclass
class Resolution:
    provider: str
    model: str | None
    api_key: str
    source: str  # human-readable: "config file", "env (ANTHROPIC_API_KEY)", "--api-key-file"


def resolve_runtime(
    cfg: Config,
    *,
    cli_provider: str | None = None,
    cli_model: str | None = None,
    cli_key: str | None = None,
    cli_key_source: str | None = None,
) -> Resolution | str:
    """Resolve the (provider, model, key) to use at startup.

    Returns a :class:`Resolution` on success, or a human-readable error string
    so the CLI can print it and exit non-zero.

    Order:
      provider:  CLI flag > config > infer from any env var with a key
      key:       --api-key-file > env var for provider > config file
      model:     CLI flag > config > provider default
    """
    from . import providers as _p  # late import to avoid cycles

    provider = cli_provider or cfg.provider
    if provider is None:
        # Try to infer from env.
        for name, info in _p.REGISTRY.items():
            if os.environ.get(info["env_var"]):
                provider = name
                break

    if provider is None:
        return (
            "no provider configured.\n"
            "  run `inq init` to set one up,\n"
            "  or set ANTHROPIC_API_KEY / GEMINI_API_KEY / OPENAI_API_KEY in the environment."
        )

    if provider not in _p.REGISTRY:
        return f"unknown provider {provider!r} (known: {_p.known_providers()})"

    info = _p.REGISTRY[provider]
    env_var = info["env_var"]

    if cli_key:
        api_key, source = cli_key, cli_key_source or "--api-key-file"
    elif (env_key := os.environ.get(env_var)):
        api_key, source = env_key, f"env ({env_var})"
    elif (cfg_key := cfg.api_key_for(provider)):
        api_key, source = cfg_key, "config file"
    else:
        return (
            f"no api key found for {provider}.\n"
            f"  run `inq init` to save one,\n"
            f"  or set {env_var} in the environment."
        )

    model = cli_model or cfg.model or info["default_model"]
    return Resolution(provider=provider, model=model, api_key=api_key, source=source)
