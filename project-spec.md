# inq — Project Specification

> A lightweight, terminal-native web UI for AI-assisted code and document review.

---

## Problem

Reading code, specs, and documents deeply requires asking questions inline—but current workflows force you to copy-paste into a chat window, losing context and breaking flow. IDE plugins like Copilot are too heavy. Jupyter is notebook-centric. There is no minimal, hacker-friendly tool that lets you browse a codebase or document, ask questions at any line, and get AI responses in context—all accessible via SSH port forwarding.

---

## Solution

`inq` is a self-hosted web server you run on your remote machine. You port-forward it locally and open it in a browser. It gives you a file explorer, a scrollable code/document viewer, and inline AI annotation—no IDE, no clipboard, no context switching.

---

## Usage

```bash
inq --port 9090 --root ~/my-project
```

Then on your local machine:

```bash
ssh -L 9090:localhost:9090 user@remote
```

Open `http://localhost:9090` in your browser.

---

## Core Features (MVP)

### 1. File Explorer (Left Panel)
- Directory tree of the `--root` path
- Click to open any file (code, markdown, text, PDF eventually)
- Collapsible folders
- Highlight currently open file

### 2. File Viewer (Center Panel)
- Syntax-highlighted, line-numbered display
- Smooth scrolling
- A cursor/highlight that tracks which line you're on
- Press `@` at any line to open an inline input field anchored to that line

### 3. Inline Question Input
- Triggered by `@` keypress on any line, or with a range selected
- If a selection is active, the question anchors to the full selection (multi-line spans supported — ask about a function, block, or paragraph); otherwise it anchors to the cursor line
- Lightweight text field appears inline below the anchor
- Submit with `Enter` or `Ctrl+D`; `Esc` dismisses
- A gutter marker remains on annotated lines so threads can be reopened

### 4. AI Response Panel (Right Panel or Overlay)
- Responses appear in a side panel so the file view is undisturbed
- Each response is anchored to the line/file it came from
- Responses are threaded per line (follow-up questions stay in context)
- Configurable AI backend (Claude, Gemini, OpenAI)

### 5. Context Sent to AI
- The question text
- File name and language
- The anchored region — selection or cursor line — plus ±N lines of surrounding context (default ±20)
- Optionally: full file content (toggle)
- Conversation history per thread (for follow-ups)
- File contents are sent inside a cached prompt block (Anthropic prompt caching), so follow-ups on the same file are cheap and fast

### 6. Comment-only Notes (`#` keybind)
- Same anchor mechanism as `@`, but no AI roundtrip
- Renders alongside AI threads in the right panel with a `#` sigil
- Useful for "ask me about this later" or static review notes that don't need a model

---

## Configuration

Resolution order for credentials: `--api-key-file` flag → `<PROVIDER>_API_KEY` env var → `~/.config/inq/config.toml` (mode `0600`) → macOS keychain (service `inq`).

`~/.config/inq/config.toml`:

```toml
provider = "anthropic"         # anthropic | gemini | openai
model = "claude-sonnet-4-6"    # bump to claude-opus-4-7 for harder reading

[providers.anthropic]
api_key = "..."                # or fall back to keychain / env var

[google_oauth]                 # only needed if using Google Drive as a source
client_id = "..."
client_secret = "..."
```

`inq init` walks you through this interactively.

---

## Security & Sandboxing

- All client-supplied paths are resolved to absolute paths and asserted to live inside `--root`. Reject anything that escapes via `..` or symlinks.
- The server is read-only by design — no write or exec endpoints.
- No auth: SSH port forwarding is the trust boundary. Bind to `127.0.0.1` only, never `0.0.0.0`.
- Refuse files above a size cap (default 2 MB) and binary files (NUL-byte sniff). Return an explanatory stub instead of bytes.

---

## Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Backend | Python + FastAPI | Async-native, clean SSE streaming, three endpoints fit on one screen |
| Frontend | Vite + React + TypeScript | UI is the product — vanilla JS turns to spaghetti once threading, streaming, and selection ranges land |
| Editor / viewer | CodeMirror 6 | Decoration & widget API is purpose-built for inline `@` inputs and line-anchored markers; selection ranges are first-class |
| Styling | Tailwind | Dark theme + dense UI with no CSS architecture debate |
| AI client | Anthropic / Google `google-genai` / OpenAI SDKs behind a `Provider` protocol | Three providers via one interface; prompt caching on the shared file-context system block |
| Source layer | `FileSource` protocol with `LocalSource` (filesystem) and `DriveSource` (Google Drive v3) | A registry maps multiple sources at runtime — local always present, Drive added via the UI after OAuth |
| Packaging | `pip install inq-review` (frontend pre-built into the wheel; sdist also includes the built assets) | One install, no Node on the remote box. `inq` is taken on PyPI — the import name and CLI command are still `inq` |

