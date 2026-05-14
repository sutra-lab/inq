from __future__ import annotations

import sys
from pathlib import Path

import pytest

from inq import config as config_mod
from inq.config import Config, load_config, resolve_runtime


@pytest.fixture(autouse=True)
def stub_keychain(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default to "no keychain hit" so tests don't read the actual macOS keychain."""
    monkeypatch.setattr(config_mod, "_keychain_get", lambda *args, **kwargs: None)


@pytest.fixture(autouse=True)
def clear_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
    ):
        monkeypatch.delenv(var, raising=False)


class TestLoadConfig:
    def test_missing_file_returns_empty_config(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "does-not-exist.toml")
        assert cfg.provider is None
        assert cfg.api_keys == {}

    def test_loads_provider_model_and_keys(self, tmp_path: Path) -> None:
        p = tmp_path / "c.toml"
        p.write_text(
            'provider = "anthropic"\n'
            'model = "claude-sonnet-4-6"\n'
            '[providers.anthropic]\n'
            'api_key = "k1"\n'
            '[providers.openai]\n'
            'api_key = "k2"\n',
            encoding="utf-8",
        )
        cfg = load_config(p)
        assert cfg.provider == "anthropic"
        assert cfg.model == "claude-sonnet-4-6"
        assert cfg.api_keys == {"anthropic": "k1", "openai": "k2"}

    def test_malformed_toml_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "c.toml"
        p.write_text("this is = not [ valid toml", encoding="utf-8")
        cfg = load_config(p)
        assert cfg.provider is None

    def test_google_oauth_env_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        p = tmp_path / "c.toml"
        p.write_text(
            '[google_oauth]\n'
            'client_id = "from-file"\n'
            'client_secret = "secret-file"\n',
            encoding="utf-8",
        )
        monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "from-env")
        cfg = load_config(p)
        assert cfg.google_oauth.client_id == "from-env"
        assert cfg.google_oauth.client_secret == "secret-file"

    def test_google_oauth_keychain_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            config_mod,
            "_keychain_get",
            lambda account, service="inq": {
                "google_oauth_client_id": "kc-id",
                "google_oauth_client_secret": "kc-secret",
            }.get(account),
        )
        cfg = load_config(tmp_path / "missing.toml")
        assert cfg.google_oauth.client_id == "kc-id"
        assert cfg.google_oauth.client_secret == "kc-secret"


class TestResolveRuntime:
    def test_cli_key_wins(self) -> None:
        cfg = Config(api_keys={"anthropic": "from-config"})
        res = resolve_runtime(
            cfg,
            cli_provider="anthropic",
            cli_key="from-cli",
            cli_key_source="--api-key-file",
        )
        assert not isinstance(res, str)
        assert res.api_key == "from-cli"
        assert res.source == "--api-key-file"

    def test_env_beats_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
        cfg = Config(provider="anthropic", api_keys={"anthropic": "from-config"})
        res = resolve_runtime(cfg)
        assert not isinstance(res, str)
        assert res.api_key == "from-env"
        assert "env (ANTHROPIC_API_KEY)" in res.source

    def test_config_when_no_env(self) -> None:
        cfg = Config(provider="openai", api_keys={"openai": "k"})
        res = resolve_runtime(cfg)
        assert not isinstance(res, str)
        assert res.api_key == "k"
        assert res.source == "config file"

    def test_keychain_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            config_mod,
            "_keychain_get",
            lambda account, service="inq": "from-kc" if account == "anthropic_api_key" else None,
        )
        cfg = Config(provider="anthropic")
        res = resolve_runtime(cfg)
        assert not isinstance(res, str)
        assert res.api_key == "from-kc"
        assert "keychain" in res.source

    def test_no_provider_returns_error_string(self) -> None:
        cfg = Config()
        res = resolve_runtime(cfg)
        assert isinstance(res, str)
        assert "no provider configured" in res

    def test_unknown_provider_returns_error_string(self) -> None:
        cfg = Config(provider="bogus")
        res = resolve_runtime(cfg)
        assert isinstance(res, str)
        assert "unknown provider" in res

    def test_no_key_returns_error_string(self) -> None:
        cfg = Config(provider="anthropic")
        res = resolve_runtime(cfg)
        assert isinstance(res, str)
        assert "no api key found" in res

    def test_default_model_applied(self) -> None:
        cfg = Config(provider="anthropic", api_keys={"anthropic": "k"})
        res = resolve_runtime(cfg)
        assert not isinstance(res, str)
        assert res.model is not None  # provider default kicks in

    def test_cli_model_wins(self) -> None:
        cfg = Config(provider="anthropic", api_keys={"anthropic": "k"}, model="from-config")
        res = resolve_runtime(cfg, cli_model="from-cli")
        assert not isinstance(res, str)
        assert res.model == "from-cli"


def test_keychain_no_op_on_non_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    # Real function, not the stubbed one — we want to assert it short-circuits.
    from inq.config import _keychain_get as kc
    assert kc("anthropic_api_key") is None
