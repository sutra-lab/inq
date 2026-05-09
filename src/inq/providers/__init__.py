from __future__ import annotations

from typing import TYPE_CHECKING

from . import anthropic as anthropic_mod
from . import gemini as gemini_mod
from . import openai as openai_mod
from .base import AskRequest, Provider, StreamEvent

if TYPE_CHECKING:
    from typing import Type


REGISTRY: dict[str, dict] = {
    "anthropic": {
        "cls": anthropic_mod.AnthropicProvider,
        "default_model": anthropic_mod.DEFAULT_MODEL,
        "models": anthropic_mod.MODELS,
        "api_key_url": anthropic_mod.API_KEY_URL,
        "env_var": "ANTHROPIC_API_KEY",
        "display_name": anthropic_mod.DISPLAY_NAME,
    },
    "gemini": {
        "cls": gemini_mod.GeminiProvider,
        "default_model": gemini_mod.DEFAULT_MODEL,
        "models": gemini_mod.MODELS,
        "api_key_url": gemini_mod.API_KEY_URL,
        "env_var": "GEMINI_API_KEY",
        "display_name": gemini_mod.DISPLAY_NAME,
    },
    "openai": {
        "cls": openai_mod.OpenAIProvider,
        "default_model": openai_mod.DEFAULT_MODEL,
        "models": openai_mod.MODELS,
        "api_key_url": openai_mod.API_KEY_URL,
        "env_var": "OPENAI_API_KEY",
        "display_name": openai_mod.DISPLAY_NAME,
    },
}


def make_provider(name: str, api_key: str, model: str | None = None) -> Provider:
    info = REGISTRY.get(name)
    if info is None:
        raise ValueError(f"unknown provider: {name!r} (known: {list(REGISTRY)})")
    return info["cls"](api_key=api_key, model=model)


def known_providers() -> list[str]:
    return list(REGISTRY.keys())


__all__ = [
    "AskRequest",
    "Provider",
    "StreamEvent",
    "REGISTRY",
    "make_provider",
    "known_providers",
]
