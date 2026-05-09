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

---

## Configuration

Via a config file (`~/.inqrc` or `inq.yaml`) or CLI flags:

```yaml
port: 9090
root: ~/projects
ai:
  provider: claude          # claude | gemini | openai
  model: claude-sonnet-4-6     # default; bump to claude-opus-4-7 for harder reading
  api_key_env: ANTHROPIC_API_KEY
  prompt_caching: true         # cache file contents across follow-ups
  context_window: 20           # lines above/below the anchored region
  full_file_context: false     # send entire file vs windowed context
```

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
| AI client | Anthropic SDK with prompt caching | Direct. File contents cache well — the difference between snappy and chat-app-feel |
| Packaging | `pip install inq` (frontend pre-built into the wheel) | One install, no Node on the remote box |

---

## MVP Build Plan (a focused weekend, ~10 hrs)

### Phase 1: Backend (~2 hrs)
- [ ] FastAPI server with `--port` and `--root` CLI args; bind to `127.0.0.1` only
- [ ] `GET /api/tree?path=...&depth=1` — lazy directory listing one level at a time, `.gitignore`-aware, root-sandboxed
- [ ] `GET /api/file?path=...` — returns content + language hint, enforces size cap, rejects binaries
- [ ] `POST /api/ask` — receives `{question, file, anchor, context_lines, history}` (anchor is `{startLine, endLine}`), calls Anthropic with prompt caching, streams response via SSE

### Phase 2: Frontend Shell (~1.5 hrs)
- [ ] Vite + React + TypeScript + Tailwind scaffold
- [ ] Three-panel layout, dark theme baseline
- [ ] File tree component with lazy expand on click

### Phase 3: Viewer + Inline Input (~3 hrs)
- [ ] CodeMirror 6 viewer with line numbers, language modes, dark theme
- [ ] `@` keybind reads current selection (or cursor line if collapsed); opens an inline widget at the anchor
- [ ] Submit POSTs to `/api/ask` with the resolved range; response streams into the right panel

### Phase 4: Threading + Polish (~2.5 hrs)
- [ ] Right panel groups responses by file, anchored by line/range
- [ ] Follow-up questions stay inside the same thread
- [ ] Gutter markers on annotated lines; click to reopen the thread
- [ ] Keyboard nav (arrow keys, `Esc` to dismiss, `Cmd-K` to focus tree)

### Phase 5: Packaging (~1 hr)
- [ ] Build frontend, ship `dist/` inside the Python wheel
- [ ] Console script entrypoint: `inq --port 9090 --root .`

---

## Out of Scope for MVP
- Authentication (it's local port-forwarded, you own it)
- PDF rendering (Phase 2)
- Multi-user sessions
- Response persistence / history across sessions
- Diffing or editing files

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
