from __future__ import annotations

from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic

from ._context import (
    SYSTEM_PROMPT,
    build_file_block,
    build_user_text,
    format_context,
)
from .base import AskRequest, StreamEvent

DEFAULT_MODEL = "claude-sonnet-4-6"
MODELS = ["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5"]
API_KEY_URL = "https://console.anthropic.com/settings/keys"
DISPLAY_NAME = "Anthropic (Claude)"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise ValueError("anthropic provider requires a non-empty api_key")
        self.api_key = api_key
        self.model = model or DEFAULT_MODEL
        self._client = AsyncAnthropic(api_key=api_key)

    async def stream(self, req: AskRequest) -> AsyncIterator[StreamEvent]:
        skipped = req.file_data.get("skipped")
        if skipped:
            yield StreamEvent("error", f"file skipped ({skipped}); cannot answer")
            return

        ctx = format_context(req)
        system_blocks = [
            {"type": "text", "text": SYSTEM_PROMPT},
            {
                "type": "text",
                "text": build_file_block(req, ctx),
                "cache_control": {"type": "ephemeral"},
            },
        ]

        messages: list[dict] = []
        for h in req.history:
            role = h.get("role")
            content = h.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": build_user_text(req, ctx)})

        yield StreamEvent("start", {"provider": self.name, "model": self.model})

        try:
            async with self._client.messages.stream(
                model=self.model,
                max_tokens=req.max_tokens,
                system=system_blocks,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield StreamEvent("token", text)
                final = await stream.get_final_message()
                u = getattr(final, "usage", None)
                if u is not None:
                    yield StreamEvent(
                        "usage",
                        {
                            "input_tokens": getattr(u, "input_tokens", None),
                            "output_tokens": getattr(u, "output_tokens", None),
                            "cache_read_input_tokens": getattr(
                                u, "cache_read_input_tokens", None
                            ),
                            "cache_creation_input_tokens": getattr(
                                u, "cache_creation_input_tokens", None
                            ),
                        },
                    )
        except Exception as exc:
            yield StreamEvent("error", f"{type(exc).__name__}: {exc}")
