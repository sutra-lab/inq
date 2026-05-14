# inq

> A lightweight, terminal-native web UI for reviewing and annotating code, PDFs, and markdown — together with AI.

`inq` is a self-hosted server. You run it on a remote machine, forward the port locally, and open it in a browser. It gives you a file explorer, a scrollable viewer for code / PDFs / markdown, and an annotation surface that humans and AI agents both write into. Threads stay anchored to the line (or page) you asked about, and persist per source.

```
┌─────────┬────────────────────────┬────────────────┐
│ FILES   │ src/inq/sandbox.py     │ THREADS        │
│  inq/   │  56  class Gitignore…  │  sandbox.py:56 │
│   ai.py │  57    def __init__(   │  › what does…  │
│   ▸ …   │  58      …             │  · It walks …  │
└─────────┴────────────────────────┴────────────────┘
```

Press `@` on any line (or with a range selected) to **ask the AI**. Press `#` to **leave a note** — same anchor, no model roundtrip. Responses stream in, render as markdown, and stay threaded per anchor.

## Quickstart

```bash
pip install inq-review                    # PyPI distribution; CLI is `inq`
inq init                                  # pick provider, paste API key, choose model
inq --port 9090 --root .                  # serve the current directory
```

On your local machine:

```bash
ssh -L 9090:localhost:9090 user@remote
```

Open `http://localhost:9090`.

## Features

- **Anchored threads.** Every question or note pins to a line range (code/markdown) or page (PDF). Threads persist per source at `~/.config/inq/threads/`.
- **Two annotation modes.** `@` asks the AI (streaming, threaded follow-ups). `#` saves a comment-only note (no AI call). Both render side-by-side in the panel.
- **Multi-format viewers.** CodeMirror for source, `pdf.js` for PDFs (cmaps + standard fonts bundled so math/ligatures render correctly), `react-markdown` for `.md` files.
- **Multi-source.** Browse the local filesystem by default; click "Open Drive folder" in the UI to pick a Google Drive folder via OAuth.
- **Three providers.** Anthropic, Google (Gemini), OpenAI — all with prompt-cached file context so follow-ups are cheap.
- **Markdown export.** "Copy md" buttons in the UI, or `inq notes --root <dir>` for the same output from the CLI.

## Providers

| Provider  | Models                                       | Where to mint a key                              |
| --------- | -------------------------------------------- | ------------------------------------------------ |
| Anthropic | `claude-sonnet-4-6`, `claude-opus-4-7`, …    | https://console.anthropic.com/settings/keys      |
| Google    | `gemini-2.5-pro`, `gemini-2.5-flash`, …      | https://aistudio.google.com/apikey               |
| OpenAI    | `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, …        | https://platform.openai.com/api-keys             |

Credential resolution order: `--api-key-file` flag → `<PROVIDER>_API_KEY` env var → `~/.config/inq/config.toml` (mode `0600`) → macOS keychain (service `inq`).

## Building from source

If you want to hack on the frontend, you'll need Node 20+:

```bash
git clone https://github.com/sutra-lab/inq && cd inq
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cd web
npm install
npm run build           # produces src/inq/web/ — FastAPI mounts it at /
# or `npm run dev` for hot-reload on :5173 (backend stays on :9090)
```

## Why

Reading code, specs, and documents deeply means asking questions inline — but most workflows force you into a chat window, losing context. Cursor and VS Code remote are heavy editor environments; Claude Code lives in the terminal, not in a scrollable viewer. `inq` is the small, focused tool that fits between them: zero-install on the client, browser-native, and built around asking questions in place.

See [`project-spec.md`](./project-spec.md) for the full design.

## License

MIT — see [`LICENSE`](./LICENSE).
