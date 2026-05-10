from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = Path(
    os.environ.get("INQ_CONFIG")
    or (Path.home() / ".config" / "inq" / "config.toml")
)


def _keychain_get(account: str, service: str = "inq") -> str | None:
    """Read a generic-password secret from the macOS keychain. No-op elsewhere."""
    if sys.platform != "darwin":
        return None
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    val = out.stdout.strip()
    return val or None


@dataclass
class GoogleOAuthConfig:
    client_id: str | None = None
    client_secret: str | None = None


@dataclass
class Config:
    provider: str | None = None
    model: str | None = None
    api_keys: dict[str, str] = field(default_factory=dict)
    google_oauth: GoogleOAuthConfig = field(default_factory=GoogleOAuthConfig)

    def api_key_for(self, provider: str) -> str | None:
        return self.api_keys.get(provider)


def load_config(path: Path = CONFIG_PATH) -> Config:
    data: dict = {}
    if path.is_file():
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            data = {}

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

    google = GoogleOAuthConfig()
    g_block = data.get("google_oauth")
    if isinstance(g_block, dict):
        cid = g_block.get("client_id")
        cs = g_block.get("client_secret")
        if isinstance(cid, str):
            google.client_id = cid
        if isinstance(cs, str):
            google.client_secret = cs

    # Env-var override (single-session use)
    env_cid = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    env_cs = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if env_cid:
        google.client_id = env_cid
    if env_cs:
        google.client_secret = env_cs

    # macOS keychain fallback for any missing field.
    # Stored under: service="inq", account="google_oauth_client_id" / "..._secret"
    if not google.client_id:
        google.client_id = _keychain_get("google_oauth_client_id")
    if not google.client_secret:
        google.client_secret = _keychain_get("google_oauth_client_secret")

    return Config(provider=provider, model=model, api_keys=api_keys, google_oauth=google)


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
    if cfg.google_oauth.client_id or cfg.google_oauth.client_secret:
        out.append("[google_oauth]")
        if cfg.google_oauth.client_id:
            out.append(f'client_id = "{_esc(cfg.google_oauth.client_id)}"')
        if cfg.google_oauth.client_secret:
            out.append(f'client_secret = "{_esc(cfg.google_oauth.client_secret)}"')
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
      provider:  CLI flag > config > env var present > keychain entry present
      key:       --api-key-file > env var > config file > macOS keychain
                 (service=inq, account=<provider>_api_key)
      model:     CLI flag > config > provider default
    """
    from . import providers as _p  # late import to avoid cycles

    provider = cli_provider or cfg.provider
    if provider is None:
        # Try to infer from env vars first, then keychain entries.
        for name, info in _p.REGISTRY.items():
            if os.environ.get(info["env_var"]):
                provider = name
                break
        if provider is None:
            for name in _p.known_providers():
                if _keychain_get(f"{name}_api_key"):
                    provider = name
                    break

    if provider is None:
        return (
            "no provider configured.\n"
            "  run `inq init` to set one up,\n"
            "  or set ANTHROPIC_API_KEY / GEMINI_API_KEY / OPENAI_API_KEY in the environment,\n"
            "  or store the key in macOS keychain:\n"
            "    security add-generic-password -s inq -a anthropic_api_key -w"
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
    elif (kc_key := _keychain_get(f"{provider}_api_key")):
        api_key, source = kc_key, f"keychain (inq/{provider}_api_key)"
    else:
        return (
            f"no api key found for {provider}.\n"
            f"  run `inq init` to save one,\n"
            f"  set {env_var} in the environment,\n"
            f"  or store in macOS keychain:\n"
            f"    security add-generic-password -s inq -a {provider}_api_key -w"
        )

    model = cli_model or cfg.model or info["default_model"]
    return Resolution(provider=provider, model=model, api_key=api_key, source=source)
