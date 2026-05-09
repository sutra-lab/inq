# inq

> A lightweight, terminal-native web UI for AI-assisted code and document review.

`inq` is a self-hosted server you run on your remote machine. You forward the port locally and open it in a browser. It gives you a file explorer, a scrollable code/document viewer, and inline AI annotation — no IDE, no clipboard, no context switching.

```
┌─────────┬────────────────────────┬────────────────┐
│ FILES   │ src/inq/sandbox.py     │ ASK            │
│  inq/   │  56  class Gitignore…  │  pyproject:7-12│
│   ai.py │  57    def __init__(   │  > what does…  │
│   ▸ …   │  58      …             │  · This file…  │
└─────────┴────────────────────────┴────────────────┘
```

Press `@` on any line — or with a range selected — and ask. The answer streams into the right panel, threaded per anchor.

## Quickstart

```bash
pip install inq          # not on PyPI yet — clone + pip install -e .
inq init                 # pick provider, paste API key, choose model
inq --port 9090 --root . # serve the current directory
```

On your local machine:

```bash
ssh -L 9090:localhost:9090 user@remote
```

Open `http://localhost:9090`.

## Providers

| Provider  | Models                                       | Where to mint a key                              |
| --------- | -------------------------------------------- | ------------------------------------------------ |
| Anthropic | `claude-sonnet-4-6`, `claude-opus-4-7`, …    | https://console.anthropic.com/settings/keys      |
| Google    | `gemini-2.5-pro`, `gemini-2.5-flash`, …      | https://aistudio.google.com/apikey               |
| OpenAI    | `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, …        | https://platform.openai.com/api-keys             |

Resolution order: `--api-key-file` flag → `<PROVIDER>_API_KEY` env var → `~/.config/inq/config.toml` (mode `0600`).

## Why

Reading code, specs, and documents deeply requires asking questions inline — but current workflows force you into a chat window, losing context and breaking flow. Cursor and VS Code remote are heavy editor environments; Claude Code lives in the terminal, not in a scrollable viewer. `inq` is the small, focused tool that fits between them: zero-install on the client, browser-native, and built around the act of asking questions in place.

## Status

Early. Working today: file tree, CodeMirror viewer with selection-range `@`, streaming responses, threading per anchor, prompt caching on file context. Coming soon: PDF rendering, Google Drive folders, OAuth-backed Gemini.

See [`project-spec.md`](./project-spec.md) for the full design.

## License

MIT — see [`LICENSE`](./LICENSE).
