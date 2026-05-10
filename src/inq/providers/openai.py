from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from ._context import (
    SYSTEM_PROMPT,
    build_file_block,
    build_user_text,
    format_context,
)
from .base import AskRequest, StreamEvent

DEFAULT_MODEL = "gpt-4o"
MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"]
API_KEY_URL = "https://platform.openai.com/api-keys"
DISPLAY_NAME = "OpenAI (GPT)"


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise ValueError("openai provider requires a non-empty api_key")
        self.api_key = api_key
        self.model = model or DEFAULT_MODEL
        self._client = AsyncOpenAI(api_key=api_key)

    async def stream(self, req: AskRequest) -> AsyncIterator[StreamEvent]:
        skipped = req.file_data.get("skipped")
        if skipped:
            yield StreamEvent("error", f"file skipped ({skipped}); cannot answer")
            return

        ctx = format_context(req)
        # Putting the file block in the system message keeps it as a stable
        # prefix; OpenAI's automatic prompt caching will pick this up for
        # follow-ups on prompts >= ~1024 tokens.
        system_text = SYSTEM_PROMPT + "\n\n" + build_file_block(req, ctx)

        messages: list[dict] = [{"role": "system", "content": system_text}]
        for h in req.history:
            role = h.get("role")
            content = h.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": build_user_text(req, ctx)})

        yield StreamEvent("start", {"provider": self.name, "model": self.model})

        try:
            stream = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=req.max_tokens,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
            )
            async for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    text = getattr(delta, "content", None)
                    if text:
                        yield StreamEvent("token", text)
                u = getattr(chunk, "usage", None)
                if u is not None:
                    details = getattr(u, "prompt_tokens_details", None)
                    cache_read = getattr(details, "cached_tokens", None) if details else None
                    yield StreamEvent(
                        "usage",
                        {
                            "input_tokens": getattr(u, "prompt_tokens", None),
                            "output_tokens": getattr(u, "completion_tokens", None),
                            "cache_read_input_tokens": cache_read,
                            "cache_creation_input_tokens": None,
                        },
                    )
        except Exception as exc:
            yield StreamEvent("error", f"{type(exc).__name__}: {exc}")
