from __future__ import annotations

from collections.abc import AsyncIterator

from google import genai
from google.genai import types

from ._context import (
    SYSTEM_PROMPT,
    build_file_block,
    build_user_text,
    format_context,
)
from .base import AskRequest, StreamEvent

DEFAULT_MODEL = "gemini-2.5-pro"
MODELS = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"]
API_KEY_URL = "https://aistudio.google.com/apikey"
DISPLAY_NAME = "Google (Gemini)"


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise ValueError("gemini provider requires a non-empty api_key")
        self.api_key = api_key
        self.model = model or DEFAULT_MODEL
        self._client = genai.Client(api_key=api_key)

    async def stream(self, req: AskRequest) -> AsyncIterator[StreamEvent]:
        skipped = req.file_data.get("skipped")
        if skipped:
            yield StreamEvent("error", f"file skipped ({skipped}); cannot answer")
            return

        ctx = format_context(req)
        # Gemini accepts a single system_instruction string; fold our system
        # prompt and the file block together. Implicit caching kicks in for
        # large prefixes, so keeping the file block at the start is enough.
        system_text = SYSTEM_PROMPT + "\n\n" + build_file_block(req, ctx)

        contents: list[types.Content] = []
        for h in req.history:
            role = h.get("role")
            content = h.get("content")
            if not isinstance(content, str):
                continue
            if role == "user":
                contents.append(
                    types.Content(role="user", parts=[types.Part.from_text(text=content)])
                )
            elif role == "assistant":
                contents.append(
                    types.Content(role="model", parts=[types.Part.from_text(text=content)])
                )
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=build_user_text(req, ctx))],
            )
        )

        yield StreamEvent("start", {"provider": self.name, "model": self.model})

        config = types.GenerateContentConfig(
            system_instruction=system_text,
            max_output_tokens=req.max_tokens,
        )

        try:
            stream = await self._client.aio.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config,
            )
            usage = None
            async for chunk in stream:
                text = getattr(chunk, "text", None)
                if text:
                    yield StreamEvent("token", text)
                # Each chunk may carry partial usage; keep the latest one.
                u = getattr(chunk, "usage_metadata", None)
                if u is not None:
                    usage = u
            if usage is not None:
                yield StreamEvent(
                    "usage",
                    {
                        "input_tokens": getattr(usage, "prompt_token_count", None),
                        "output_tokens": getattr(usage, "candidates_token_count", None),
                        "cache_read_input_tokens": getattr(
                            usage, "cached_content_token_count", None
                        ),
                        "cache_creation_input_tokens": None,
                    },
                )
        except Exception as exc:
            yield StreamEvent("error", f"{type(exc).__name__}: {exc}")