---

## Build Plan

### Phase 1: Backend (shipped)
- [x] FastAPI server with `--port` and `--root` CLI args; bind to `127.0.0.1` only
- [x] `GET /api/tree?path=...&depth=1` — lazy directory listing one level at a time, `.gitignore`-aware, root-sandboxed
- [x] `GET /api/file?path=...` — returns content + language hint, enforces size cap, rejects binaries
- [x] `POST /api/ask` — receives `{question, file, anchor, context_lines, history}` (anchor is `{startLine, endLine}`), calls the provider with prompt caching, streams via SSE

### Phase 2: Frontend Shell (shipped)
- [x] Vite + React 19 + TypeScript + Tailwind v4 scaffold
- [x] Three-panel layout; dark + light (paper) themes
- [x] File tree component with lazy expand on click

### Phase 3: Viewer + Inline Input (shipped)
- [x] CodeMirror 6 viewer with line numbers, language modes, both themes
- [x] `@` keybind reads selection (or cursor line); inline widget opens at the anchor
- [x] Submit POSTs to `/api/ask`; response streams into the right panel, rendered as markdown

### Phase 4: Threading + Polish (shipped)
- [x] Right panel groups responses by file, anchored by line/range
- [x] Follow-up questions stay inside the same thread
- [x] Gutter markers on annotated lines; click to reopen the thread
- [x] Keyboard nav, dismiss, focus

### Phase 5: Packaging (shipped)
- [x] Build frontend, ship inside the Python wheel
- [x] Console script entrypoint: `inq --port 9090 --root .`

### Phase 6a: PDF + File Source Abstraction (shipped)
- [x] `FileSource` protocol; `LocalSource` reads the filesystem, sandboxed at `--root`
- [x] PDF viewer (pdfjs-dist) with page anchors; cmaps + standard fonts bundled

### Phase 6b: Google Drive + OAuth (shipped)
- [x] `DriveSource` reads a Drive folder as `inq`'s root (Drive v3, file-id-as-path)
- [x] Browser-driven OAuth: "Open Drive folder" button → popup → multi-source registry adds the folder
- [x] Account-picker re-auth when the current account can't see the requested folder
- [x] OAuth client credentials read from config + macOS keychain fallback

### Phase 7a: Persistent Threads (shipped)
- [x] Threads persist per source at `~/.config/inq/threads/<sha256(source.label)[:16]>.json`
- [x] Each source label is hashed for the filename — labels include `"local: <abs path>"` or `"drive: <folder name>"`

### Phase 7b: Comment-only Notes (shipped)
- [x] `#` keybind creates a thread with `mode: 'comment'` — no AI call, no follow-ups against the model
- [x] Renders with `#` sigil instead of `›`; follow-ups append additional notes

### Phase 7c: Markdown Export (shipped)
- [x] `inq notes --root <dir> [--file <path>] [--json]` prints threads as markdown
- [x] "Copy md" buttons in the UI use the same renderer
- [x] Same shape works for both `@` ask and `#` comment threads

### CI / Release (shipped)
- [x] `ci.yml`: python smoke matrix (3.11/3.12) + ruff + web typecheck/build
- [x] `release.yml`: tag-driven (`v*`), builds frontend → builds sdist + wheel → verifies frontend is bundled → publishes via PyPI Trusted Publishing

---

## Out of Scope (still)
- Authentication (it's local port-forwarded, you own it)
- Multi-user sessions
- Diffing or editing files
- Server-side write endpoints (read-only by design)

---

## Name

**inq** — short for inquiry. Feels at home alongside `tmux`, `mosh`, `htop`. Runs like a CLI tool, lives in your workflow.

---

## Why Build It

> "Even if something is useful for only two people, it's worth building."

`inq` is *reading*-shaped, not *editing*-shaped. Cursor, VS Code remote, and code-server are heavy editor environments — overkill when the task is "scroll through a repo and ask questions." Claude Code is great for agentic edits but lives in the terminal, not in a scrollable viewer. `inq` is the small, focused tool that fits between them: zero-install on the client, browser-native, built around the act of asking questions in place.

If it's useful for you and Claude Code, it's already worth it. If your team picks it up, that's a bonus.

---

*Spec drafted: May 2026. Ship it.*
